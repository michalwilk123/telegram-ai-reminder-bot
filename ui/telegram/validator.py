from __future__ import annotations

from datetime import datetime
from typing import Callable

from apscheduler.triggers.cron import CronTrigger
from telegram import Update

from ui.base import BaseValidator, Errors, ValidationError, noop_on_errors


class TelegramValidationError(ValidationError):
    pass


class TelegramValidator(BaseValidator):
    def __init__(
        self, raises: bool | type[Exception], on_errors: Callable[[Errors], None] = noop_on_errors
    ):
        super().__init__(raises, on_errors)

    def has_message(self, update: Update) -> TelegramValidator:
        if not update.message:
            self._add_error('No message in update')
        return self


def parse_add_command_args(args: list[str]) -> dict[str, datetime | str]:
    text = ' '.join(args)
    if ' at ' not in text:
        raise TelegramValidationError(
            "Missing 'at' separator. Usage: /add [Title] at [YYYY-MM-DD HH:MM]"
        )

    summary, time_str = text.split(' at ', 1)

    if not summary or not summary.strip():
        raise TelegramValidationError('Summary is required')

    try:
        dt = datetime.strptime(time_str.strip(), '%Y-%m-%d %H:%M')
    except ValueError as e:
        raise TelegramValidationError(
            'Date: Invalid date format. Expected format: %Y-%m-%d %H:%M'
        ) from e

    return {
        'summary': summary.strip(),
        'datetime': dt,
    }


def parse_reminder_add_args(args: list[str]) -> dict[str, str]:
    if len(args) < 6:
        raise TelegramValidationError('Usage: /reminder_add [cron_expression] [message]')

    cron = ' '.join(args[:5])
    message = ' '.join(args[5:])

    try:
        CronTrigger.from_crontab(cron)
    except Exception as e:
        raise TelegramValidationError(f'Invalid cron expression: {str(e)}') from e

    if not message or not message.strip():
        raise TelegramValidationError('Message is required')

    return {
        'cron': cron,
        'message': message,
    }


def parse_reminder_del_args(args: list[str]) -> int:
    if not args:
        raise TelegramValidationError('Usage: /reminder_del [id]')

    try:
        reminder_id = int(args[0])
    except ValueError as e:
        raise TelegramValidationError('Invalid ID. ID must be a number.') from e

    return reminder_id
