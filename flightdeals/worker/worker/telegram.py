"""Telegram channel poster + admin failure alerts (raw Bot API via httpx)."""
from __future__ import annotations

import html
import logging
import time

import httpx

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"
POST_GAP_SECONDS = 1.2  # gentle pacing, far below Telegram limits


class TelegramPoster:
    def __init__(self, bot_token: str, channel_id: str, site_base_url: str):
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.site_base_url = site_base_url
        self.client = httpx.Client(timeout=20)

    def _send(self, chat_id: str | int, text: str) -> bool:
        url = API.format(token=self.bot_token, method="sendMessage")
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        for attempt in range(3):
            resp = self.client.post(url, json=payload)
            if resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
                log.warning("telegram 429, sleeping %ss", retry_after)
                time.sleep(retry_after + 1)
                continue
            if resp.is_success:
                return True
            log.error("telegram send failed (%s): %s", resp.status_code, resp.text[:200])
            return False
        return False

    def format_deal(self, deal: dict) -> str:
        """deal: row from DB.unposted_deals (deal + route columns)."""
        origin = deal["origin"]
        dest = html.escape(deal["dest_name"])
        price = float(deal["price_gbp"])
        pct = deal.get("discount_pct")
        baseline = deal.get("baseline_gbp")
        trigger = deal["trigger"]

        lines = [f"✈️ <b>{origin} → {dest} — £{price:.0f} return</b>"]
        if pct and baseline:
            lines.append(f"📉 {float(pct):.0f}% below the typical £{float(baseline):.0f}")
        if trigger == "floor":
            lines.append("🔥 Exceptional fare — at or under our band floor")
        out = deal["depart_date"].strftime("%a %d %b")
        back = deal["return_date"].strftime("%a %d %b") if deal.get("return_date") else None
        when = f"📅 Out {out}" + (f" · Back {back}" if back else " · one-way")
        if deal.get("airline"):
            when += f" · {html.escape(str(deal['airline']))}"
        lines.append(when)
        lines.append(f'🎟 <a href="{self.site_base_url}/go/{deal["id"]}">Check &amp; book</a>')
        lines.append("")
        lines.append("Fares move fast — verify the price before booking.")
        return "\n".join(lines)

    def post_deal(self, deal: dict) -> bool:
        ok = self._send(self.channel_id, self.format_deal(deal))
        time.sleep(POST_GAP_SECONDS)
        return ok

    def dm(self, chat_id: int, text: str) -> bool:
        ok = self._send(chat_id, text)
        time.sleep(POST_GAP_SECONDS)
        return ok


def admin_alert(bot_token: str | None, admin_chat_id: str | None, text: str) -> None:
    """Best-effort failure alert to the operator. Never raises."""
    if not (bot_token and admin_chat_id):
        return
    try:
        httpx.post(
            API.format(token=bot_token, method="sendMessage"),
            json={"chat_id": admin_chat_id, "text": f"⚠️ flightdeals worker: {text[:3500]}"},
            timeout=10,
        )
    except httpx.HTTPError:
        log.exception("admin alert failed")
