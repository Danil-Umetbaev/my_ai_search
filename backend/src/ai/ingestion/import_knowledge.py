"""Load or update the public SetRetail10 knowledge base."""
import argparse
import asyncio
from pathlib import Path


async def run(path: Path, limit: int | None) -> int:
    from src.ai.ingestion.confluence import ConfluenceKnowledgeSource
    from src.ai.chunking.token import TokenChunker
    from src.ai.embeddings.qwen import QwenEmbeddingProvider
    from src.services.document_indexer import DocumentIndexerService
    from src.utils.db import DBManager
    from src.database import async_session_maker

    urls = list(dict.fromkeys(line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                              if line.strip() and not line.startswith("#")))
    if limit is not None:
        urls = urls[:limit]
    source = ConfluenceKnowledgeSource()
    chunker = TokenChunker("Qwen/Qwen3-Embedding-0.6B", 120, 30)
    embeddings = QwenEmbeddingProvider()
    failed = 0
    async with DBManager(async_session_maker) as db:
        indexer = DocumentIndexerService(db, chunker, embeddings)
        for position, url in enumerate(urls, 1):
            try:
                document = await source.fetch(url)
                existing = await db.documents.get_one_or_none(source_url=document.source_url)
                if existing and existing.checksum == document.checksum:
                    print(f"[{position}/{len(urls)}] unchanged: {url}", flush=True)
                    continue
                if existing:
                    saved = await db.documents.update_by_id(document_id=existing.id, document=document)
                else:
                    saved = await db.documents.add(document)
                await indexer.index_document(saved)
                await db.commit()
                print(f"[{position}/{len(urls)}] indexed: {url}", flush=True)
            except Exception as error:
                await db.rollback()
                failed += 1
                print(f"[{position}/{len(urls)}] FAILED {url}: {type(error).__name__}: {error}", flush=True)
    print(f"Finished: {len(urls)} pages, {failed} failures. Rerun to retry failed pages.")
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--urls", type=Path, default=Path(__file__).resolve().parents[3] / "data/knowledge_urls.txt")
    parser.add_argument("--limit", type=int, help="Import only the first N pages for a smoke check")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    raise SystemExit(asyncio.run(run(args.urls, args.limit)))


if __name__ == "__main__":
    main()
