import sqlite3


class LongTermMemory:
    """Blijvende feiten over de eigenaar (feiten, voorkeuren, projecten, doelen)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._create_table()

    def _create_table(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS long_term (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT,          -- fact | preference | project | goal
                content TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def add(self, memory_type: str, content: str):
        # Avoid storing exact duplicates
        existing = self.conn.execute(
            "SELECT 1 FROM long_term WHERE content = ? LIMIT 1",
            (content,),
        ).fetchone()
        if existing:
            return "Dat weet ik al."

        self.conn.execute(
            "INSERT INTO long_term (memory_type, content) VALUES (?, ?)",
            (memory_type, content),
        )
        self.conn.commit()
        return "Opgeslagen."

    def get_all(self, limit: int = 50):
        rows = self.conn.execute(
            """
            SELECT memory_type, content
            FROM long_term
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return rows

    def get_by_type(self, memory_type: str):
        rows = self.conn.execute(
            "SELECT content FROM long_term WHERE memory_type = ? ORDER BY created_at DESC",
            (memory_type,),
        ).fetchall()
        return [r[0] for r in rows]

    def clear(self):
        self.conn.execute("DELETE FROM long_term")
        self.conn.commit()