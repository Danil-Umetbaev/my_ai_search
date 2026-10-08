import asyncio

from src.utils.db import DBManager
from src.database import async_session_maker
from src.services.chat import ChatService
from src.services.rag import RAGService
from src.services.vector_search import VectorSearchService
from src.ai.embeddings.qwen import QwenEmbeddingProvider
from src.ai.llm.qwen import QwenLLMProvider
from src.ai.reranking.cross_encoder import CrossEncoderRerankerProvider

from src.schemas.chat import ChatRequest, ChatResponse
async def main():
    async with DBManager(async_session_maker) as db:

        embedding = QwenEmbeddingProvider()
        llm = QwenLLMProvider()
        reranker = CrossEncoderRerankerProvider()
        vector_search = VectorSearchService(db, embedding)
        rag_service = RAGService(db, vector_search, llm, reranker)

        chat_service = ChatService(db, rag_service)

        conversation = (await db.conversations.get_all())[0]

        message = 'Как оформить отпуск сотруднику?'
        chat_request = ChatRequest(conversation_id=conversation.id, message=message)
        chat_response = await chat_service.send_message(chat_request)

        print(f'MESSAGE_ID: {chat_response.message_id}')
        print(f'STATUS: {chat_response.status}')
        print(f'ANSWER: {chat_response.answer}')
        print(f'SOURCES: {chat_response.sources}')
        print(f'CONFIDENCE: {chat_response.confidence}')



if __name__ == '__main__':
    asyncio.run(main())