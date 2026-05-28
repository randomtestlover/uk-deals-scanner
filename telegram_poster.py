"""Telegram posting layer.

Formats a ScoredDeal into a clean message, posts it with rate-limit
awareness (Telegram caps ~30 msgs/sec and ~20 msgs/min to one chat),
and can DM the operator on failures.
"""

from __future__ import annotations

import asyncio
import html
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError

from core.models import ScoredDeal


def _score_badge(score: int) -> str:
    if score >= 85:
        return "🔥 RED HOT"
    if score >= 75:
        return "⭐ GREAT"
    if score >= 65:
        return "👍 GOOD"
    return "🆗 DECENT"


def format_message(deal: ScoredDeal, disclosure: str) -> str:
    title = html.escape(deal.title)
    price = f"£{deal.current_price:,.2f}"
    lines = [f"<b>{_score_badge(deal.deal_score)}</b>  ({deal.deal_score}/100)", "", f"<b>{title}</b>"]

    if deal.ref_price and deal.pct_off:
        was = f"£{deal.ref_price:,.2f}"
        lines.append(f"💷 <b>{price}</b>  <s>{was}</s>  (−{deal.pct_off:.0f}%)")
    else:
        lines.append(f"💷 <b>{price}</b>")

    lines.append(f"🏷️ {html.escape(deal.category.title())}")
    lines.append("")
    lines.append(f'➡️ <a href="{html.escape(deal.affiliate_url, quote=True)}">View deal</a>')
    lines.append("")
    lines.append(f"<i>{html.escape(disclosure)}</i>")
    return "\n".join(lines)


class TelegramPoster:
    def __init__(self, token: str, alert_chat_id: str = ""):
        self.bot = Bot(token=token)
        self.alert_chat_id = alert_chat_id

    async def _send(self, chat_id: str, text: str) -> Optional[int]:
        """Send one message, honouring Telegram RetryAfter back-off."""
        for attempt in range(4):
            try:
                msg = await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False,
                )
                return msg.message_id
            except RetryAfter as e:
                await asyncio.sleep(float(e.retry_after) + 1)
            except TelegramError:
                await asyncio.sleep(2 * (attempt + 1))
        return None

    async def post_deal(self, deal: ScoredDeal, channel: str, disclosure: str) -> Optional[int]:
        text = format_message(deal, disclosure)
        message_id = await self._send(channel, text)
        # Gentle throughput limit — well under Telegram's caps.
        await asyncio.sleep(1.2)
        return message_id

    async def alert(self, message: str) -> None:
        if not self.alert_chat_id:
            return
        try:
            await self.bot.send_message(
                chat_id=self.alert_chat_id,
                text=f"⚠️ <b>UK Deals Scanner</b>\n{html.escape(message)}",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            pass
