from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
import uvicorn

from managers.adapters import AiAgentAdapter
from managers.agent_manager import AgentManager
from managers.config_manager import config_manager
from managers.google_services_manager import GoogleServicesManager
from managers.logging_manager import create_log_function, create_logger
from managers.schedule_manager import ScheduleManager
from managers.storage_manager import StorageManager
from ui.telegram import (
    create_bot_application,
    register_handlers,
    start_telegram_bot,
    stop_telegram_bot,
)
from ui.web import create_app
from utils import create_http_client


@asynccontextmanager
async def combined_lifespan(app: Starlette):
    storage_manager = app.state.storage_manager
    schedule_manager = app.state.schedule_manager
    http_client = app.state.http_client
    bot_application = app.state.bot_application
    google_services_manager = app.state.google_services_manager
    logger = app.state.logger

    await storage_manager.init_db()

    # Initialize agent manager for web interface
    web_agent_adapter = AiAgentAdapter(
        storage_manager, schedule_manager, google_services_manager, logger
    )
    app.state.agent_manager = AgentManager(
        config_manager.google_api_key, services=web_agent_adapter, logger=logger
    )
    logger('Agent manager initialized', 'info')

    await start_telegram_bot(
        bot_application,
        storage_manager,
        schedule_manager,
        google_services_manager,
        logger,
        config_manager.google_api_key,
    )

    try:
        yield
    finally:
        await stop_telegram_bot(bot_application, schedule_manager, logger)
        logger('Closing resources', 'info')
        await storage_manager.close()
        await http_client.aclose()


def build_app(verbose: bool):
    log_dir = Path.cwd() / 'logs'
    logger_instance = create_logger(log_dir, 'reminder_app', verbose)
    log_message = create_log_function(logger_instance)

    http_client = create_http_client(log_message)
    storage_manager = StorageManager(config_manager.database_url)
    schedule_manager = ScheduleManager(log_message, storage_manager.get_all_reminders)
    google_services_manager = GoogleServicesManager(http_client, log_message)

    bot_application = create_bot_application()
    bot_application.bot_data['storage_manager'] = storage_manager
    bot_application.bot_data['schedule_manager'] = schedule_manager
    bot_application.bot_data['google_services_manager'] = google_services_manager
    bot_application.bot_data['logger'] = log_message

    register_handlers(bot_application)

    web_app = create_app(
        storage_manager=storage_manager,
        schedule_manager=schedule_manager,
        google_services_manager=google_services_manager,
        http_client=http_client,
        logger=log_message,
        bot_application=bot_application,
    )

    web_app.state.google_services_manager = google_services_manager
    web_app.router.lifespan_context = combined_lifespan

    return web_app


def start():
    app = build_app(verbose=True)
    uvicorn.run(
        app,
        host=config_manager.server_host,
        port=config_manager.server_port,
        proxy_headers=True,
        forwarded_allow_ips='*',
    )


if __name__ == '__main__':
    start()
