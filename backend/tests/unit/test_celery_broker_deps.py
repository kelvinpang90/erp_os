"""Guard the Celery broker dependency set.

kombu (pulled in by celery) checks the installed redis-py version when it
builds a Redis client. kombu 5.7.0 requires redis-py >= 6.1 while we pin
redis 5.2.1, and an unpinned rebuild picked it up: the worker and beat then
crash-looped on startup. Building the client class needs no Redis server, so
this fails in CI the moment the resolved versions stop being compatible.
"""

from __future__ import annotations

from kombu.transport import redis as kombu_redis


def test_kombu_redis_transport_accepts_installed_redis_py() -> None:
    channel = object.__new__(kombu_redis.Channel)

    # Raises kombu.exceptions.VersionMismatch when redis-py is too old for kombu.
    client_cls = channel._get_client()

    assert client_cls is not None
