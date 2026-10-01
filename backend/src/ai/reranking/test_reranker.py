from src.ai.reranking.cross_encoder import CrossEncoderRerankerProvider

query = "Что находилось вдали за горизонтом?"
documents = [
    "Вдали за горизонтом виднелись величественные горы.",
    "Воздух был чистым и прозрачным.",
    "Работник оформил отпуск в кадровой системе."
]
reranker = CrossEncoderRerankerProvider()

result = reranker.rerank(query, documents)

for document, rank in zip(documents, result):
    print(f'rank = {rank}, document = {document}')