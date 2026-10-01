import asyncio

from src.utils.db import DBManager
from src.schemas.documents import DocumentAddSchema
from src.schemas.document_chunks import DocumentChunkAddSchema
from src.database import async_session_maker
from src.services.document_indexer import DocumentIndexerService
from src.ai.chunking.token import TokenChunker
from src.ai.embeddings.qwen import QwenEmbeddingProvider
document = DocumentAddSchema(
    source_type='тест',
    source_url='test_url',
    title='test_title',
    content="""
            В утреннем свете город просыпался, окутанный свежестью и тишиной. Птицы наполняли воздух своими мелодичными трелями, а первые лучи солнца скользили по крышам домов, раскрашивая их в золотистые тона. Улицы медленно наполнялись людьми, спешащими по своим делам, но в этой суете всё равно чувствовалась особая гармония и умиротворение.
            Вдали, за горизонтом, виднелись величественные горы, чьи вершины терялись в облаках. Их снежные шапки сверкали на солнце, словно бриллианты, а подножия утопали в зелёных лесах. Воздух был чистым и прозрачным, наполненным ароматами цветущих растений и свежестью горных родников. Каждый, кто смотрел на эту картину, чувствовал прилив сил и вдохновения, желание жить и наслаждаться каждым мгновением.
            """,
    checksum='test_checksum'
)

async def main():
    async with DBManager(async_session_maker) as db:
        document_schema = await db.documents.add(document)
        chunker = TokenChunker("Qwen/Qwen3-Embedding-0.6B", 20, 10)
        embadding = QwenEmbeddingProvider()
        await DocumentIndexerService(db, chunker, embadding).index_document(document_schema)

if __name__ == '__main__':
    asyncio.run(main())