from app.services.store_service import (
    hash_password,
    normalize_order_status,
    parse_bearer_token,
    parse_datetime_text,
    verify_password,
)


def test_parse_bearer_token() -> None:
    assert parse_bearer_token("Bearer abc123") == "abc123"
    assert parse_bearer_token("bearer xyz") == "xyz"
    assert parse_bearer_token("Token abc") == ""
    assert parse_bearer_token("") == ""


def test_normalize_order_status_alias() -> None:
    assert normalize_order_status("待确认") == "未完工"
    assert normalize_order_status("已确认") == "已完工"
    assert normalize_order_status("") == "未完工"


def test_password_hash_and_verify_roundtrip() -> None:
    raw = "admin123"
    hashed = hash_password(raw)

    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password(raw, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_parse_datetime_text_formats() -> None:
    assert parse_datetime_text("2026-03-11") is not None
    assert parse_datetime_text("2026-03-11 10:30") is not None
    assert parse_datetime_text("2026/03/11") is not None
    assert parse_datetime_text("not-a-date") is None
