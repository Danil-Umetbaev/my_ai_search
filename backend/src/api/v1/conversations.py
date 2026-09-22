from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from src.schemas.messages import MessageSchema
from src.api.dependencies import DBDep
from src.schemas.conversations import ConversationSchema, ConversationAddSchema
from src.exceptions import NoResultFoundException
conversation_router = APIRouter(prefix='/conversations')


@conversation_router.post('')
async def add_conversation(db: DBDep) -> ConversationSchema:
    data = ConversationAddSchema()
    result = await db.conversations.add(data)
    await db.commit()
    return result


@conversation_router.get('/{conversation_id}/messages')
async def get_messages_by_conversation_id(
    db: DBDep,
    conversation_id: UUID

) -> list[MessageSchema]:
    try:
        await db.conversations.get_one(id=conversation_id)
        return await db.messages.get_messages_by_conversation_id(conversation_id)
    except NoResultFoundException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Нет такой беседы')
