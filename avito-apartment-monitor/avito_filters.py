"""Pure helpers for the listing monitor (no browser, easy to unit-test)."""


def is_blacklisted(location: str, blacklist: list[str]) -> bool:
    """True if the listing location contains any blacklisted metro station."""
    loc = location.lower()
    return any(name.strip().lower() in loc for name in blacklist if name.strip())


def parse_blacklist(raw: str) -> list[str]:
    """Parse a comma-separated env value into a clean list."""
    return [part.strip() for part in raw.split(",") if part.strip()]
