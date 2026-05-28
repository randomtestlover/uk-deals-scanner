"""Builds the final outbound link: injects the Amazon Associates tag,
then optionally wraps it in the Cloudflare Worker click-tracking redirect."""

from __future__ import annotations

from urllib.parse import quote, urlencode, urlparse, urlunparse, parse_qsl


def inject_amazon_tag(url: str, tag: str) -> str:
    """Add/replace the ?tag= associate parameter on an Amazon URL.
    Non-Amazon URLs are returned unchanged."""
    parsed = urlparse(url)
    if "amazon." not in parsed.netloc and "amzn." not in parsed.netloc:
        return url
    query = dict(parse_qsl(parsed.query))
    query["tag"] = tag
    new_query = urlencode(query)
    return urlunparse(parsed._replace(query=new_query))


def wrap_click_tracking(url: str, worker_base: str, category: str) -> str:
    """Route a link through the Worker so clicks can be counted.
    The Worker 302-redirects to ?u= and logs the hit."""
    if not worker_base:
        return url
    base = worker_base.rstrip("/")
    qs = urlencode({"u": url, "c": category})
    return f"{base}/go?{qs}"


def build_outbound_url(raw_url: str, *, amazon_tag: str, category: str,
                       tracking_enabled: bool, worker_base: str) -> str:
    tagged = inject_amazon_tag(raw_url, amazon_tag)
    if tracking_enabled and worker_base:
        return wrap_click_tracking(tagged, worker_base, category)
    return tagged
