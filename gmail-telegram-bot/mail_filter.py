"""Pure e-mail classification logic (no network, easy to unit-test)."""

IMPORTANT_KEYWORDS = (
    "оплата",
    "подписка",
    "счет",
    "отклик",
    "приглашение",
    "одобрен",
    "чек",
    "заказ",
    "пароль",
    "код",
)
UNWANTED_KEYWORDS = ("скидки", "акция", "распродажа", "новости", "unsub", "unsubscribe")


def classify(subject: str, snippet: str) -> str:
    """Return 'important', 'unwanted' or 'ignored'. Important wins over unwanted."""
    text = f"{subject} {snippet}".lower()
    if any(kw in text for kw in IMPORTANT_KEYWORDS):
        return "important"
    if any(kw in text for kw in UNWANTED_KEYWORDS):
        return "unwanted"
    return "ignored"
