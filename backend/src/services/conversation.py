from src.services.base import BaseService
from src.schemas.conversations import ConversationAddSchema
from src.schemas.messages import MessageSchema
from src.exceptions import NoResultFoundException, NoConversationFoundException

class ConversationService(BaseService):

    async def create_conversation(self):
        data = ConversationAddSchema()
        result = await self.db.conversations.add(data)
        await self.db.commit()
        return result

    async def get_messages(self, conversation_id: int) -> list[MessageSchema]:
        try:
            await self.db.conversations.get_one(id=conversation_id)
            return await self.db.messages.get_messages_by_conversation_id(conversation_id)
        except NoResultFoundException:
            raise NoConversationFoundException
