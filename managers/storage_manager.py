from typing import Any

from sqlalchemy import JSON, Integer, String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def rotate_messages(messages: list[dict[str, Any]], max_messages: int) -> list[dict[str, Any]]:
    if max_messages <= 0:
        raise ValueError('max_messages must be positive')

    if len(messages) <= max_messages:
        return messages

    return messages[-max_messages:]


class Base(DeclarativeBase):
    pass


class UserToken(Base):
    __tablename__ = 'user_tokens'

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    token_data: Mapped[dict[str, Any]] = mapped_column(JSON)


class Reminder(Base):
    __tablename__ = 'reminders'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String)
    cron: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(String)

    def to_dict(self) -> dict[str, Any]:
        return {'id': self.id, 'user_id': self.user_id, 'cron': self.cron, 'message': self.message}


class TelegramUserMapping(Base):
    __tablename__ = 'telegram_user_mappings'

    telegram_id: Mapped[str] = mapped_column(String, primary_key=True)
    google_sub: Mapped[str] = mapped_column(String)


class ConversationHistory(Base):
    __tablename__ = 'conversation_history'

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class StorageManager:
    def __init__(self, db_url: str):
        self.engine = create_async_engine(db_url)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def save_user_token(self, user_id: str, token_data: dict[str, Any]):
        async with self.async_session() as session:
            result = await session.execute(select(UserToken).where(UserToken.user_id == user_id))
            user_token = result.scalar_one_or_none()

            if user_token:
                user_token.token_data = token_data
            else:
                user_token = UserToken(user_id=user_id, token_data=token_data)
                session.add(user_token)

            await session.commit()

    async def get_user_token(self, user_id: str) -> dict[str, Any] | None:
        async with self.async_session() as session:
            result = await session.execute(select(UserToken).where(UserToken.user_id == user_id))
            user_token = result.scalar_one_or_none()
            return user_token.token_data if user_token else None

    async def delete_user_token(self, user_id: str) -> bool:
        async with self.async_session() as session:
            result = await session.execute(select(UserToken).where(UserToken.user_id == user_id))
            user_token = result.scalar_one_or_none()
            if user_token:
                await session.delete(user_token)
                await session.commit()
                return True
            return False

    async def add_reminder(self, user_id: str, cron: str, message: str) -> int:
        async with self.async_session() as session:
            reminder = Reminder(user_id=user_id, cron=cron, message=message)
            session.add(reminder)
            await session.commit()
            await session.refresh(reminder)
            return reminder.id

    async def get_reminders(self, user_id: str) -> list[dict[str, Any]]:
        async with self.async_session() as session:
            result = await session.execute(select(Reminder).where(Reminder.user_id == user_id))
            reminders = result.scalars().all()
            return [r.to_dict() for r in reminders]

    async def get_all_reminders(self) -> list[dict[str, Any]]:
        async with self.async_session() as session:
            result = await session.execute(select(Reminder))
            reminders = result.scalars().all()
            return [r.to_dict() for r in reminders]

    async def delete_reminder(self, reminder_id: int) -> bool:
        async with self.async_session() as session:
            result = await session.execute(select(Reminder).where(Reminder.id == reminder_id))
            reminder = result.scalar_one_or_none()
            if reminder:
                await session.delete(reminder)
                await session.commit()
                return True
            return False

    async def get_conversation_history(self, user_id: str) -> list[dict[str, Any]]:
        async with self.async_session() as session:
            result = await session.execute(
                select(ConversationHistory).where(ConversationHistory.user_id == user_id)
            )
            history = result.scalar_one_or_none()
            return history.messages if history else []

    async def save_conversation_history(
        self, user_id: str, messages: list[dict[str, Any]], max_messages: int
    ):
        if max_messages <= 0:
            raise ValueError('max_messages must be positive')

        rotated_messages = rotate_messages(messages, max_messages)

        async with self.async_session() as session:
            result = await session.execute(
                select(ConversationHistory).where(ConversationHistory.user_id == user_id)
            )
            history = result.scalar_one_or_none()

            if history:
                history.messages = rotated_messages
            else:
                history = ConversationHistory(user_id=user_id, messages=rotated_messages)
                session.add(history)

            await session.commit()

    async def save_telegram_user_mapping(self, telegram_id: str, google_sub: str):
        async with self.async_session() as session:
            result = await session.execute(
                select(TelegramUserMapping).where(TelegramUserMapping.telegram_id == telegram_id)
            )
            mapping = result.scalar_one_or_none()

            if mapping:
                mapping.google_sub = google_sub
            else:
                mapping = TelegramUserMapping(telegram_id=telegram_id, google_sub=google_sub)
                session.add(mapping)

            await session.commit()

    async def get_google_sub_for_telegram_id(self, telegram_id: str) -> str | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(TelegramUserMapping).where(TelegramUserMapping.telegram_id == telegram_id)
            )
            mapping = result.scalar_one_or_none()
            return mapping.google_sub if mapping else None

    async def get_telegram_id_for_google_sub(self, google_sub: str) -> str | None:
        async with self.async_session() as session:
            result = await session.execute(
                select(TelegramUserMapping).where(TelegramUserMapping.google_sub == google_sub)
            )
            mapping = result.scalar_one_or_none()
            return mapping.telegram_id if mapping else None

    async def close(self):
        await self.engine.dispose()
