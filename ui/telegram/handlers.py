from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from managers.agent_manager import AgentManager
from managers.config_manager import config_manager
from managers.google_services_manager import GoogleServicesManager
from managers.schedule_manager import ScheduleManager
from managers.storage_manager import StorageManager
from ui.telegram import user_tokens
from ui.telegram.validator import (
    parse_add_command_args,
    parse_reminder_add_args,
    parse_reminder_del_args,
)
from utils import LogFunction


async def get_user_id_for_telegram(storage_manager: StorageManager, telegram_id: int) -> str | None:
    """Get the Google sub (user_id) for a given Telegram ID"""
    google_sub = await storage_manager.get_google_sub_for_telegram_id(str(telegram_id))
    return google_sub


def build_login_url(base_url: str, telegram_id: int) -> str:
    return f'{base_url}/login?telegram_id={telegram_id}&from_telegram=true'


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    
    storage_manager: StorageManager = context.bot_data['storage_manager']
    logger: LogFunction = context.bot_data['logger']

    user_id = update.effective_user.id
    logger(f'User {user_id} started the bot', 'info')

    google_sub = await get_user_id_for_telegram(storage_manager, user_id)
    if google_sub:
        token_data = await storage_manager.get_user_token(google_sub)
        if token_data:
            welcome_msg = (
                "✨ <b>Welcome back!</b>\n\n"
                "You're already authenticated! Here's what you can do:\n\n"
                "📅 <b>Calendar Events:</b>\n"
                "• Chat with me naturally to create events\n"
                "• /events - View your upcoming events\n"
                "• /newevent - Quick event creation\n\n"
                "⏰ <b>Periodic Reminders:</b>\n"
                "• /newreminder - Create a recurring reminder\n"
                "• /myreminders - View all your reminders\n"
                "• /deletereminder - Remove a reminder\n\n"
                "💬 Just send me a message to get started!"
            )
            await update.message.reply_text(welcome_msg, parse_mode='HTML')
            return

    parsed = urlparse(config_manager.redirect_url)
    base_url = f'{parsed.scheme}://{parsed.netloc}'
    login_url = build_login_url(base_url, user_id)
    
    keyboard = [[InlineKeyboardButton('🔐 Login with Google Calendar', url=login_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_msg = (
        "👋 <b>Welcome to your Personal Calendar Assistant!</b>\n\n"
        "I can help you manage your Google Calendar events and set up recurring reminders.\n\n"
        "To get started, please authenticate with your Google account:"
    )
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='HTML')


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    
    storage_manager: StorageManager = context.bot_data['storage_manager']

    user_id = update.effective_user.id

    google_sub = await get_user_id_for_telegram(storage_manager, user_id)
    if not google_sub:
        await update.message.reply_text(
            "🔐 <b>Authentication Required</b>\n\n"
            "Please authenticate first using /start",
            parse_mode='HTML'
        )
        return
    
    token_data = await storage_manager.get_user_token(google_sub)
    if not token_data:
        await update.message.reply_text(
            "🔐 <b>Authentication Required</b>\n\n"
            "Please authenticate first using /start",
            parse_mode='HTML'
        )
        return

    menu_msg = (
        "📋 <b>Main Menu</b>\n\n"
        "Here's what you can do:\n\n"
        "📅 <b>Calendar Events:</b>\n"
        "• Chat with me naturally to create events\n"
        "• /events - View your upcoming events\n"
        "• /newevent - Quick event creation\n\n"
        "⏰ <b>Periodic Reminders:</b>\n"
        "• /newreminder - Create a recurring reminder\n"
        "• /myreminders - View all your reminders\n"
        "• /deletereminder - Remove a reminder\n\n"
        "🔧 <b>Other Commands:</b>\n"
        "• /logout - Logout from Google\n"
        "• /menu - Show this menu\n\n"
        "💬 Just send me a message to get started!"
    )
    await update.message.reply_text(menu_msg, parse_mode='HTML')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user or not update.message.text:
        return
    
    agent_manager: AgentManager = context.bot_data['agent_manager']
    storage_manager: StorageManager = context.bot_data['storage_manager']
    logger: LogFunction = context.bot_data['logger']

    telegram_id = update.effective_user.id
    user_message = update.message.text

    logger(f'User {telegram_id} sent message: {user_message}', 'info')
    
    google_sub = await get_user_id_for_telegram(storage_manager, telegram_id)
    if not google_sub:
        await update.message.reply_text(
            "🔐 <b>Authentication Required</b>\n\n"
            "Please authenticate first using /start",
            parse_mode='HTML'
        )
        return
    
    token_data = await storage_manager.get_user_token(google_sub)
    if not token_data:
        await update.message.reply_text(
            "🔐 <b>Authentication Required</b>\n\n"
            "Please authenticate first using /start",
            parse_mode='HTML'
        )
        return

    user_email = token_data.get('userinfo', {}).get('email', 'unknown')
    user_timezone = token_data.get('userinfo', {}).get('timezone', 'UTC')

    response = await agent_manager.run_agent(user_message, google_sub, user_email, user_timezone)

    await update.message.reply_text(response)


async def handle_confirmation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.callback_query or not update.effective_user:
        return
    
    query = update.callback_query
    await query.answer()

    storage_manager: StorageManager = context.bot_data['storage_manager']
    google_services_manager: GoogleServicesManager = context.bot_data['google_services_manager']
    logger: LogFunction = context.bot_data['logger']
    pending_events: dict = context.bot_data.get('pending_events', {})

    telegram_id = update.effective_user.id

    if query.data == 'confirm_event':
        google_sub = await get_user_id_for_telegram(storage_manager, telegram_id)
        if not google_sub:
            await query.edit_message_text(
                "❌ <b>Authentication Expired</b>\n\nPlease use /start to login again.",
                parse_mode='HTML'
            )
            return

        pending_event = pending_events.get(telegram_id)
        if not pending_event:
            await query.edit_message_text(
                "❌ <b>Error</b>\n\nNo pending event found.",
                parse_mode='HTML'
            )
            return

        token_data = await storage_manager.get_user_token(google_sub)
        if not token_data:
            await query.edit_message_text(
                "❌ <b>Authentication Expired</b>\n\nPlease use /start to login again.",
                parse_mode='HTML'
            )
            return

        access_token = token_data.get('access_token')
        if not access_token:
            await query.edit_message_text(
                "❌ <b>Error</b>\n\nAccess token not found.",
                parse_mode='HTML'
            )
            return

        result = await google_services_manager.create_calendar_event(
            access_token,
            pending_event['event_name'],
            pending_event['start_dt'],
            pending_event['end_dt'],
            pending_event['description'],
            pending_event['event_timezone'],
        )

        pending_events.pop(telegram_id, None)

        html_link = result.get('htmlLink', 'N/A')
        await query.edit_message_text(
            f"✅ <b>Event Created!</b>\n\n"
            f"Your event has been added to Google Calendar.\n\n"
            f"🔗 <a href='{html_link}'>View in Calendar</a>",
            parse_mode='HTML'
        )
        logger(f'Event created for user {telegram_id}', 'info')

    elif query.data == 'cancel_event':
        pending_events.pop(telegram_id, None)
        await query.edit_message_text(
            "🚫 <b>Event Cancelled</b>\n\nThe event was not created.",
            parse_mode='HTML'
        )


async def handle_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    
    storage_manager: StorageManager = context.bot_data['storage_manager']
    google_services_manager: GoogleServicesManager = context.bot_data['google_services_manager']
    logger: LogFunction = context.bot_data['logger']

    telegram_id = update.effective_user.id

    google_sub = await get_user_id_for_telegram(storage_manager, telegram_id)
    if not google_sub:
        await update.message.reply_text(
            "🔐 <b>Authentication Required</b>\n\n"
            "Please authenticate first using /start",
            parse_mode='HTML'
        )
        return

    try:
        events = await list_upcoming_events(
            storage_manager, google_services_manager, logger, google_sub
        )

        if not events:
            await update.message.reply_text(
                "📅 <b>No Upcoming Events</b>\n\n"
                "You don't have any upcoming events on your calendar.\n\n"
                "💬 Try chatting with me to create one!",
                parse_mode='HTML'
            )
            return

        message = '📅 <b>Your Upcoming Events:</b>\n\n'
        for event in events:
            summary = event.get('summary', 'No title')
            start = event.get('start', {}).get('dateTime', 'No date')
            message += f'• <b>{summary}</b>\n  📆 {start}\n\n'

        await update.message.reply_text(message, parse_mode='HTML')
    except Exception as e:
        logger(f'Error listing events for user {telegram_id}: {e}', 'error')
        await update.message.reply_text(
            f"❌ <b>Error</b>\n\n{e}",
            parse_mode='HTML'
        )


async def handle_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    
    storage_manager: StorageManager = context.bot_data['storage_manager']
    google_services_manager: GoogleServicesManager = context.bot_data['google_services_manager']
    logger: LogFunction = context.bot_data['logger']

    telegram_id = update.effective_user.id

    google_sub = await get_user_id_for_telegram(storage_manager, telegram_id)
    if not google_sub:
        await update.message.reply_text(
            "🔐 <b>Authentication Required</b>\n\n"
            "Please authenticate first using /start",
            parse_mode='HTML'
        )
        return

    try:
        args = context.args
        parsed = parse_add_command_args(args)

        event = await create_event(
            storage_manager,
            google_services_manager,
            logger,
            google_sub,
            parsed['summary'],
            parsed['datetime'],
        )

        html_link = event.get('htmlLink', 'N/A')
        await update.message.reply_text(
            f"✅ <b>Event Created!</b>\n\n"
            f"Your event has been added to Google Calendar.\n\n"
            f"🔗 <a href='{html_link}'>View in Calendar</a>",
            parse_mode='HTML'
        )
    except Exception as e:
        logger(f'Error creating event for user {telegram_id}: {e}', 'error')
        await update.message.reply_text(
            f"❌ <b>Error</b>\n\n{e}\n\n"
            f"<i>Usage: /newevent [summary] [datetime]</i>",
            parse_mode='HTML'
        )


async def handle_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    
    storage_manager: StorageManager = context.bot_data['storage_manager']

    telegram_id = update.effective_user.id

    reminders = await storage_manager.get_reminders(str(telegram_id))

    if not reminders:
        await update.message.reply_text(
            "⏰ <b>No Reminders</b>\n\n"
            "You don't have any recurring reminders set up.\n\n"
            "💡 Use /newreminder to create one!",
            parse_mode='HTML'
        )
        return

    message = '⏰ <b>Your Periodic Reminders:</b>\n\n'
    for reminder in reminders:
        message += (
            f"🔔 <b>ID #{reminder['id']}</b>\n"
            f"   📝 {reminder['message']}\n"
            f"   🕐 <code>{reminder['cron']}</code>\n\n"
        )

    await update.message.reply_text(message, parse_mode='HTML')


async def handle_reminder_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    
    storage_manager: StorageManager = context.bot_data['storage_manager']
    schedule_manager: ScheduleManager = context.bot_data['schedule_manager']
    logger: LogFunction = context.bot_data['logger']

    telegram_id = update.effective_user.id

    try:
        args = context.args
        parsed = parse_reminder_add_args(args)

        reminder_id = await add_reminder(
            schedule_manager,
            storage_manager,
            logger,
            telegram_id,
            parsed['cron'],
            parsed['message'],
        )

        await update.message.reply_text(
            f"✅ <b>Reminder Created!</b>\n\n"
            f"🔔 <b>ID:</b> #{reminder_id}\n"
            f"📝 <b>Message:</b> {parsed['message']}\n"
            f"🕐 <b>Schedule:</b> <code>{parsed['cron']}</code>\n\n"
            f"💡 Use /myreminders to view all your reminders",
            parse_mode='HTML'
        )
    except Exception as e:
        logger(f'Error adding reminder for user {telegram_id}: {e}', 'error')
        await update.message.reply_text(
            f"❌ <b>Error</b>\n\n{e}\n\n"
            f"<i>Usage: /newreminder [cron expression] [message]</i>\n"
            f"<i>Example: /newreminder 0 9 * * * Good morning!</i>",
            parse_mode='HTML'
        )


async def handle_reminder_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    
    storage_manager: StorageManager = context.bot_data['storage_manager']
    schedule_manager: ScheduleManager = context.bot_data['schedule_manager']
    logger: LogFunction = context.bot_data['logger']

    telegram_id = update.effective_user.id

    try:
        args = context.args
        reminder_id = parse_reminder_del_args(args)

        await delete_reminder(
            schedule_manager,
            storage_manager,
            logger,
            telegram_id,
            reminder_id,
        )

        await update.message.reply_text(
            f"✅ <b>Reminder Deleted!</b>\n\n"
            f"Reminder #{reminder_id} has been removed.\n\n"
            f"💡 Use /myreminders to view remaining reminders",
            parse_mode='HTML'
        )
    except Exception as e:
        logger(f'Error deleting reminder for user {telegram_id}: {e}', 'error')
        await update.message.reply_text(
            f"❌ <b>Error</b>\n\n{e}\n\n"
            f"<i>Usage: /deletereminder [reminder_id]</i>\n"
            f"<i>Use /myreminders to see your reminder IDs</i>",
            parse_mode='HTML'
        )


async def handle_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    
    storage_manager: StorageManager = context.bot_data['storage_manager']
    logger: LogFunction = context.bot_data['logger']

    telegram_id = update.effective_user.id

    google_sub = await get_user_id_for_telegram(storage_manager, telegram_id)
    if not google_sub:
        await update.message.reply_text(
            "ℹ️ <b>Not Logged In</b>\n\n"
            "You are not currently logged in.\n\n"
            "Use /start to login with Google.",
            parse_mode='HTML'
        )
        return

    success = await storage_manager.delete_user_token(google_sub)

    if success:
        await update.message.reply_text(
            "👋 <b>Logged Out</b>\n\n"
            "You have been successfully logged out.\n\n"
            "Use /start to login again.",
            parse_mode='HTML'
        )
        logger(f'User {telegram_id} logged out', 'info')
    else:
        await update.message.reply_text(
            "❌ <b>Logout Failed</b>\n\n"
            "There was an error logging you out. Please try again.",
            parse_mode='HTML'
        )


async def list_upcoming_events(
    storage_manager: StorageManager,
    google_services_manager: GoogleServicesManager,
    logger: LogFunction,
    google_sub: str,
    user_timezone: str = 'UTC',
):
    token_data = await user_tokens.get_valid_token(storage_manager, google_sub, logger)
    if not token_data:
        raise ValueError('User not authenticated')

    access_token = token_data.get('access_token')
    if not access_token:
        raise ValueError('Access token not found')

    tz = ZoneInfo(user_timezone)
    now = datetime.now(tz)
    events = await google_services_manager.list_upcoming_events(access_token, now, tz)
    return events


async def create_event(
    storage_manager: StorageManager,
    google_services_manager: GoogleServicesManager,
    logger: LogFunction,
    google_sub: str,
    summary: str,
    start_dt: datetime,
    user_timezone: str = 'UTC',
):
    token_data = await user_tokens.get_valid_token(storage_manager, google_sub, logger)
    if not token_data:
        raise ValueError('User not authenticated')

    access_token = token_data.get('access_token')
    if not access_token:
        raise ValueError('Access token not found')

    end_dt = start_dt + timedelta(hours=1)
    tz = ZoneInfo(user_timezone)

    event = await google_services_manager.create_calendar_event(
        access_token,
        summary,
        start_dt,
        end_dt,
        '',
        tz,
    )
    return event


async def add_reminder(
    schedule_manager: ScheduleManager,
    storage_manager: StorageManager,
    logger: LogFunction,
    user_id: int,
    cron: str,
    message: str,
):
    logger(f'Adding reminder for user {user_id}: "{message}" with cron "{cron}"', 'info')
    reminder_id = await storage_manager.add_reminder(str(user_id), cron, message)
    await schedule_manager.add_reminder(reminder_id, str(user_id), cron, message)
    logger(f'Reminder {reminder_id} added successfully for user {user_id}', 'info')
    return reminder_id


async def delete_reminder(
    schedule_manager: ScheduleManager,
    storage_manager: StorageManager,
    logger: LogFunction,
    user_id: int,
    reminder_id: int,
):
    logger(f'Deleting reminder {reminder_id} for user {user_id}', 'info')
    await schedule_manager.delete_reminder(reminder_id)
    await storage_manager.delete_reminder(reminder_id)
    logger(f'Reminder {reminder_id} deleted successfully for user {user_id}', 'info')


async def run_agent(
    agent_manager: AgentManager,
    user_message: str,
    user_id: int,
    user_email: str,
    user_timezone: str,
):
    response = await agent_manager.run_agent(user_message, str(user_id), user_email, user_timezone)
    return response
