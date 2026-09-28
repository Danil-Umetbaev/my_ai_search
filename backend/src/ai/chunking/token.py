from src.ai.chunking.base import Chunker
from transformers import AutoTokenizer
class TokenChunker(Chunker):

    def __init__(self, model_name: str, chunk_size: int, chunk_overlap: int):
        if chunk_size <= 0:
            raise ValueError('Размер нужно иметь')
        if chunk_overlap < 0:
            raise ValueError('Размер нужно иметь')
        if chunk_size <= chunk_overlap:
            raise ValueError('chunk_overlap поменьше нужно сделать')

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

    def split(self, text: str) -> list[str]:
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        step = self.chunk_size - self.chunk_overlap
        result = []
        for i in range(0, len(tokens), step):
            result.append(self.tokenizer.decode(tokens[i: i + self.chunk_size], skip_special_tokens=True))
            if (i + self.chunk_size) >= len(tokens):
                break
        return result


