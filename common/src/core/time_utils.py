from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_iso_z(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def now_iso_z() -> str:
    return to_iso_z(utcnow())


def parse_iso_z(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
