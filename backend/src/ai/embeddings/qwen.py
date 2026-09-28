
from src.ai.embeddings.base import EmbeddingProvider
from sentence_transformers import SentenceTransformer
class QwenEmbeddingProvider(EmbeddingProvider):
    MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"
    def __init__(self):
        self.model = SentenceTransformer(self.MODEL_NAME)

    def embed_query(self, message: str):
        embedding = self.model.encode(message, prompt_name='query')
        return embedding.tolist()
    def embed_document(self, documents: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(documents)
        return embeddings.tolist()