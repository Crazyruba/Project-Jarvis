"""
Het geheugen van JARVIS.

Twee soorten, in één SQLite-bestand:

  • feiten    — wat blijvend over de eigenaar bekend is (voorkeuren, projecten)
  • beurten   — het gesprekslogboek, voor "wat zei ik net ook alweer"

Het verschil met een simpele tabel zit in het ophalen. Alles wat ooit onthouden
is in élke prompt stoppen werkt tot een stuk of twintig feiten en daarna niet
meer: het kost tokens en het leidt het model af. Daarom staat er een FTS5-index
over de feiten en haalt `context_for()` alleen op wat bij de huidige vraag past,
aangevuld met de feiten die het vaakst van pas kwamen.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

SOORTEN = {"feit", "voorkeur", "project", "doel"}
SCHEMA_VERSIE = 1


@dataclass(frozen=True)
class Feit:
    id: int
    soort: str
    inhoud: str
    treffers: int


def _normaliseer(tekst: str) -> str:
    """Voor het ontdubbelen: accenten, hoofdletters en leestekens weg."""
    plat = unicodedata.normalize("NFKD", tekst.lower())
    plat = "".join(teken for teken in plat if not unicodedata.combining(teken))
    plat = re.sub(r"[^a-z0-9]+", " ", plat)
    # Opeenvolgende spaties samenvoegen, anders telt "koffie  zwart" als nieuw.
    return " ".join(plat.split())


def _fts_query(tekst: str) -> str:
    """
    Maak van vrije tekst een veilige FTS5-zoekopdracht.

    FTS5 heeft een eigen syntaxis; een vraag met een aanhalingsteken of een
    losse `-` laat de query anders ontploffen. Daarom: alleen woorden, als
    OR aan elkaar, elk met een sterretje zodat verbuigingen meetellen.
    """
    woorden = [w for w in re.findall(r"[0-9A-Za-zÀ-ÿ]{3,}", tekst.lower())][:12]
    return " OR ".join(f'"{w}"*' for w in woorden)


class Memory:
    """Blijvende feiten en het gesprekslogboek."""

    def __init__(self, pad: str = "data/memory.db"):
        bestand = Path(pad)
        bestand.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: de spraaklus draait in een eigen thread.
        self.conn = sqlite3.connect(bestand, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._maak_schema()

    # -- schema ------------------------------------------------------------
    def _maak_schema(self) -> None:
        with self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS feiten (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    soort       TEXT NOT NULL,
                    inhoud      TEXT NOT NULL,
                    sleutel     TEXT NOT NULL UNIQUE,   -- genormaliseerd, tegen dubbel
                    treffers    INTEGER NOT NULL DEFAULT 0,
                    aangemaakt  TEXT NOT NULL DEFAULT (datetime('now')),
                    gezien      TEXT
                );

                CREATE TABLE IF NOT EXISTS beurten (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    rol     TEXT NOT NULL,
                    inhoud  TEXT NOT NULL,
                    moment  TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS beurten_moment ON beurten(moment);

                -- Losse FTS-tabel plus triggers: zo blijft de index vanzelf
                -- gelijklopen met de feiten, ook bij wijzigen en verwijderen.
                CREATE VIRTUAL TABLE IF NOT EXISTS feiten_fts
                    USING fts5(inhoud, content='feiten', content_rowid='id');

                CREATE TRIGGER IF NOT EXISTS feiten_na_insert AFTER INSERT ON feiten
                BEGIN
                    INSERT INTO feiten_fts(rowid, inhoud) VALUES (new.id, new.inhoud);
                END;
                CREATE TRIGGER IF NOT EXISTS feiten_na_delete AFTER DELETE ON feiten
                BEGIN
                    INSERT INTO feiten_fts(feiten_fts, rowid, inhoud)
                        VALUES ('delete', old.id, old.inhoud);
                END;
                CREATE TRIGGER IF NOT EXISTS feiten_na_update AFTER UPDATE OF inhoud ON feiten
                BEGIN
                    INSERT INTO feiten_fts(feiten_fts, rowid, inhoud)
                        VALUES ('delete', old.id, old.inhoud);
                    INSERT INTO feiten_fts(rowid, inhoud) VALUES (new.id, new.inhoud);
                END;
                """
            )
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSIE}")

    # -- feiten ------------------------------------------------------------
    def onthoud(self, soort: str, inhoud: str) -> str:
        """Sla iets blijvends op. Dubbele inhoud wordt niet nog eens bewaard."""
        inhoud = inhoud.strip()
        if not inhoud:
            return "Daar zat niets in om te onthouden."

        soort = soort if soort in SOORTEN else "feit"
        sleutel = _normaliseer(inhoud)

        bestaand = self.conn.execute(
            "SELECT id FROM feiten WHERE sleutel = ?", (sleutel,)
        ).fetchone()
        if bestaand:
            return "Dat weet ik al."

        with self.conn:
            self.conn.execute(
                "INSERT INTO feiten (soort, inhoud, sleutel) VALUES (?, ?, ?)",
                (soort, inhoud, sleutel),
            )
        return "Opgeslagen."

    def vergeet(self, zoekterm: str) -> str:
        """Verwijder de feiten die op deze zoekterm passen."""
        treffers = self.zoek(zoekterm, limiet=10)
        if not treffers:
            return f"Ik vond niets over '{zoekterm}'."

        with self.conn:
            self.conn.executemany(
                "DELETE FROM feiten WHERE id = ?", [(f.id,) for f in treffers]
            )
        if len(treffers) == 1:
            return f"Vergeten: {treffers[0].inhoud}"
        return f"{len(treffers)} herinneringen vergeten."

    def zoek(self, vraag: str, limiet: int = 5) -> list[Feit]:
        """Zoek de feiten die het best bij deze vraag passen."""
        query = _fts_query(vraag)
        if not query:
            return []

        rijen = self.conn.execute(
            """
            SELECT f.id, f.soort, f.inhoud, f.treffers
            FROM feiten_fts
            JOIN feiten f ON f.id = feiten_fts.rowid
            WHERE feiten_fts MATCH ?
            ORDER BY bm25(feiten_fts), f.treffers DESC
            LIMIT ?
            """,
            (query, limiet),
        ).fetchall()

        if rijen:
            # Wat van pas kwam telt mee in de volgorde van een volgende keer.
            with self.conn:
                self.conn.executemany(
                    "UPDATE feiten SET treffers = treffers + 1, "
                    "gezien = datetime('now') WHERE id = ?",
                    [(r["id"],) for r in rijen],
                )

        return [Feit(r["id"], r["soort"], r["inhoud"], r["treffers"]) for r in rijen]

    def alle_feiten(self, limiet: int = 100) -> list[Feit]:
        rijen = self.conn.execute(
            "SELECT id, soort, inhoud, treffers FROM feiten "
            "ORDER BY aangemaakt DESC LIMIT ?", (limiet,)
        ).fetchall()
        return [Feit(r["id"], r["soort"], r["inhoud"], r["treffers"]) for r in rijen]

    def kern(self, limiet: int = 5) -> list[Feit]:
        """De feiten die het vaakst van pas kwamen; die horen er altijd bij."""
        rijen = self.conn.execute(
            "SELECT id, soort, inhoud, treffers FROM feiten "
            "WHERE treffers > 0 ORDER BY treffers DESC, aangemaakt DESC LIMIT ?",
            (limiet,),
        ).fetchall()
        return [Feit(r["id"], r["soort"], r["inhoud"], r["treffers"]) for r in rijen]

    # -- gesprekslogboek ---------------------------------------------------
    def log(self, rol: str, inhoud: str) -> None:
        inhoud = (inhoud or "").strip()
        if not inhoud:
            return
        with self.conn:
            self.conn.execute(
                "INSERT INTO beurten (rol, inhoud) VALUES (?, ?)", (rol, inhoud)
            )

    def recente_beurten(self, limiet: int = 6, binnen_uren: int = 24) -> list[dict]:
        grens = (datetime.now() - timedelta(hours=binnen_uren)).strftime(
            "%Y-%m-%d %H:%M:%S")
        rijen = self.conn.execute(
            "SELECT rol, inhoud FROM beurten WHERE moment >= ? "
            "ORDER BY id DESC LIMIT ?", (grens, limiet),
        ).fetchall()
        return [{"rol": r["rol"], "inhoud": r["inhoud"]} for r in reversed(rijen)]

    def snoei_beurten(self, bewaar: int = 500) -> int:
        """Houd het logboek eindig. Geeft terug hoeveel er weg zijn."""
        with self.conn:
            cursor = self.conn.execute(
                "DELETE FROM beurten WHERE id NOT IN "
                "(SELECT id FROM beurten ORDER BY id DESC LIMIT ?)", (bewaar,)
            )
        return cursor.rowcount

    # -- wat het model te zien krijgt --------------------------------------
    def context_for(self, vraag: str = "", limiet: int = 8) -> str:
        """
        Bouw het geheugenblok voor de systeemprompt.

        Alleen wat bij de vraag past plus de kern, in plaats van alles. Dat
        scheelt tokens en houdt het model bij de les.
        """
        gekozen: dict[int, Feit] = {}
        for feit in self.zoek(vraag, limiet=limiet) if vraag else []:
            gekozen[feit.id] = feit
        for feit in self.kern(limiet=max(0, limiet - len(gekozen))):
            gekozen.setdefault(feit.id, feit)

        if not gekozen and not vraag:
            # Zonder vraag en zonder kern: val terug op het meest recente.
            for feit in self.alle_feiten(limiet=limiet):
                gekozen.setdefault(feit.id, feit)

        delen: list[str] = []
        if gekozen:
            delen.append("Wat je weet:")
            delen += [f"- ({f.soort}) {f.inhoud}" for f in gekozen.values()]

        recent = self.recente_beurten()
        if recent:
            delen.append("\nEerder in dit gesprek:")
            delen += [f"- {b['rol']}: {b['inhoud']}" for b in recent]

        return "\n".join(delen) if delen else "Nog geen opgeslagen herinneringen."

    def samenvatting(self) -> str:
        """Leesbaar overzicht voor 'wat weet je over mij?'."""
        feiten = self.alle_feiten()
        if not feiten:
            return "Ik weet nog niets over je."
        regels = "\n".join(f"- {f.inhoud}" for f in feiten)
        return f"Dit is wat ik me van je herinner:\n{regels}"

    # -- onderhoud ---------------------------------------------------------
    def aantallen(self) -> dict[str, int]:
        return {
            "feiten": self.conn.execute("SELECT count(*) FROM feiten").fetchone()[0],
            "beurten": self.conn.execute("SELECT count(*) FROM beurten").fetchone()[0],
        }

    def close(self) -> None:
        self.conn.close()
