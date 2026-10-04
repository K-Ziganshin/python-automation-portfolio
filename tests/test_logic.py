from avito_filters import is_blacklisted, parse_blacklist
from mail_filter import classify
from schedule_notifier import build_schedule, find_row


def test_classify_important_wins_over_unwanted():
    assert classify("Скидки на заказ", "") == "important"


def test_classify_unwanted_and_ignored():
    assert classify("Распродажа", "") == "unwanted"
    assert classify("Привет", "как дела") == "ignored"


def test_blacklist():
    assert is_blacklisted("м. Девяткино, 5 мин", ["девяткино"])
    assert not is_blacklisted("м. Парнас", ["Девяткино"])
    assert not is_blacklisted("anything", [""])
    assert parse_blacklist(" A, B ,,") == ["A", "B"]


def test_schedule():
    rows = [["x"], ["name", "1.10", "2.10"], ["Ivan", "D", ""]]
    row = find_row(rows, "Ivan")
    assert build_schedule(rows[1], row) == ["name - Ivan", "1.10 - D"]
    assert find_row(rows, "Nobody") is None
