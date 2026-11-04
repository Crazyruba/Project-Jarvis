"""
VoiceprintStore — ChromaDB-opslag voor de stemafdrukken van de eigenaar.

Stores multiple 192-dim ECAPA speaker embeddings in a cosine-space collection.
Verification averages similarity across the nearest stored samples, which gives
een stabieler oordeel dan één enkele match.
"""

import numpy as np
import chromadb
import config


class VoiceprintStore:
    """ChromaDB-opslag voor ECAPA-stemvectoren (cosinusgelijkenis)."""

    def __init__(self):
        self.client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
        # 🔑 cosine space is what enables cosine-similarity search
        self.collection = self.client.get_or_create_collection(
            name=config.VOICEPRINT_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    # ---------- helpers ----------
    @staticmethod
    def _to_float_list(embedding):
        """Convert any embedding (numpy array / list / np.float32) to native floats."""
        return np.asarray(embedding, dtype=float).flatten().tolist()

    # ---------- state ----------
    def is_enrolled(self) -> bool:
        """True if at least one voiceprint is stored."""
        return self.collection.count() > 0

    def count(self) -> int:
        """Number of stored voiceprint samples."""
        return self.collection.count()

    # ---------- write ----------
    def add_voiceprint(self, embedding, sample_id: str):
        """Store one voiceprint vector (converted to native Python floats)."""
        self.collection.add(
            embeddings=[self._to_float_list(embedding)],
            ids=[sample_id],
            metadatas=[{"owner": config.OWNER_NAME.lower()}],
        )

    # ---------- verify ----------
    def verify(self, embedding, top_k: int = 5):
        """
        Compare an incoming voice embedding against stored voiceprints.

        Averages cosine similarity across the nearest `top_k` stored samples
        for a stable score.  Returns (avg_similarity, owner).

        cosine_similarity = 1 - cosine_distance
        """
        if not self.is_enrolled():
            return 0.0, None

        n = min(top_k, self.collection.count())
        results = self.collection.query(
            query_embeddings=[self._to_float_list(embedding)],
            n_results=n,
        )

        distances = results["distances"][0]
        metadatas = results["metadatas"][0]

        # Convert each distance to similarity, then average
        sims = [1.0 - d for d in distances]
        avg_sim = sum(sims) / len(sims) if sims else 0.0

        # Alle opgeslagen afdrukken zijn van de eigenaar; neem de bovenste.
        owner = metadatas[0].get("owner") if metadatas else None

        return avg_sim, owner

    # ---------- maintenance ----------
    def reset(self):
        """Wipe all voiceprints (used for re-enrollment)."""
        self.client.delete_collection(config.VOICEPRINT_COLLECTION)
        self.collection = self.client.get_or_create_collection(
            name=config.VOICEPRINT_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )