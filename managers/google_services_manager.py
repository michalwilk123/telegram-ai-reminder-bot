from datetime import datetime, timedelta, timezone
from typing import NotRequired, TypedDict
from zoneinfo import ZoneInfo

import httpx

from utils import LogFunction, pick


class EventDateTime(TypedDict):
    dateTime: str
    timeZone: str


class CalendarEvent(TypedDict):
    id: str
    summary: str
    description: NotRequired[str]
    start: EventDateTime
    end: EventDateTime
    status: str


class GoogleCalendarAuthError(Exception):
    pass


class GoogleCalendarAPIError(Exception):
    pass


class GoogleServicesManager:
    GOOGLE_CALENDAR_API_BASE = 'https://www.googleapis.com/calendar/v3/calendars/primary/events'

    def __init__(self, http_client: httpx.AsyncClient, logger: LogFunction):
        self.http_client = http_client
        self.logger = logger

    async def list_upcoming_events(
        self, access_token: str, now: datetime, user_timezone: ZoneInfo
    ) -> list[CalendarEvent]:
        now_utc = now.astimezone(timezone.utc)
        time_min = now_utc.isoformat()
        time_max = (now_utc + timedelta(days=7)).isoformat()

        self.logger(
            f'GoogleServicesManager: Fetching events from {time_min} to {time_max}', 'debug'
        )

        response = await self.http_client.get(
            self.GOOGLE_CALENDAR_API_BASE,
            headers={'Authorization': f'Bearer {access_token}'},
            params={
                'timeMin': time_min,
                'timeMax': time_max,
                'singleEvents': 'true',
                'orderBy': 'startTime',
            },
        )

        self.logger(
            f'GoogleServicesManager: Calendar API response status: {response.status_code}', 'debug'
        )

        if response.status_code == 401:
            self.logger(
                'GoogleServicesManager: Auth error (401) fetching events. Token might be invalid despite local checks.',
                'warning',
            )
            raise GoogleCalendarAuthError(
                f'Authentication failed (401). Please re-login. Error: {response.text}'
            )

        if response.status_code != 200:
            self.logger(
                f'GoogleServicesManager: Error fetching events: {response.status_code} - {response.text}',
                'error',
            )
            raise GoogleCalendarAPIError(f'Error fetching events: {response.text}')

        data = response.json()
        items = data.get('items', [])
        event_count = len(items)
        self.logger(f'GoogleServicesManager: Successfully fetched {event_count} events', 'info')
        # Security: Do not log full event structure in debug mode as it may contain sensitive data
        # Log only event IDs and summaries for debugging
        if items:
            event_summaries = [item.get('summary', 'N/A') for item in items[:5]]  # Limit to first 5
            self.logger(f'GoogleServicesManager: Event summaries: {event_summaries}', 'debug')

        # Transform raw events to only include essential fields
        calendar_events: list[CalendarEvent] = [
            pick(item, ['id', 'summary', 'description', 'start', 'end', 'status']) for item in items
        ]

        return calendar_events

    async def create_calendar_event(
        self,
        access_token: str,
        summary: str,
        start_time: datetime,
        end_time: datetime,
        description: str | None,
        event_timezone: ZoneInfo,
    ) -> CalendarEvent:
        start_str = start_time.isoformat()
        end_str = end_time.isoformat()
        timezone_str = str(event_timezone)

        self.logger(
            f'GoogleServicesManager: Creating event "{summary}" from {start_str} to {end_str}',
            'info',
        )

        event_body = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_str, 'timeZone': timezone_str},
            'end': {'dateTime': end_str, 'timeZone': timezone_str},
        }
        response = await self.http_client.post(
            self.GOOGLE_CALENDAR_API_BASE,
            headers={'Authorization': f'Bearer {access_token}'},
            json=event_body,
        )

        self.logger(
            f'GoogleServicesManager: Calendar API response status: {response.status_code}', 'debug'
        )

        if response.status_code not in (200, 201):
            self.logger(
                f'GoogleServicesManager: Error creating event: {response.status_code} - {response.text}',
                'error',
            )
            raise GoogleCalendarAPIError(f'Error creating event: {response.text}')

        result = response.json()
        self.logger(
            f'GoogleServicesManager: Event created successfully with ID: {result.get("id")}', 'info'
        )

        # Transform raw event to only include essential fields
        calendar_event: CalendarEvent = pick(
            result, ['id', 'summary', 'description', 'start', 'end', 'status']
        )

        return calendar_event
