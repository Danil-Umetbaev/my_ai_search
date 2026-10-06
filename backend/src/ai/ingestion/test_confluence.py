import asyncio

import httpx
from src.ai.ingestion.confluence import ConfluenceKnowledgeSource

confluence = ConfluenceKnowledgeSource()
url = 'https://crystals.atlassian.net/wiki/spaces/SR10SUPPORT/pages/1112867129/SetRetail10'

async def main():
    document_add = await confluence.fetch(url)
    print(document_add.title)
    print(document_add.content)
    print(document_add.checksum)

if __name__ == '__main__':
    asyncio.run(main())
