from enum import Enum

class Status(Enum):
    pending = 'pending'
    sent = 'sent'
    failed = 'failed'


class Role(Enum):
    user = 'user'
    assistant = 'assistant'