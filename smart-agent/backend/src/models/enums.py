from enum import Enum

class Status(Enum):
    pending = 'pending'
    sent = 'sent'
    failed = 'failed'


class Role(Enum):
    user = 'user'
    assistant = 'assistant'


class UserRole(Enum):
    admin = 'admin'
    kassir = 'kassir'
    it = 'it'