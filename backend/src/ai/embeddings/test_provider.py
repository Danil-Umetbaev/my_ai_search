from src.ai.embeddings.qwen import QwenEmbeddingProvider
from sentence_transformers import util
provider = QwenEmbeddingProvider()


query = 'Как создать магазин в SetRetail10?'
query_embedding = provider.embed_query(
    query
)
documents = [
    "Для создания магазина необходимо настроить структуру торговой сети.",
    "Настройка кассового оборудования выполняется в параметрах магазина.",
    "Сотрудник может оформить отпуск через кадровую систему."
]
document_embeddings = provider.embed_document(documents)

print('Длина векторов:', len(query_embedding))
print('Count of documents', len(document_embeddings))
print('Len documents vector:', len(document_embeddings))
print(query_embedding[:5])

result = util.cos_sim(query_embedding, document_embeddings).tolist()


print('Меры близости для запроса Как создать магазин в SetRetail10?')
for i in range(len(result[0])):
    print(f'{result[0][i]} - {documents[i]}')