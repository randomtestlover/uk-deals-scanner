"""Telegram posting layer.

Formats a ScoredDeal into a varied, human-feeling message, posts it with
rate-limit awareness (Telegram caps ~30 msgs/sec and ~20 msgs/min to one
chat), and can DM the operator on failures.

Variety is deterministic per deal: we seed the random choices with the
deal's dedupe_hash, so a given deal always renders the same way, but
consecutive *different* deals look and read differently — avoiding the
robotic "same template every time" feel.
"""

from __future__ import annotations

import asyncio
import html
import random
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError

from core.models import ScoredDeal


# Quality tiers drive both the badge and the tone of the copy.
def _tier(score: int) -> str:
    if score >= 85:
        return "hot"
    if score >= 72:
        return "great"
    if score >= 60:
        return "good"
    return "ok"


# Varied openers per tier. Picked deterministically per deal.
_OPENERS = {
    "hot": [
        "🔥 <b>Red-hot deal</b>",
        "🔥 <b>This one's a cracker</b>",
        "🚨 <b>Big drop just landed</b>",
        "🔥 <b>Rare price alert</b>",
        "⚡ <b>Don't sleep on this</b>",
    ],
    "great": [
        "⭐ <b>Great price</b>",
        "👀 <b>Worth a proper look</b>",
        "⭐ <b>Strong deal</b>",
        "✨ <b>Tidy little saving</b>",
        "👀 <b>Spotted a good one</b>",
    ],
    "good": [
        "👍 <b>Decent drop</b>",
        "👍 <b>Solid price</b>",
        "🛒 <b>Worth a look</b>",
        "👍 <b>Nice little deal</b>",
    ],
    "ok": [
        "🆗 <b>Price drop</b>",
        "🛒 <b>On offer</b>",
        "🆗 <b>Modest saving</b>",
    ],
}

# Varied call-to-action link text.
_CTAS = [
    "Grab it here",
    "View the deal",
    "Check it out",
    "See the price",
    "Have a look",
    "Get it here",
]

# Varied phrasing for the saving line (filled with values).
_SAVE_PHRASES = [
    "Down to <b>{price}</b> from {was} — that's <b>{pct}% off</b>",
    "<b>{price}</b> <s>{was}</s>  ·  <b>{pct}% off</b>",
    "Now <b>{price}</b> (was {was}) — save <b>{pct}%</b>",
    "<b>{price}</b>, down from {was}  ·  <b>−{pct}%</b>",
]


def _badge(tier: str, score: int) -> str:
    label = {"hot": "RED HOT", "great": "GREAT", "good": "GOOD", "ok": "DEAL"}[tier]
    return f"{label} · {score}/100"


def _stars(tier: str) -> str:
    return {"hot": "🔥🔥🔥", "great": "⭐⭐", "good": "⭐", "ok": ""}[tier]


def format_message(deal: ScoredDeal, disclosure: str) -> str:
    # Deterministic variety: same deal -> same render, different deals vary.
    rng = random.Random(deal.dedupe_hash)
    tier = _tier(deal.deal_score)
    title = html.escape(deal.title)
    price = f"£{deal.current_price:,.2f}"

    lines = []

    # 1) Opener (varied by tier)
    lines.append(rng.choice(_OPENERS[tier]))
    lines.append("")

    # 2) Product name
    lines.append(f"<b>{title}</b>")

    # 3) Price / saving line (varied phrasing when we have a 'was' price)
    if deal.ref_price and deal.pct_off:
        was = f"£{deal.ref_price:,.2f}"
        phrase = rng.choice(_SAVE_PHRASES).format(
            price=price, was=was, pct=f"{deal.pct_off:.0f}"
        )
        lines.append(f"💷 {phrase}")
    else:
        lines.append(f"💷 <b>{price}</b>")

    # 4) Compact meta line: category + score badge (+ stars for top tiers)
    stars = _stars(tier)
    meta = f"🏷️ {html.escape(deal.category.title())}  ·  {_badge(tier, deal.deal_score)}"
    if stars:
        meta += f"  {stars}"
    lines.append(meta)

    lines.append("")

    # 5) Varied CTA link
    cta = rng.choice(_CTAS)
    lines.append(f'➡️ <a href="{html.escape(deal.affiliate_url, quote=True)}">{cta}</a>')

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
