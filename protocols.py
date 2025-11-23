from datetime import datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo


class AgentServices(Protocol):
    async def add_reminder(self, user_id: str, cron: str, message: str) -> int: ...

    async def create_calendar_event(
        self,
        user_id: str,
        event_name: str,
        start_dt: datetime,
        end_dt: datetime,
        description: str,
        event_timezone: ZoneInfo,
    ) -> dict[str, Any] | str: ...

    async def get_conversation_history(self, user_id: str) -> list[dict[str, Any]]: ...

    async def save_conversation_history(self, user_id: str, messages: list[dict[str, Any]]): ...
