from src.services.base import BaseService
from src.schemas.messages import MessageAddSchema, MessageAddRequestSchema, MessageSchema
from src.exceptions import NoResultFoundException, NoConversationFoundException
from src.models.enums import Role

class ChatService(BaseService):

    async def send_message(
            self,
            message: MessageAddRequestSchema
    ) -> MessageSchema:
        try:
            await self.db.conversations.get_one(id=message.conversation_id)
        except NoResultFoundException:
            raise NoConversationFoundException
        new_message = MessageAddSchema(**message.model_dump(), role=Role.user)
        data = await self.db.messages.add(new_message)
        await self.db.commit()
        return data

