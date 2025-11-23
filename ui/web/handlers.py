from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from managers.agent_manager import AgentManager
from managers.google_services_manager import GoogleServicesManager
from managers.storage_manager import StorageManager
from utils import LogFunction


def get_create_event_form_defaults() -> tuple[datetime, datetime]:
    now = datetime.now()
    start_default = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    end_default = start_default + timedelta(hours=1)
    return start_default, end_default


async def create_calendar_event(
    google_services_manager: GoogleServicesManager,
    logger: LogFunction,
    access_token: str,
    summary: str,
    start_time: str,
    end_time: str,
    description: str,
    event_timezone: str,
):
    logger(f'Creating calendar event: "{summary}"', 'info')

    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)
    tz = ZoneInfo(event_timezone)

    event = await google_services_manager.create_calendar_event(
        access_token,
        summary,
        start_dt,
        end_dt,
        description,
        tz,
    )
    return event


async def list_calendar_events(
    google_services_manager: GoogleServicesManager,
    access_token: str,
    user_timezone: str,
):
    now = datetime.now(ZoneInfo(user_timezone))
    tz = ZoneInfo(user_timezone)
    events = await google_services_manager.list_upcoming_events(access_token, now, tz)
    return events


async def run_agent(
    agent_manager: AgentManager,
    storage_manager: StorageManager,
    google_sub: str,
    user_email: str,
    user_message: str,
):
    token_data = await storage_manager.get_user_token(google_sub)
    if not token_data:
        raise ValueError('User not authenticated')

    user_timezone = token_data.get('timezone', 'UTC')

    response = await agent_manager.run_agent(user_message, google_sub, user_email, user_timezone)
    return response
