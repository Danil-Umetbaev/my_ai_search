import logging
from time import perf_counter

import torch
from sentence_transformers import CrossEncoder

from src.ai.reranking.base import RerankerProvider
from src.utils.retry import load_with_retry


logger = logging.getLogger(__name__)


class CrossEncoderRerankerProvider(RerankerProvider):
    MODEL_NAME = "BAAI/bge-reranker-v2-m3"

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.batch_size = 2 if self.device == "cuda" else 8

        self.model = load_with_retry(
            loader=self._load_model,
            name="BGE Reranker",
            attempts=3,
            delay=5,
        )

        logger.info(
            "Reranker ready | device=%s | dtype=%s | batch_size=%s",
            self.device,
            next(self.model.model.parameters()).dtype,
            self.batch_size,
        )

    def _load_model(self):
        if self.device == "cuda":
            torch.cuda.empty_cache()

        model = CrossEncoder(
            self.MODEL_NAME,
            device=self.device,
            model_kwargs={
                "torch_dtype": (
                    torch.float16
                    if self.device == "cuda"
                    else torch.float32
                ),
            },
        )

        model.model.eval()

        return model

    def rerank(
        self,
        query: str,
        documents: list[str],
    ) -> list[float]:
        if not documents:
            return []

        started = perf_counter()
        pairs = [(query, document) for document in documents]

        try:
            with torch.inference_mode():
                scores = self.model.predict(
                    pairs,
                    batch_size=self.batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )

            return [float(score) for score in scores]
        finally:
            if self.device == "cuda":
                torch.cuda.empty_cache()

            logger.info(
                "Reranker finished | device=%s | pairs=%s | duration=%.2fs",
                self.device,
                len(pairs),
                perf_counter() - started,
            )