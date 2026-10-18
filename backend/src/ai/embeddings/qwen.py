from sentence_transformers import SentenceTransformer

from src.ai.embeddings.base import EmbeddingProvider
from src.utils.retry import load_with_retry


class QwenEmbeddingProvider(EmbeddingProvider):

    MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"

    def __init__(self):
        self.device = "cuda"

        self.model = load_with_retry(
            loader=lambda: SentenceTransformer(
                self.MODEL_NAME,
                device=self.device
            ),
            name="Qwen3 Embedding",
            attempts=3,
            delay=5,
        )

    def embed_query(self, message: str):
        embedding = self.model.encode(
            message,
            prompt_name="query"
        )

        return embedding.tolist()

    def embed_document(
        self,
        documents: list[str]
    ) -> list[list[float]]:

        embeddings = self.model.encode(documents, batch_size=32, show_progress_bar=False)
        return embeddings.tolist()