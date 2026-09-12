"""Timestamps leave this system saying which timezone they are in.

Every datetime column is naive UTC. Sent without a `Z` the browser reads it as
local time by specification, which is why a 16:49 order showed as 08:49 in the
back office. These guard the one place that fixes it, and -- more to the point
-- the three things that place must never do.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.business_time import BUSINESS_TIMEZONE, day_after, day_starts_at, local_label
from app.core.json import UtcJSONResponse, mark_utc


class TestMarkUtc:
    def test_a_naive_timestamp_is_marked(self):
        assert mark_utc("2026-09-12T08:49:20") == "2026-09-12T08:49:20Z"

    def test_fractional_seconds_survive(self):
        assert mark_utc("2026-09-12T08:49:20.123456") == "2026-09-12T08:49:20.123456Z"

    def test_a_space_separator_is_still_a_timestamp(self):
        """Not everything here went through `.isoformat()`."""
        assert mark_utc("2026-09-12 08:49:20") == "2026-09-12 08:49:20Z"

    def test_it_is_idempotent(self):
        """The guard against a second `Z`. Some payloads are built by hand and
        already carry one; running over them again must change nothing."""
        once = mark_utc("2026-09-12T08:49:20")
        assert mark_utc(once) == once == "2026-09-12T08:49:20Z"

    def test_an_offset_is_left_alone(self):
        """Already says which zone it is in -- that is the whole requirement."""
        assert mark_utc("2026-09-12T16:49:20+08:00") == "2026-09-12T16:49:20+08:00"
        assert mark_utc("2026-09-12T08:49:20+00:00") == "2026-09-12T08:49:20+00:00"

    def test_a_plain_date_is_never_touched(self):
        """The landmine. `business_date` stamped as "...T00:00:00Z" reads as the
        previous day on any browser west of Greenwich, and the next save writes
        that wrong day back onto the document."""
        assert mark_utc("2026-09-12") == "2026-09-12"

    def test_a_time_of_day_is_never_touched(self):
        """MyInvois `IssueTime` is "HH:MM:SSZ" and builds its own zone."""
        assert mark_utc("08:49:20") == "08:49:20"

    def test_prose_that_merely_contains_a_timestamp_is_untouched(self):
        """The pattern is anchored at both ends on purpose: a title, a remark or
        an address is not a timestamp, however much of one it quotes."""
        title = "Order SO-2026-00002 raised 2026-09-12T08:49:20 by WhatsApp"
        assert mark_utc(title) == title

    def test_prose_that_ends_in_a_timestamp_is_untouched(self):
        """Separate from the case above, and not redundant: a pattern anchored
        only at the tail passes that one and mangles this one. Notification
        bodies here end in a time."""
        body = "Imported from AutoCount at 2026-09-12T08:49:20"
        assert mark_utc(body) == body

    def test_prose_that_starts_with_a_timestamp_is_untouched(self):
        """The mirror image, for a pattern anchored only at the head."""
        line = "2026-09-12T08:49:20 order received"
        assert mark_utc(line) == line

    def test_it_reaches_into_nested_structures(self):
        payload = {
            "items": [
                {"created_at": "2026-09-12T08:49:20", "business_date": "2026-09-12"},
                {"created_at": "2026-09-12T08:50:00", "confirmed_at": None},
            ],
            "meta": {"generated_at": "2026-09-12T10:00:00", "total": 2},
        }
        marked = mark_utc(payload)
        assert marked["items"][0]["created_at"] == "2026-09-12T08:49:20Z"
        assert marked["items"][0]["business_date"] == "2026-09-12"
        assert marked["items"][1]["confirmed_at"] is None
        assert marked["meta"]["generated_at"] == "2026-09-12T10:00:00Z"
        assert marked["meta"]["total"] == 2

    def test_non_strings_pass_through(self):
        assert mark_utc(None) is None
        assert mark_utc(42) == 42
        assert mark_utc(3.5) == 3.5
        assert mark_utc(True) is True

    def test_the_response_class_marks_what_it_renders(self):
        body = UtcJSONResponse(content={"created_at": "2026-09-12T08:49:20"}).body
        assert b'"2026-09-12T08:49:20Z"' in body


class TestBusinessDay:
    """A date in a filter is a day on a Malaysian wall clock; the column it is
    compared against is naive UTC. Eight hours apart."""

    def test_a_day_starts_at_sixteen_hundred_the_day_before_in_utc(self):
        assert day_starts_at(date(2026, 9, 12)) == datetime(2026, 9, 11, 16, 0, 0)

    def test_the_upper_bound_is_the_start_of_the_next_day(self):
        assert day_after(date(2026, 9, 12)) == datetime(2026, 9, 12, 16, 0, 0)

    def test_the_bound_is_naive(self):
        """Aware would raise against a naive column rather than merely be wrong."""
        assert day_starts_at(date(2026, 9, 12)).tzinfo is None

    def test_the_range_is_exactly_one_day(self):
        day = date(2026, 9, 12)
        assert day_after(day) - day_starts_at(day) == timedelta(days=1)

    def test_a_movement_just_after_local_midnight_falls_in_the_right_day(self):
        """03:00 in Kuala Lumpur is 19:00 UTC the previous day. Compared raw it
        landed in the 11th while the screen said the 12th."""
        occurred_at = datetime(2026, 9, 11, 19, 0, 0)  # 2026-09-12 03:00 MYT
        assert day_starts_at(date(2026, 9, 12)) <= occurred_at < day_after(date(2026, 9, 12))

    def test_the_last_second_of_a_day_is_inside_it(self):
        occurred_at = datetime(2026, 9, 12, 15, 59, 59)  # 2026-09-12 23:59:59 MYT
        assert occurred_at < day_after(date(2026, 9, 12))

    def test_the_first_second_of_the_next_day_is_outside_it(self):
        occurred_at = datetime(2026, 9, 12, 16, 0, 0)  # 2026-09-13 00:00:00 MYT
        assert not occurred_at < day_after(date(2026, 9, 12))

    def test_a_month_boundary_rolls(self):
        assert day_after(date(2026, 9, 30)) == datetime(2026, 9, 30, 16, 0, 0)
        assert day_starts_at(date(2026, 10, 1)) == datetime(2026, 9, 30, 16, 0, 0)


class TestLocalLabel:
    """For text a person reads directly: no browser, no `Z` to act on."""

    def test_a_naive_utc_string_is_written_on_the_shop_clock(self):
        assert local_label("2026-09-13T00:05:00") == "2026-09-13 08:05 MYT"

    def test_a_zoned_string_is_converted_not_relabelled(self):
        assert local_label("2026-09-12T08:49:20+00:00") == "2026-09-12 16:49 MYT"

    def test_a_datetime_works_as_well_as_a_string(self):
        assert local_label(datetime(2026, 9, 13, 0, 5, 0)) == "2026-09-13 08:05 MYT"

    def test_something_that_is_not_a_timestamp_comes_back_unchanged(self):
        """A notification body is never worth raising over."""
        assert local_label("") == ""
        assert local_label("not a date") == "not a date"

    def test_it_agrees_with_the_offset_it_claims(self):
        moment = datetime(2026, 9, 12, 8, 49, 20, tzinfo=timezone.utc)
        assert moment.astimezone(BUSINESS_TIMEZONE).strftime("%H:%M") == "16:49"


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-12T08:49:20",
        "2026-09-12T08:49:20.5",
        "2026-09-12 08:49:20",
    ],
)
def test_everything_marked_parses_back_as_utc(value):
    """The point of the exercise: a browser, or anything else, can now read the
    instant rather than guess at it."""
    parsed = datetime.fromisoformat(mark_utc(value).replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
