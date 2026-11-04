import os
import sqlite3

from memory.working_memory import WorkingMemory
from memory.short_term_memory import ShortTermMemory
from memory.long_term_memory import LongTermMemory
import config


class MemoryManager:
    """Coordinates working, short-term, and long-term memory."""

    def __init__(self, db_path: str = "memory/memory.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        # check_same_thread=False so it's safe for later voice threads
        self.conn = sqlite3.connect(db_path, check_same_thread=False)

        self.working = WorkingMemory()
        self.short = ShortTermMemory(self.conn)
        self.long = LongTermMemory(self.conn)

    # ---------- WRITE ----------
    def remember_fact(self, memory_type: str, content: str) -> str:
        """Sla iets blijvends over de eigenaar op."""
        valid = {"fact", "preference", "project", "goal"}
        if memory_type not in valid:
            memory_type = "fact"
        return self.long.add(memory_type, content)

    def log_interaction(self, role: str, content: str):
        """Leg een beurt vast in het kortetermijngeheugen."""
        self.short.add(role, content)

    # ---------- READ ----------
    def build_memory_context(self) -> str:
        """
        Build the text block injected into the system prompt so
        JARVIS de eigenaar elke beurt 'kent'.
        """
        parts = []

        long_mems = self.long.get_all()
        if long_mems:
            parts.append(f"Wat je over {config.OWNER_NAME} weet:")
            for mtype, content in long_mems:
                parts.append(f"- ({mtype}) {content}")

        recent = self.short.get_recent()
        if recent:
            parts.append("\nRecente interacties:")
            for role, content, _ in recent:
                parts.append(f"- {role}: {content}")

        if not parts:
            return f"Je hebt nog geen herinneringen over {config.OWNER_NAME} opgeslagen."

        return "\n".join(parts)

    def summary(self) -> str:
        """Human-readable dump for 'what do you know about me?'"""
        long_mems = self.long.get_all()
        if not long_mems:
            return "Ik weet nog niets over je."
        lines = [f"- {content}" for _, content in long_mems]
        return "Dit is wat ik me van je herinner:\n" + "\n".join(lines)

    def close(self):
        self.conn.close()