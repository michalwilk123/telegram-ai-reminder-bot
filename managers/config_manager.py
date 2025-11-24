from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigManager(BaseSettings):
    google_oauth2_client_id: str
    google_oauth2_secret: str
    redirect_url: str
    secret_key: str
    telegram_bot_token: str
    google_api_key: str
    database_url: str
    debug: bool
    server_host: str = '0.0.0.0'
    server_port: int = 9000

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')


config_manager = ConfigManager()
