from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from managers.adapters import AiAgentAdapter
from managers.agent_manager import AgentManager
from managers.config_manager import config_manager
from managers.google_services_manager import GoogleServicesManager
from managers.schedule_manager import ScheduleManager
from managers.storage_manager import StorageManager
from ui.telegram.handlers import (
    handle_add,
    handle_confirmation_callback,
    handle_list,
    handle_logout,
    handle_menu,
    handle_message,
    handle_reminder_add,
    handle_reminder_del,
    handle_reminders,
    handle_start,
)
from utils import LogFunction


class TelegramAgentAdapter(AiAgentAdapter):
    def __init__(
        self,
        storage_manager: StorageManager,
        schedule_manager: ScheduleManager,
        google_services_manager: GoogleServicesManager,
        logger: LogFunction,
        send_message_callback,
    ):
        super().__init__(storage_manager, schedule_manager, google_services_manager, logger)
        self.send_message_callback = send_message_callback

    async def create_calendar_event(
        self,
        user_id: str,
        event_name: str,
        start_dt: datetime,
        end_dt: datetime,
        description: str,
        event_timezone: ZoneInfo,
    ):
        self.logger(
            f'TelegramAgentAdapter: Creating event for user {user_id}: "{event_name}"', 'info'
        )

        # Get the Telegram ID from the Google sub (user_id)
        telegram_id = await self.storage_manager.get_telegram_id_for_google_sub(user_id)
        if not telegram_id:
            self.logger(
                f'TelegramAgentAdapter: No Telegram ID found for Google sub {user_id}', 'error'
            )
            return 'Failed to send confirmation: Telegram mapping not found.'

        event_data = {
            'user_id': user_id,
            'event_name': event_name,
            'start_dt': start_dt,
            'end_dt': end_dt,
            'description': description,
            'event_timezone': event_timezone,
        }

        message = (
            f'📅 <b>Confirm Event Creation</b>\n\n'
            f'📌 <b>Title:</b> {event_name}\n'
            f'🕐 <b>Start:</b> {start_dt}\n'
            f'🕐 <b>End:</b> {end_dt}\n'
            f'📝 <b>Description:</b> {description}'
        )

        keyboard = [
            [
                InlineKeyboardButton('✅ Confirm', callback_data='confirm_event'),
                InlineKeyboardButton('❌ Cancel', callback_data='cancel_event'),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await self.send_message_callback(telegram_id, message, reply_markup, event_data, 'HTML')

        return "✨ I've prepared your event! Please check the confirmation buttons above."


def create_telegram_agent_adapter_and_manager(
    storage_manager: StorageManager,
    schedule_manager: ScheduleManager,
    google_services_manager: GoogleServicesManager,
    bot_application: Application,
    logger: LogFunction,
    google_api_key: str,
):
    pending_events = {}

    async def send_message_with_confirmation(
        user_id: int, message: str, reply_markup, event_data: dict, parse_mode: str = None
    ):
        pending_events[user_id] = event_data
        await bot_application.bot.send_message(
            chat_id=user_id, text=message, reply_markup=reply_markup, parse_mode=parse_mode
        )

    telegram_adapter = TelegramAgentAdapter(
        storage_manager,
        schedule_manager,
        google_services_manager,
        logger,
        send_message_with_confirmation,
    )

    agent_manager = AgentManager(google_api_key, services=telegram_adapter, logger=logger)

    return agent_manager, pending_events


def create_bot_application() -> Application:
    return Application.builder().token(config_manager.telegram_bot_token).build()


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler('start', handle_start))
    application.add_handler(CommandHandler('menu', handle_menu))
    application.add_handler(CommandHandler('events', handle_list))
    application.add_handler(CommandHandler('newevent', handle_add))

    application.add_handler(CommandHandler('newreminder', handle_reminder_add))
    application.add_handler(CommandHandler('myreminders', handle_reminders))
    application.add_handler(CommandHandler('deletereminder', handle_reminder_del))

    application.add_handler(CommandHandler('logout', handle_logout))

    application.add_handler(
        CallbackQueryHandler(handle_confirmation_callback, pattern='^(confirm_event|cancel_event)$')
    )

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


async def setup_bot_commands(bot_application: Application) -> None:
    commands = [
        BotCommand('start', '🏠 Start the bot and login'),
        BotCommand('menu', '📋 Show available commands'),
        BotCommand('events', '📅 View upcoming calendar events'),
        BotCommand('newevent', '➕ Create a new calendar event'),
        BotCommand('myreminders', '⏰ View all periodic reminders'),
        BotCommand('newreminder', '➕ Create a new periodic reminder'),
        BotCommand('deletereminder', '🗑️ Delete a periodic reminder'),
        BotCommand('logout', '👋 Logout from Google'),
    ]
    await bot_application.bot.set_my_commands(commands)


async def start_telegram_bot(
    bot_application: Application,
    storage_manager: StorageManager,
    schedule_manager: ScheduleManager,
    google_services_manager: GoogleServicesManager,
    logger: LogFunction,
    google_api_key: str,
) -> None:
    logger('Starting Telegram Bot', 'info')

    await bot_application.initialize()
    await bot_application.start()

    await setup_bot_commands(bot_application)

    agent_manager, pending_events = create_telegram_agent_adapter_and_manager(
        storage_manager,
        schedule_manager,
        google_services_manager,
        bot_application,
        logger,
        google_api_key,
    )

    bot_application.bot_data['agent_manager'] = agent_manager
    bot_application.bot_data['pending_events'] = pending_events

    async def notifier(user_id: str, message: str):
        try:
            telegram_id_str = user_id
            
            if len(user_id) > 15:
                telegram_id_str = await storage_manager.get_telegram_id_for_google_sub(user_id)
                if not telegram_id_str:
                    logger(f'Failed to find telegram_id for user {user_id}', 'warning')
                    telegram_id_str = user_id
            
            await bot_application.bot.send_message(
                chat_id=telegram_id_str,
                text=message,
                parse_mode='HTML'
            )
        except Exception as exc:
            logger(f'Failed to send reminder to {user_id}: {exc}', 'error')

    schedule_manager.set_callback(notifier)
    schedule_manager.on_start = storage_manager.get_all_reminders
    await schedule_manager.start()

    await bot_application.updater.start_polling()

    bot_info = await bot_application.bot.get_me()
    logger(f'Bot username: {bot_info.username}', 'info')


async def stop_telegram_bot(
    bot_application: Application,
    schedule_manager: ScheduleManager,
    logger: LogFunction,
) -> None:
    logger('Stopping Telegram Bot', 'info')
    await bot_application.updater.stop()
    await bot_application.stop()
    await bot_application.shutdown()
    await schedule_manager.stop()
