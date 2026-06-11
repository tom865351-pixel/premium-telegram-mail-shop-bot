from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    database_public_url: str | None = Field(default=None, alias="DATABASE_PUBLIC_URL")
    admin_ids_raw: str = Field(default="", alias="ADMIN_IDS")
    support_admin_ids_raw: str = Field(default="", alias="SUPPORT_ADMIN_IDS")
    stock_manager_ids_raw: str = Field(default="", alias="STOCK_MANAGER_IDS")

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
    usd_to_tk_rate: float = Field(default=125.0, alias="USD_TO_TK_RATE")
    semi_auto_deposit_enabled: bool = Field(default=True, alias="SEMI_AUTO_DEPOSIT_ENABLED")
    semi_auto_deposit_max_amount: float = Field(default=100, alias="SEMI_AUTO_DEPOSIT_MAX_AMOUNT")
    semi_auto_trusted_user_min_approved_deposits: int = Field(
        default=1,
        alias="SEMI_AUTO_TRUSTED_USER_MIN_APPROVED_DEPOSITS",
    )
    semi_auto_daily_user_limit: float = Field(default=200, alias="SEMI_AUTO_DAILY_USER_LIMIT")
    ocr_enabled: bool = Field(default=True, alias="OCR_ENABLED")
    ocr_space_api_key: str = Field(default="helloworld", alias="OCR_SPACE_API_KEY")
    ocr_space_api_url: str = Field(default="https://api.ocr.space/parse/image", alias="OCR_SPACE_API_URL")
    low_stock_alert_threshold: int = Field(default=5, alias="LOW_STOCK_ALERT_THRESHOLD")
    ai_enabled: bool = Field(default=False, alias="AI_ENABLED")
    ai_provider: str = Field(default="gemini", alias="AI_PROVIDER")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    force_join_enabled: bool = Field(default=True, alias="FORCE_JOIN_ENABLED")
    required_channel_username: str = Field(default="@PremiumXMethod", alias="REQUIRED_CHANNEL_USERNAME")
    required_channel_link: str = Field(default="https://t.me/PremiumXMethod", alias="REQUIRED_CHANNEL_LINK")
    zinipay_trx_enabled: bool = Field(default=False, alias="ZINIPAY_TRX_ENABLED")
    zinipay_api_key: str | None = Field(default=None, alias="ZINIPAY_API_KEY")
    zinipay_trx_base_url: str = Field(default="https://api.zinipay.com/api/trx", alias="ZINIPAY_TRX_BASE_URL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @staticmethod
    def parse_id_set(value: str | set[int] | list[int] | None) -> set[int]:
        if isinstance(value, set):
            return value
        if isinstance(value, list):
            return {int(item) for item in value}
        if not value:
            return set()
        return {int(item.strip()) for item in str(value).split(",") if item.strip()}

    @property
    def admin_ids(self) -> set[int]:
        return self.parse_id_set(self.admin_ids_raw)

    @property
    def support_admin_ids(self) -> set[int]:
        return self.parse_id_set(self.support_admin_ids_raw)

    @property
    def stock_manager_ids(self) -> set[int]:
        return self.parse_id_set(self.stock_manager_ids_raw)

    @field_validator("admin_ids_raw", "support_admin_ids_raw", "stock_manager_ids_raw", mode="before")
    @classmethod
    def normalize_id_list(cls, value: str | None) -> str:
        if not value:
            return ""
        return str(value)

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
