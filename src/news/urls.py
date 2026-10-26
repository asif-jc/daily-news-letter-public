"""Shared URL identity, publisher boundaries and model text validation."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def canonical_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Expected a public HTTP article URL")
    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query)
        if not k.lower().startswith("utm_")
        and k.lower()
        not in {"fbclid", "gclid", "at_medium", "at_campaign", "ref", "source"}
    ]
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            urlencode(sorted(query)),
            "",
        )
    )


def _text(value, field, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"Expected text for {field}")
    return value.strip()


def allowed_public_url(url, hosts):
    """Restrict every fetch and rendered source link to reviewed publisher domains."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        return (
            parsed.scheme in ("http", "https")
            and not parsed.username
            and not parsed.password
            and parsed.port in (None, 80, 443)
            and any(
                host == allowed or host.endswith("." + allowed) for allowed in hosts
            )
        )
    except (ValueError, TypeError):
        return False


def allowed_publisher_url(url):
    from .sources import PUBLISHER_HOSTS

    return allowed_public_url(url, PUBLISHER_HOSTS)
