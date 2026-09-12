"""Say which timezone a timestamp is in, on the way out.

Every datetime column in this system is naive UTC. The API used to serialise
them as `"2026-09-12T08:49:20"` -- no `Z`, no offset -- and the browser is then
entitled to read that as local time, because that is what the ECMAScript
specification says an offset-less date-time means. On a UTC+8 screen the UTC
digits were printed verbatim, so an order placed at 16:49 in Kuala Lumpur read
08:49 in the back office. Nothing was ever converted; the instant was simply
lost in transit.

The fix is to say what the value already is. One `Z` on the wire, and both
`new Date()` and `dayjs()` convert correctly with no change to any page.

**Why here and not on the schemas.** There are 30 schema modules and 123
`response_model` declarations. A `field_serializer` would have to reach all of
them, through a base class every schema remembers to inherit -- and the one that
forgets is silently wrong, today and every time somebody adds a schema. This
runs at the single point every JSON response passes through, so it cannot miss
one and does not need to be maintained.

**Why `fullmatch`.** The whole string must be a naive ISO timestamp and nothing
else. A title, a remark, an address -- anything with other characters around it
-- is not touched. A field whose entire value is a timestamp is a timestamp.

`fullmatch` rather than anchors on the pattern: with `re.match` a leading `^` is
silently redundant, so only the `$` would have been load-bearing, and a reader
cannot tell which half is doing the work.

Three properties fall out of the pattern rather than out of anybody remembering
them:

- **Idempotent.** A value that already carries `Z` or `+08:00` does not match,
  so a second pass changes nothing.
- **Dates are safe.** `"2026-09-12"` has no `T`, so it does not match.
  `business_date` matters: stamped as `"...T00:00:00Z"` it would read as the
  previous day on any browser west of Greenwich, and quietly rewrite the
  document date on the next save.
- **Times of day are safe.** `"08:49:20"` has no date, so it does not match.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi.responses import JSONResponse

# A naive ISO datetime and nothing else. Both `T` and space separators, because
# a hand-built payload somewhere may not have gone through `.isoformat()`.
NAIVE_ISO_DATETIME = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?")


def mark_utc(value: Any) -> Any:
    """Append `Z` to every naive ISO timestamp in an already-JSON-able value.

    Recurses through dicts and lists. Everything else is returned untouched --
    including strings that merely contain a timestamp rather than being one.
    """
    if isinstance(value, str):
        return value + "Z" if NAIVE_ISO_DATETIME.fullmatch(value) else value
    if isinstance(value, dict):
        return {key: mark_utc(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mark_utc(item) for item in value]
    return value


class UtcJSONResponse(JSONResponse):
    """The application's JSON response, with its timestamps saying so.

    By the time `render` is called FastAPI has already turned datetimes into
    strings, through the response model, so this works on the wire format rather
    than on Python objects. That is the point: it sees exactly what the browser
    will see, including anything hand-built that never passed through a schema.
    """

    def render(self, content: Any) -> bytes:
        return super().render(mark_utc(content))
