from src.ai.chunking.base import Chunker
from transformers import AutoTokenizer
from bisect import bisect_left, bisect_right
import re
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
        offsets = self.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)['offset_mapping']
        if not offsets:
            return []
        starts = [start for start, _ in offsets]
        boundaries = [match.end() for match in re.finditer(r'\n+', text)]
        result = []
        start = 0
        while start < len(offsets):
            end = min(start + self.chunk_size, len(offsets))
            if end < len(offsets):
                boundary_index = bisect_right(boundaries, offsets[end - 1][1]) - 1
                if boundary_index >= 0:
                    candidate = bisect_left(starts, boundaries[boundary_index])
                    minimum_end = start + max(self.chunk_size // 2, self.chunk_overlap + 1)
                    if minimum_end <= candidate <= end:
                        end = candidate
            result.append(text[offsets[start][0]:offsets[end - 1][1]])
            if end == len(offsets):
                break
            start = max(start + 1, end - self.chunk_overlap)
        return result


