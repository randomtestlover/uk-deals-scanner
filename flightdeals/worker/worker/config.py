"""Configuration: secrets from env, route/detection settings from config.yaml."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Secrets:
    database_url: str
    travelpayouts_token: str | None
    travelpayouts_marker: str | None
    kiwi_api_key: str | None
    telegram_bot_token: str | None
    telegram_channel_id: str | None
    admin_chat_id: str | None
    resend_api_key: str | None
    alert_from_email: str | None
    site_base_url: str

    @classmethod
    def from_env(cls) -> "Secrets":
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url:
            raise ConfigError("DATABASE_URL is required")
        return cls(
            database_url=database_url,
            travelpayouts_token=os.environ.get("TRAVELPAYOUTS_TOKEN") or None,
            travelpayouts_marker=os.environ.get("TRAVELPAYOUTS_MARKER") or None,
            kiwi_api_key=os.environ.get("KIWI_API_KEY") or None,
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN") or None,
            telegram_channel_id=os.environ.get("TELEGRAM_CHANNEL_ID") or None,
            admin_chat_id=os.environ.get("ADMIN_CHAT_ID") or None,
            resend_api_key=os.environ.get("RESEND_API_KEY") or None,
            alert_from_email=os.environ.get("ALERT_FROM_EMAIL") or None,
            site_base_url=os.environ.get("SITE_BASE_URL", "http://localhost:3000").rstrip("/"),
        )


@dataclass
class Config:
    raw: dict
    secrets: Secrets
    shadow: bool = False
    path: Path = field(default_factory=lambda: Path("config.yaml"))

    @classmethod
    def load(cls, path: str | Path = "config.yaml", shadow: bool = False) -> "Config":
        p = Path(path)
        if not p.exists():
            # fall back to the file next to this package (container WORKDIR varies)
            p = Path(__file__).resolve().parent.parent / "config.yaml"
        with open(p, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        shadow = shadow or os.environ.get("SHADOW_MODE", "").lower() in ("1", "true", "yes")
        return cls(raw=raw, secrets=Secrets.from_env(), shadow=shadow, path=p)

    # --- detection ---
    @property
    def detection(self) -> dict:
        return self.raw.get("detection", {})

    @property
    def bands(self) -> dict[str, dict]:
        return self.raw.get("bands", {})

    def floor_for_band(self, band: str) -> float:
        return float(self.bands.get(band, {}).get("floor_gbp", 0))

    # --- airports & routes ---
    @property
    def airports(self) -> list[dict]:
        """All origin airports with their tier."""
        out: list[dict] = []
        for tier in ("free", "plus"):
            for a in self.raw.get("airports", {}).get(tier, []):
                out.append({**a, "tier": tier})
        return out

    @property
    def destinations(self) -> list[dict]:
        return [
            {"iata": d[0], "name": d[1], "band": d[2]}
            for d in self.raw.get("destinations", [])
        ]

    def routes(self) -> list[dict]:
        """Cross-product of origins x destinations. Route tier = origin tier."""
        out = []
        for a in self.airports:
            for d in self.destinations:
                if a["iata"] == d["iata"]:
                    continue
                out.append(
                    {
                        "origin": a["iata"],
                        "destination": d["iata"],
                        "dest_name": d["name"],
                        "band": d["band"],
                        "tier": a["tier"],
                    }
                )
        return out


def redact(text: str, secrets: Secrets) -> str:
    """Strip secret values from log lines (defence-in-depth for CI/Coolify logs)."""
    for value in (
        secrets.travelpayouts_token,
        secrets.kiwi_api_key,
        secrets.telegram_bot_token,
        secrets.resend_api_key,
    ):
        if value:
            text = text.replace(value, "***")
    return text
