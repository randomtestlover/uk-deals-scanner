"""Loads config.yaml + environment secrets into a single typed object."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml
from dotenv import load_dotenv

load_dotenv()  # no-op in CI/containers; loads .env locally


@dataclass
class Secrets:
    telegram_bot_token: str
    database_url: str
    alert_chat_id: str = ""

    @classmethod
    def from_env(cls) -> "Secrets":
        missing = [
            k
            for k in ("TELEGRAM_BOT_TOKEN", "DATABASE_URL")
            if not os.getenv(k)
        ]
        if missing:
            raise RuntimeError(
                f"Missing required secrets: {', '.join(missing)}. "
                "Set them in Coolify's environment variables (or .env locally)."
            )
        return cls(
            telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"].strip(),
            database_url=os.environ["DATABASE_URL"].strip(),
            alert_chat_id=os.getenv("ALERT_CHAT_ID", "").strip(),
        )


@dataclass
class Config:
    raw: dict[str, Any] = field(default_factory=dict)
    secrets: Optional[Secrets] = None

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        return cls(raw=raw, secrets=Secrets.from_env())

    # convenience accessors -----------------------------------
    @property
    def filters(self) -> dict:
        return self.raw["filters"]

    @property
    def posting(self) -> dict:
        return self.raw["posting"]

    @property
    def affiliate(self) -> dict:
        return self.raw["affiliate"]

    @property
    def categories(self) -> dict:
        return self.raw["categories"]

    @property
    def channels(self) -> dict:
        return self.raw["channels"]

    @property
    def click_tracking(self) -> dict:
        return self.raw.get("click_tracking", {"enabled": False})

    @property
    def scrape_fallback(self) -> dict:
        return self.raw.get("scrape_fallback", {"enabled": False})

    def channel_for(self, category: str) -> str:
        """Per-category channel if configured, else the main channel."""
        per = self.channels.get("per_category", {}) or {}
        return per.get(category) or self.channels["main_channel"]

    def awin_feed_urls(self) -> list[str]:
        """Awin datafeed URLs come from the AWIN_FEED_URLS secret (they
        contain your API key, so they must not live in config.yaml).
        Multiple feeds are separated by '|'. Returns [] if unset."""
        raw = os.getenv("AWIN_FEED_URLS", "").strip()
        if not raw:
            return []
        return [u.strip() for u in raw.split("|") if u.strip()]
