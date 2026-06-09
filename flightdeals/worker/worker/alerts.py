"""Saved-route alert fan-out: email (Resend) + Telegram DM for linked accounts."""
from __future__ import annotations

import html
import logging

import httpx

from .config import Secrets
from .db import DB
from .telegram import TelegramPoster

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


def _email_body(deal: dict, site: str) -> str:
    pct = deal.get("discount_pct")
    pct_line = f" ({float(pct):.0f}% below typical)" if pct else ""
    return (
        f"<p><strong>{deal['origin']} → {html.escape(deal['dest_name'])} "
        f"£{float(deal['price_gbp']):.0f} return</strong>{pct_line}</p>"
        f"<p>Out {deal['depart_date']:%a %d %b}"
        + (f" · Back {deal['return_date']:%a %d %b}" if deal.get("return_date") else "")
        + f"</p><p><a href=\"{site}/go/{deal['id']}\">Check &amp; book</a></p>"
        f"<p>You're getting this because of your saved alert on FlightDeals UK. "
        f"Manage alerts: {site}/account</p>"
    )


def send_email(secrets: Secrets, to: str, subject: str, html_body: str) -> bool:
    if not (secrets.resend_api_key and secrets.alert_from_email):
        return False
    try:
        resp = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {secrets.resend_api_key}"},
            json={"from": secrets.alert_from_email, "to": [to],
                  "subject": subject, "html": html_body},
            timeout=15,
        )
        return resp.is_success
    except httpx.HTTPError:
        log.exception("resend email failed")
        return False


def run_alerts(db: DB, secrets: Secrets, poster: TelegramPoster | None,
               shadow: bool = False, hours: int = 24) -> int:
    """Match deals found in the last `hours` against saved alerts and notify.

    Idempotence: alert fan-out runs right after detection in the same pipeline,
    and deals are only inserted once per fare_hash per dedupe window, so each
    deal is fanned out at most once.
    """
    sent = 0
    for deal in db.recent_unnotified_deals(hours=hours):
        for match in db.matching_alerts(deal):
            subject = (
                f"✈ {deal['origin']} → {deal['dest_name']} "
                f"£{float(deal['price_gbp']):.0f} return"
            )
            if shadow:
                log.info("[shadow] would alert user=%s %s", match["user_id"], subject)
                continue
            if "email" in match["channels"] and match.get("email"):
                if send_email(secrets, match["email"], subject,
                              _email_body(deal, secrets.site_base_url)):
                    sent += 1
            if "telegram" in match["channels"] and match.get("telegram_chat_id") and poster:
                if poster.dm(match["telegram_chat_id"], poster.format_deal(deal)):
                    sent += 1
    return sent
