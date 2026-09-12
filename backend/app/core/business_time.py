"""The business day, in the timezone the business is actually open in.

Every datetime column here is naive UTC, and a date somebody picks in a filter
is a date on their wall. Those are eight hours apart, so comparing one against
the other directly puts the boundary of "the 12th" at 08:00 on the morning of
the 12th -- which is what `func.date(occurred_at) <= date_to` was doing.

A fixed offset rather than `ZoneInfo`: Malaysia has never observed daylight
saving, so +08:00 is exact rather than an approximation, and it needs no tzdata
in the image to resolve.

This is deliberately a business timezone and not the viewer's. A range built
from a date has to be anchored somewhere, and the shop's own day is the honest
anchor for a document filter -- an order placed on the 12th in Kuala Lumpur was
placed on the 12th, whatever timezone the person reading the report is sitting
in. The alternative, having the client send instants it computed from its own
clock, would make "the 12th" mean a different span for every viewer.
"""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta, timezone

# Malaysia Standard Time. No daylight saving, ever, so this is exact.
BUSINESS_UTC_OFFSET = timedelta(hours=8)
BUSINESS_TIMEZONE = timezone(BUSINESS_UTC_OFFSET)


def day_starts_at(day: date_type) -> datetime:
    """Midnight at the start of `day`, local, as a naive UTC datetime.

    Naive because that is what the columns hold; comparing an aware datetime
    against them would raise rather than merely be wrong.
    """
    local_midnight = datetime.combine(day, datetime.min.time(), tzinfo=BUSINESS_TIMEZONE)
    return local_midnight.astimezone(timezone.utc).replace(tzinfo=None)


def day_after(day: date_type) -> datetime:
    """Midnight at the *end* of `day`, local, as a naive UTC datetime.

    The exclusive upper bound of an inclusive date range. Expressed as "before
    the next day began" rather than "at 23:59:59" so that nothing occurring in
    the last second of the day is silently dropped.
    """
    return day_starts_at(day + timedelta(days=1))


def local_label(value: datetime | str) -> str:
    """A naive-UTC timestamp written out on the business's own clock.

    For text a person reads directly -- a notification body, an email -- where
    there is no browser to do the converting and no `Z` to tell it to. Anything
    that cannot be read as a timestamp is handed back unchanged: a label is
    never worth raising over.
    """
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BUSINESS_TIMEZONE).strftime("%Y-%m-%d %H:%M MYT")
