from typing import Any, Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from utils import LogFunction


class ScheduleManager:
    def __init__(
        self,
        logger: LogFunction,
        on_start: Callable[[], Awaitable[list[dict[str, Any]]]] | None = None,
    ):
        self.logger = logger
        self.scheduler = AsyncIOScheduler()
        self.callback: Callable[[int, str], Awaitable[None]] | None = None
        self.on_start = on_start

    def set_callback(self, callback: Callable[[str, str], Awaitable[None]]):
        self.callback = callback

    async def _job_wrapper(self, user_id: str, message: str, cron: str) -> None:
        if self.callback:
            try:
                formatted_message = f"⏰ <b>Periodic Reminder</b>\n\n{message}\n\n🕐 <code>{cron}</code>"
                await self.callback(user_id, formatted_message)
            except Exception as e:
                self.logger(f'Error in reminder callback: {e}', 'error')
        else:
            self.logger(
                f'Reminder triggered but no callback set. User: {user_id}, Message: {message}',
                'warning',
            )

    def schedule_job(self, reminder_id: int, user_id: str, cron: str, message: str) -> None:
        try:
            trigger = CronTrigger.from_crontab(cron)
            self.scheduler.add_job(
                self._job_wrapper,
                trigger=trigger,
                args=[user_id, message, cron],
                id=str(reminder_id),
                replace_existing=True,
            )
            self.logger(f'Scheduled job {reminder_id} for user {user_id} with cron {cron}', 'info')
        except ValueError as e:
            self.logger(f'Failed to schedule job {reminder_id}: {e}', 'error')

    async def start(self):
        # Load reminders from callback and schedule them
        if self.on_start:
            try:
                reminders = await self.on_start()
                self.logger(f'Loading {len(reminders)} reminders from callback...', 'info')
                for reminder in reminders:
                    self.schedule_job(
                        reminder['id'], reminder['user_id'], reminder['cron'], reminder['message']
                    )
            except Exception as e:
                self.logger(f'Error loading initial reminders: {e}', 'error')

        if not self.scheduler.running:
            self.scheduler.start()
            self.logger('Scheduler started.', 'info')

    async def add_reminder(self, reminder_id: int, user_id: str, cron: str, message: str) -> None:
        # Validate cron first
        try:
            CronTrigger.from_crontab(cron)
        except ValueError as e:
            raise ValueError(f'Invalid cron expression: {e}') from e

        self.schedule_job(reminder_id, user_id, cron, message)

    async def delete_reminder(self, reminder_id: int) -> bool:
        job_id = str(reminder_id)
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            return True
        return False

    async def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()
