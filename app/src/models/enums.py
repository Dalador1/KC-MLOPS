from enum import Enum


class UserRole(Enum):
    USER = "user"
    ADMIN = "admin"


class PredictionStatus(Enum):
    CREATED = "created"
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class EmailLabel(Enum):
    SPAM = "spam"
    HAM = "ham"
