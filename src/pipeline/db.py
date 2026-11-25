"""Database connection helper that survives a database that is still starting up."""

import logging
import time

import psycopg2

log = logging.getLogger(__name__)


def get_connection(settings, max_wait_s=60):
    """Return a NON-autocommit connection, retrying until the DB accepts connections.

    Waits 2s, 4s, 8s, then 10s between attempts, and re-raises the last error once
    max_wait_s has passed, so a truly dead database still fails loudly.
    """
    deadline = time.monotonic() + max_wait_s  # monotonic clock: immune to system time changes
    attempt = 0
    while True:
        attempt += 1
        try:
            return psycopg2.connect(
                host=settings.db_host,
                port=settings.db_port,
                user=settings.db_user,
                password=settings.db_password,
                dbname=settings.db_name,
                connect_timeout=5,  # do not hang forever on one attempt
            )
        except psycopg2.OperationalError as exc:
            if time.monotonic() >= deadline:
                raise  # out of time: let the caller see the real error
            delay = min(2**attempt, 10)  # exponential backoff, capped at 10 seconds
            log.warning(
                "database not ready (attempt %s): %s; retrying in %ss",
                attempt,
                str(exc).strip(),
                delay,
            )
            time.sleep(delay)
