from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import quote_plus

class Settings(BaseSettings):
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    postgres_db: str
    
    influxdb_host: str
    influxdb_port: int
    influx_token: str
    influx_org: str
    influx_bucket: str
    
    redis_host: str
    redis_port: int
    redis_channel: str
    
    mqtt_broker: str
    mqtt_port: int
    
    cors_origins: str
    api_port: int
    data_dir: str
    contracts_dir: str

    @property
    def sync_database_url(self) -> str:
        pwd = quote_plus(self.postgres_password)
        return f"postgresql+psycopg://{self.postgres_user}:{pwd}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    model_config = SettingsConfigDict(extra="ignore")

settings = Settings()
