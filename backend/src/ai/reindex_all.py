import asyncio

from sqlalchemy import text

from src.ai.embeddings.qwen import QwenEmbeddingProvider
from src.database import async_session_maker


BATCH_SIZE = 256


def vector_to_postgres(
    embedding: list[float],
) -> str:
    return "[" + ",".join(
        str(value)
        for value in embedding
    ) + "]"


async def main():

    print("=" * 100)
    print("ПЕРЕСЧЁТ EMBEDDINGS: TITLE + CHUNK")
    print("=" * 100)

    provider = QwenEmbeddingProvider()

    async with async_session_maker() as session:

        result = await session.execute(
            text(
                """
                SELECT
                    dc.id AS chunk_id,
                    dc.content AS content,
                    d.title AS title
                FROM document_chunks dc
                JOIN documents d
                    ON d.id = dc.document_id
                ORDER BY d.id, dc.chunk_index
                """
            )
        )

        chunks = result.mappings().all()

        total = len(chunks)

        print(f"Всего chunks: {total}")

        updated = 0

        for start in range(
            0,
            total,
            BATCH_SIZE,
        ):

            batch = chunks[
                start:start + BATCH_SIZE
            ]

            texts = [
                (
                    f"Название документа: "
                    f"{row['title'] or ''}\n"
                    f"{row['content']}"
                )
                for row in batch
            ]

            embeddings = (
                provider.embed_document(
                    texts
                )
            )

            params = [
                {
                    "chunk_id": row["chunk_id"],
                    "embedding": vector_to_postgres(
                        embedding
                    ),
                }
                for row, embedding
                in zip(batch, embeddings)
            ]

            await session.execute(
                text(
                    """
                    UPDATE document_chunks
                    SET embedding = CAST(
                        :embedding AS vector
                    )
                    WHERE id = :chunk_id
                    """
                ),
                params,
            )

            await session.commit()

            updated += len(batch)

            print(
                f"[{updated}/{total}] "
                f"готово"
            )

    print()
    print("=" * 100)
    print("ПЕРЕИНДЕКСАЦИЯ ЗАВЕРШЕНА")
    print("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())