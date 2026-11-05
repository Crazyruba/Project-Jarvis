# data/

Wordt tijdens het draaien gevuld en staat niet in git:

| Wat | Door |
|---|---|
| `memory.db` | het blijvende geheugen (SQLite) |
| `voiceprint.npz` + `.json` | je stemafdrukken |
| `ecapa_model/` | het sprekerherkenningsmodel |
| `piper/` | de Nederlandse stem |
| `screenshots/` | wat de schermafbeelding-tool maakt |
| `laatste_groet.txt` | zodat hij je één keer per dag groet |

Opnieuw beginnen met de stemherkenning: verwijder `voiceprint.npz` en
`voiceprint.json`, of draai `python -m voice.enroll --reset`.
