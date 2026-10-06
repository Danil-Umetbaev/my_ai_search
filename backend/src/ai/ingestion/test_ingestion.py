import asyncio

from src.ai.ingestion.confluence import ConfluenceKnowledgeSource
from src.ai.chunking.token import TokenChunker
from src.ai.embeddings.qwen import QwenEmbeddingProvider
from src.services.document_indexer import DocumentIndexerService
from src.utils.db import DBManager
from src.database import async_session_maker

async def main():

    async with DBManager(async_session_maker) as db:
        confluence = ConfluenceKnowledgeSource()
        chunker = TokenChunker('Qwen/Qwen3-Embedding-0.6B', 120, 30)
        provider = QwenEmbeddingProvider()
        indexer = DocumentIndexerService(db, chunker, provider)

        urls = [
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/1112867129/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/1237844110/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/1237713144/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/3540615169/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/3549298689/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/3540617651",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/442073283/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/1185644576",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/434504396/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/4259446955/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/1105429657/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/447709281/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/4064936067/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/4977655960/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/1161396377/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/3069280368/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/5019271278/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/3919413364",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/1237680404/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/1237680412",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/6736379916/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/4321476695/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/2780266540/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/3887039038/SetRetail10",
            "https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/6045171745/SetRetail10",
        ]
        for url in urls:
            print(f'url: {url}')
            document_add = await confluence.fetch(url)

            existing_document = await db.documents.get_one_or_none(source_url=document_add.source_url)
            if existing_document is not None:
                print('Документ уже загружен')
                continue
            saved_document = await db.documents.add(document_add)

            await indexer.index_document(saved_document)

            await db.commit()
            print('Готово')

if __name__ == '__main__':
    asyncio.run(main())
