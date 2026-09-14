"""Einstellungen aus Umgebungsvariablen (Präfix EMPRISE_)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMPRISE_", env_file=".env", extra="ignore")

    env: Literal["local", "test", "staging", "production"] = "local"
    release: str = "dev"
    log_level: str = "INFO"

    # Öffentliche Adresse, unter der Frontend und API gemeinsam erreichbar sind (Plan 6.2)
    public_base_url: str = "http://localhost:8080"

    # Datenbank: die Anwendung arbeitet mit der Rolle `app`, Migrationen mit `migrator` (Plan 6.6)
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/emprise"
    migration_database_url: str | None = None

    # Geheimnis für Signaturen (OIDC-Zwischenspeicher, Rate-Limit-Schlüssel)
    secret_key: SecretStr = SecretStr("local-development-only-change-me")

    # Anmeldung Büro über OIDC (Entscheidung D4 offen; Anbieter per Konfiguration)
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = None
    oidc_scopes: str = "openid email profile"
    oidc_require_mfa: bool = True
    oidc_mfa_amr_values: list[str] = Field(default_factory=lambda: ["mfa", "otp", "hwk", "swk", "fido"])
    staff_session_hours: int = 12

    # Kundenprojekte ohne Kontakt (Plan 6.6)
    project_retention_days: int = 90
    project_create_limit_per_hour: int = 30

    # Objektspeicher (S3-kompatibel)
    s3_endpoint_url: str | None = None
    s3_public_endpoint_url: str | None = None
    s3_region: str = "fr-par"
    s3_bucket: str = "emprise-local"
    s3_access_key: SecretStr | None = None
    s3_secret_key: SecretStr | None = None

    # Mail (Anbieter offen, E2); lokal Mailpit
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = False
    smtp_ssl: bool = False
    mail_from: str = "Emprise <no-reply@emprise.local>"

    # Überwachung
    sentry_dsn: str | None = None
    job_waiting_alarm_minutes: int = 15

    # Worker
    worker_queues: list[str] = Field(default_factory=lambda: ["default"])
    worker_poll_seconds: float = 1.0

    @property
    def cookie_secure(self) -> bool:
        return self.env in ("staging", "production")

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if self.env in ("staging", "production"):
            if self.secret_key.get_secret_value() == "local-development-only-change-me":
                raise ValueError("EMPRISE_SECRET_KEY muss in staging und production gesetzt sein")
            if not self.public_base_url.startswith("https://"):
                raise ValueError("EMPRISE_PUBLIC_BASE_URL muss in staging und production https verwenden")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
