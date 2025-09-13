from pydantic import BaseModel


class Config(BaseModel):
    imap_host: str
    imap_port: int = 993
    email_user: str
    email_pass: str  # WARNING: prefer app passwords or OAuth in production
    telegram_bot_token: str
    telegram_chat_id: str  # int or @channelusername
    poll_interval: int = 30  # seconds

