from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic_ai import Agent, FunctionToolset, ModelMessagesTypeAdapter, RunContext
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from protocols import AgentServices
from utils import LogFunction, get_current_datetime


@dataclass
class AgentDeps:
    user_id: str
    user_email: str
    user_timezone: str
    services: AgentServices


STATIC_INSTRUCTIONS = (
    'You are a helpful and friendly AI assistant that helps users manage reminders and calendar events.\n\n'
    'Be conversational and natural - respond to greetings, small talk, and questions naturally. '
    'When users want to set reminders or calendar events, help them by:\n'
    '- Asking clarifying questions if important details are missing (time, date, description, etc.)\n'
    '- Making reasonable assumptions for minor details when appropriate\n'
    '- For RECURRING/REPEATING events (daily, weekly, monthly, etc.), use the save_reminder tool with cron syntax\n'
    '- For ONE-TIME events, use the save_to_google_calendar tool to create a Google Calendar event\n\n'
    'IMPORTANT - Timezone Handling:\n'
    '- If the user timezone is "UTC" (default), infer the actual timezone from language, date (winter/summer time) and context:\n'
    '  * Polish language -> Europe/Warsaw (UTC+1/+2)\n'
    '  * German language -> Europe/Berlin (UTC+1/+2)\n'
    '- Use the inferred timezone for all time-related calculations and event scheduling\n'
    '- When user mentions a specific time, interpret it in their inferred timezone\n\n'
    "Always respond in the same language as the user's current message."
)


def add_context_info(ctx: RunContext[AgentDeps]) -> str:
    user_tz = ZoneInfo(ctx.deps.user_timezone)
    now = datetime.now(user_tz)
    current_datetime = now.strftime('%Y-%m-%d %H:%M')
    return f'Current datetime: {current_datetime}\nUser timezone: {ctx.deps.user_timezone}\nUser email: {ctx.deps.user_email}'


async def save_reminder(ctx: RunContext[AgentDeps], cron: str, message: str) -> str:
    reminder_id = await ctx.deps.services.add_reminder(ctx.deps.user_id, cron, message)
    return f'Reminder saved with ID: {reminder_id}'


async def save_to_google_calendar(
    ctx: RunContext[AgentDeps],
    event_name: str,
    event_datetime: str,
    description: str,
    duration_minutes: int,
) -> str:
    try:
        start_dt = datetime.fromisoformat(event_datetime)
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        event_timezone = ZoneInfo(ctx.deps.user_timezone)
    except ValueError:
        return 'Invalid date format. Please use ISO format.'

    result = await ctx.deps.services.create_calendar_event(
        ctx.deps.user_id,
        event_name,
        start_dt,
        end_dt,
        description,
        event_timezone,
    )

    if isinstance(result, str):
        return result

    html_link = result.get('htmlLink', 'N/A')
    return (
        f"Event '{event_name}' has been added to your Google Calendar for {event_datetime} "
        f'(duration: {duration_minutes} minutes). Link: {html_link}'
    )


global_function_toolset = FunctionToolset(
    tools=[get_current_datetime, save_reminder, save_to_google_calendar]
)


def convert_to_model_messages(messages: list[dict[str, Any]]) -> list[ModelMessage]:
    return ModelMessagesTypeAdapter.validate_python(messages)


def convert_from_model_messages(messages: list[ModelMessage]) -> list[dict[str, Any]]:
    return ModelMessagesTypeAdapter.dump_python(messages, mode='json')


class AgentManager:
    def __init__(self, google_api_key: str, services: AgentServices, logger: LogFunction):
        self.services = services
        self.logger = logger
        provider = GoogleProvider(api_key=google_api_key)
        model = GoogleModel('models/gemini-flash-latest', provider=provider)

        self.agent = Agent(
            model,
            deps_type=AgentDeps,
            instructions=STATIC_INSTRUCTIONS,
            toolsets=[global_function_toolset],
        )

        self.agent.instructions(add_context_info)

    async def run_agent(
        self,
        user_message: str,
        user_id: str,
        user_email: str,
        user_timezone: str,
    ) -> str:
        deps = AgentDeps(
            user_id=user_id,
            user_email=user_email,
            user_timezone=user_timezone,
            services=self.services,
        )

        history_dicts = await self.services.get_conversation_history(user_id)
        message_history = convert_to_model_messages(history_dicts)

        result = await self.agent.run(user_message, deps=deps, message_history=message_history)

        all_messages = result.all_messages()
        history_to_save = convert_from_model_messages(all_messages)
        await self.services.save_conversation_history(user_id, history_to_save, max_messages=10)

        return result.output
