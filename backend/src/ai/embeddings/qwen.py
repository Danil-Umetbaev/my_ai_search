import logging

from sentence_transformers import SentenceTransformer

from src.ai.embeddings.base import EmbeddingProvider
from src.utils.retry import load_with_retry


logger = logging.getLogger(__name__)


class QwenEmbeddingProvider(EmbeddingProvider):
    MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"

    def __init__(self):
        self.device = "cpu"

        self.model = load_with_retry(
            loader=lambda: SentenceTransformer(
                self.MODEL_NAME,
                device=self.device,
            ),
            name="Qwen3 Embedding",
            attempts=3,
            delay=5,
        )

        logger.info(
            "Embedding ready | device=%s",
            self.device,
        )

    def embed_query(self, message: str) -> list[float]:
        embedding = self.model.encode(
            message,
            prompt_name="query",
            show_progress_bar=False,
        )

        return embedding.tolist()

    def embed_document(
        self,
        documents: list[str],
    ) -> list[list[float]]:
        if not documents:
            return []

        embeddings = self.model.encode(
            documents,
            batch_size=8,
            show_progress_bar=False,
        )

        return embeddings.tolist()