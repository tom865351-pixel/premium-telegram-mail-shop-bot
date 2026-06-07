from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    database_public_url: str | None = Field(default=None, alias="DATABASE_PUBLIC_URL")
    admin_ids: set[int] = Field(default_factory=set, alias="ADMIN_IDS")

    binance_pay_id: str | None = Field(default=None, alias="BINANCE_PAY_ID")
    usdt_trc20_address: str | None = Field(default=None, alias="USDT_TRC20_ADDRESS")
    usdt_bep20_address: str | None = Field(default=None, alias="USDT_BEP20_ADDRESS")
    bkash_number: str | None = Field(default=None, alias="BKASH_NUMBER")
    nagad_number: str | None = Field(default=None, alias="NAGAD_NUMBER")
    rocket_number: str | None = Field(default=None, alias="ROCKET_NUMBER")

    referral_commission_percent: float = Field(default=10, alias="REFERRAL_COMMISSION_PERCENT")
    support_username: str = Field(default="support", alias="SUPPORT_USERNAME")
    min_deposit: float = Field(default=1.0, alias="MIN_DEPOSIT")
    currency_symbol: str = Field(default="$", alias="CURRENCY_SYMBOL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: str | set[int] | list[int]) -> set[int]:
        if isinstance(value, set):
            return value
        if isinstance(value, list):
            return {int(item) for item in value}
        if not value:
            return set()
        return {int(item.strip()) for item in str(value).split(",") if item.strip()}

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("database_public_url", mode="before")
    @classmethod
    def normalize_database_public_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @model_validator(mode="after")
    def prefer_public_database_url_when_needed(self) -> "Settings":
        if self.database_public_url and ".railway.internal" in self.database_url:
            self.database_url = self.database_public_url
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
