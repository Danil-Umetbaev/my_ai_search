from fastapi import APIRouter
from src.api.dependencies import DBDep
from src.schemas.conversations import ConversationSchema, ConversationAddSchema
conversation_router = APIRouter(prefix='/conversations')


@conversation_router.post('')
async def add_conversation(db: DBDep) -> ConversationSchema:
    data = ConversationAddSchema()
    result = await db.conversations.add(data)
    await db.commit()
    return result
