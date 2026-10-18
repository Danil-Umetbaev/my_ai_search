from sentence_transformers import CrossEncoder

from src.ai.reranking.base import RerankerProvider
from src.utils.retry import load_with_retry


class CrossEncoderRerankerProvider(
    RerankerProvider
):

    MODEL_NAME = "BAAI/bge-reranker-v2-m3"

    def __init__(self):
        self.device = "cpu"

        self.model = load_with_retry(
            loader=lambda: CrossEncoder(
                self.MODEL_NAME,
                device=self.device
            ),
            name="BGE Reranker",
            attempts=3,
            delay=5,
        )

    def rerank(
        self,
        query: str,
        documents: list[str]
    ) -> list[float]:

        query_chunk_pairs = [
            (query, chunk)
            for chunk in documents
        ]

        grade_pairs = self.model.predict(query_chunk_pairs)

        return list(map(float, grade_pairs))