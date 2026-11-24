from uuid import UUID

from src.services.base import BaseService
from src.schemas.conversations import ConversationAddSchema
from src.schemas.messages import MessageSchema
from src.exceptions import NoResultFoundException, NoConversationFoundException


class ConversationService(BaseService):
    async def create_conversation(self, user=None):
        data = ConversationAddSchema()
        result = await self.db.conversations.add(data)
        if user is not None:
            await self.db.conversations.save_state(result.id, {"_chat_owner": user.id})
        await self.db.commit()
        return result

    async def accessible_state(self, conversation_id, user=None, *, for_update=False):
        try:
            state = await self.db.conversations.get_state(
                conversation_id, for_update=for_update
            )
        except NoResultFoundException as error:
            raise NoConversationFoundException from error
        owner = state.get("_chat_owner")
        if owner is not None and (user is None or user.id != owner):
            raise NoConversationFoundException
        return state

    async def get_messages(self, conversation_id: UUID, user=None) -> list[MessageSchema]:
        await self.accessible_state(conversation_id, user)
        return await self.db.messages.get_messages_by_conversation_id(conversation_id)
