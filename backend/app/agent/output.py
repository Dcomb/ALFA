import re
from urllib.parse import urlparse


MARKDOWN_LINK = re.compile(
    r"\[([^\]]+)\]\((https?://[^)\s]+)\)"
)

ALLOWED_SOURCE_DOMAINS = {
    "alfabank.ru",
    "alfabank.by",
    "alfaleasing.ru",
}


def allowed_source_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in ALLOWED_SOURCE_DOMAINS
    )


def sanitize_answer_links(answer: str) -> str:
    """Remove an untrusted URL while preserving its readable label."""

    def replace(match: re.Match) -> str:
        label, url = match.groups()
        return match.group(0) if allowed_source_url(url) else label

    return MARKDOWN_LINK.sub(replace, answer)
