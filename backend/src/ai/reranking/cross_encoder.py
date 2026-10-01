from src.ai.reranking.base import RerankerProvider
from sentence_transformers import CrossEncoder

class CrossEncoderRerankerProvider(RerankerProvider):

    MODEL_NAME = 'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'

    def __init__(self):
        self.model = CrossEncoder(self.MODEL_NAME)

    def rerank(self, query: str, documents: list[str]) -> list[float]:

        query_chunk_pairs = [(query, chunk) for chunk in documents]

        grade_pairs = self.model.predict(query_chunk_pairs)

        return list(map(float, grade_pairs))