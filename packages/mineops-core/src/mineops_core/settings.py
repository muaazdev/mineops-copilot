"""Central configuration. The only place env vars are read (CLAUDE.md: config conventions)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DbSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    name: str = "mineops"
    user: str = "mineops_owner"
    password: SecretStr = SecretStr("")
    statement_timeout_ms: int = Field(default=5000, ge=0)

    def url(self, driver: str = "postgresql+psycopg") -> str:
        """SQLAlchemy URL. The password is only revealed here, never logged."""
        pw = self.password.get_secret_value()
        auth = f"{self.user}:{pw}" if pw else self.user
        return f"{driver}://{auth}@{self.host}:{self.port}/{self.name}"

    def conninfo(self) -> str:
        """libpq conninfo string for raw psycopg connections."""
        parts = {
            "host": self.host,
            "port": str(self.port),
            "dbname": self.name,
            "user": self.user,
        }
        pw = self.password.get_secret_value()
        if pw:
            parts["password"] = pw
        return " ".join(f"{k}={v}" for k, v in parts.items())


class LogSettings(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    json_format: bool = True


class MineOpsSettings(BaseSettings):
    """Base settings; services subclass and add their own sections.

    Env vars: ``MINEOPS_SERVICE_NAME``, ``MINEOPS_DB__HOST``, ``MINEOPS_LOG__LEVEL`` ...
    """

    model_config = SettingsConfigDict(
        env_prefix="MINEOPS_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "mineops"
    environment: Literal["local", "ci", "kind", "gke"] = "local"
    db: DbSettings = DbSettings()
    log: LogSettings = LogSettings()


@lru_cache(maxsize=1)
def get_settings() -> MineOpsSettings:
    return MineOpsSettings()
