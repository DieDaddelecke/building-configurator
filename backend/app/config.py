"""Einstellungen aus Umgebungsvariablen (Präfix EMPRISE_)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.products import Product


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMPRISE_", env_file=".env", extra="ignore")

    env: Literal["local", "test", "staging", "production"] = "local"
    release: str = "dev"
    log_level: str = "INFO"

    # Produkt dieser Instanz (app/products.py, PLAN_ANALYSE 3): `analyse` lädt die Module des
    # Hauskonfigurators nicht und plant seine Datenimporte nicht ein.
    product: Product = "configurator"

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

    # Externe Dienste (Spez. 9; Endpunkte am 14.09.2026 geprüft, Plan 3.3)
    external_timeout_seconds: float = 8.0
    http_user_agent: str = "Emprise-Plattform/0.1"
    geoplateforme_base_url: str = "https://data.geopf.fr"
    georisques_base_url: str = "https://georisques.gouv.fr/api/v1"
    georisques_token: SecretStr | None = None
    cadastre_base_url: str = "https://cadastre.data.gouv.fr/data/etalab-cadastre"

    # Grundstück (G1). Einzugsgebiet als INSEE-Codes; Entscheidung D1 offen, Vorschlag: um Treillières
    cadastre_communes: list[str] = Field(default_factory=lambda: ["44209"])
    cadastre_max_count_change_ratio: float = 0.02
    cadastre_max_count_change_absolute: int = 50
    geocode_cache_hours: int = 24
    geocode_limit_per_minute: int = 60
    cadastre_limit_per_minute: int = 120
    site_write_limit_per_hour: int = 120
    site_upload_max_bytes: int = 20 * 1024 * 1024
    """Größte hochgeladene Parzellendatei (DXF, GeoJSON, PDF) in „Emprise Analyse“ (AN1, UP08)."""

    # Regelwerk (G2, Plan 3.4): GPU-Endpunkte am 14.09.2026 geprüft; Auswertung per Claude API (D11)
    apicarto_base_url: str = "https://apicarto.ign.fr/api"
    gpu_api_base_url: str = "https://www.geoportail-urbanisme.gouv.fr/api"
    gpu_files_base_url: str = "https://data.geopf.fr/annexes/gpu/documents"
    anthropic_api_key: SecretStr | None = None
    rules_model: str = "claude-opus-5"
    rules_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    rules_runs: int = Field(default=2, ge=1, le=3)
    rules_request_timeout_seconds: float = 900.0
    rules_budget_month_usd: float = 150.0
    """Obergrenze der Auswertungskosten je Kalendermonat; darüber startet keine neue Auswertung (Alarm)."""
    rules_price_input_per_mtok: float = 5.0
    rules_price_output_per_mtok: float = 25.0
    rules_limit_per_minute: int = 60

    # Baurahmen (G3)
    envelope_limit_per_minute: int = 60
    envelope_sheet_limit_per_hour: int = 20
    """Der Steckbrief wird im Worker gesetzt; je Eingabestand entsteht er nur einmal."""

    # Konfigurator (H2)
    configuration_limit_per_minute: int = 120

    # Anfrage (A, Plan 3.6)
    office_email: str = "buero@emprise.local"
    """Sammelpostfach des Architekturbüros für neue Anfragen; ein Anbieterwechsel (E2) ändert nur SMTP."""
    inquiry_code_ttl_minutes: int = 10
    inquiry_code_max_attempts: int = 5
    inquiry_contact_limit_per_hour_ip: int = 10
    inquiry_contact_limit_per_hour_email: int = 5
    inquiry_confirm_limit_per_hour_ip: int = 20

    # Vorentwurf-Übergabe (V, docs/PLAN_V_VORENTWURF_UEBERGABE.md 3.11)
    submission_limit_per_hour_ip: int = 20
    message_limit_per_hour_ip: int = 30
    access_link_days: int = 30
    """Gültigkeit des Zugangslinks in Kundenmails (Spez. 5.10.7)."""
    access_redeem_limit_per_hour_ip: int = 20
    access_request_limit_per_hour_ip: int = 5
    access_request_limit_per_hour_email: int = 3

    # Überwachung
    sentry_dsn: str | None = None
    job_waiting_alarm_minutes: int = 15

    # Worker
    worker_queues: list[str] = Field(default_factory=lambda: ["default"])
    worker_poll_seconds: float = 1.0

    @field_validator("anthropic_api_key", "georisques_token", mode="before")
    @classmethod
    def _empty_secret_is_unset(cls, value: object) -> object:
        """Compose übergibt nicht gesetzte Variablen als leere Zeichenkette: „nicht eingerichtet“."""
        return None if isinstance(value, str) and not value.strip() else value

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
