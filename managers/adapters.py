from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from managers.google_services_manager import GoogleServicesManager
from managers.schedule_manager import ScheduleManager
from managers.storage_manager import StorageManager
from utils import LogFunction


class AiAgentAdapter:
    def __init__(
        self,
        storage_manager: StorageManager,
        schedule_manager: ScheduleManager,
        google_services_manager: GoogleServicesManager,
        logger: LogFunction,
    ):
        self.storage_manager = storage_manager
        self.schedule_manager = schedule_manager
        self.google_services_manager = google_services_manager
        self.logger = logger

    async def add_reminder(self, user_id: str, cron: str, message: str) -> int:
        self.logger(
            f'AiAgentAdapter: Adding reminder for user {user_id}: "{message}" with cron "{cron}"',
            'info',
        )
        reminder_id = await self.storage_manager.add_reminder(user_id, cron, message)
        await self.schedule_manager.add_reminder(reminder_id, user_id, cron, message)
        self.logger(f'AiAgentAdapter: Reminder {reminder_id} added for user {user_id}', 'debug')
        return reminder_id

    async def create_calendar_event(
        self,
        user_id: str,
        event_name: str,
        start_dt: datetime,
        end_dt: datetime,
        description: str,
        event_timezone: ZoneInfo,
    ) -> dict[str, Any] | str:
        self.logger(f'AiAgentAdapter: Creating event for user {user_id}: "{event_name}"', 'info')

        token_data = await self.storage_manager.get_user_token(user_id)
        if not token_data:
            self.logger(f'AiAgentAdapter: User token not found for user {user_id}', 'error')
            return 'Failed to create event: User not authenticated.'

        access_token = token_data.get('access_token')
        if not access_token:
            self.logger(f'AiAgentAdapter: Access token not found for user {user_id}', 'error')
            return 'Failed to create event: Access token not found.'

        result = await self.google_services_manager.create_calendar_event(
            access_token,
            event_name,
            start_dt,
            end_dt,
            description,
            event_timezone,
        )
        self.logger(f'AiAgentAdapter: Event created for user {user_id}', 'info')
        return result

    async def get_conversation_history(self, user_id: str) -> list[dict[str, Any]]:
        return await self.storage_manager.get_conversation_history(user_id)

    async def save_conversation_history(
        self, user_id: str, messages: list[dict[str, Any]], max_messages: int
    ):
        await self.storage_manager.save_conversation_history(user_id, messages, max_messages)
