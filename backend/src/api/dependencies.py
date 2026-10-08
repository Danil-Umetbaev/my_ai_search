from typing import Annotated

from fastapi import Depends

from src.database import async_session_maker
from src.utils.db import DBManager
from src.ai.embeddings.qwen import QwenEmbeddingProvider
from src.ai.llm.qwen import QwenLLMProvider
from src.ai.reranking.cross_encoder import CrossEncoderRerankerProvider
from src.services.rag import RAGService
from src.services.chat import ChatService
from src.services.vector_search import VectorSearchService
async def get_db():
    async with DBManager(async_session_maker) as db:
        yield db


DBDep = Annotated[DBManager, Depends(get_db)]


embedding_provider = QwenEmbeddingProvider()

def get_embedding_provider():
    return embedding_provider

embeddingDep = Annotated[QwenEmbeddingProvider, Depends(get_embedding_provider)]

llm = QwenLLMProvider()

def get_llm_provider():
    return llm

llmDep = Annotated[QwenLLMProvider, Depends(get_llm_provider)]

reranker = CrossEncoderRerankerProvider()
def get_reranker_provider():
    return reranker

rerankerDep = Annotated[CrossEncoderRerankerProvider, Depends(get_reranker_provider)]


def get_rag_service(db: DBDep, embedding: embeddingDep, llm: llmDep, reranker: rerankerDep):
    vector_search = VectorSearchService(db, embedding)
    return RAGService(db, vector_search, llm, reranker)

rag_serviceDep = Annotated[RAGService, Depends(get_rag_service)]


def get_chat_service(db: DBDep, rag_service: rag_serviceDep):
    return ChatService(db, rag_service)

ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
