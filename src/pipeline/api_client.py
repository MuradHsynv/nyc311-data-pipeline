"""Socrata API client: pagination, retries with backoff, and 429 handling."""

import logging
import time

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = logging.getLogger(__name__)


class RetryableAPIError(Exception):
    """Raised for transient failures worth retrying: timeouts, network errors, 429, 5xx."""


class SocrataClient:
    """Fetches pages of records from one Socrata dataset."""

    def __init__(self, dataset_id, app_token=None, page_size=5000, timeout=30):
        self.url = f"https://data.cityofnewyork.us/resource/{dataset_id}.json"
        self.page_size = page_size
        self.timeout = timeout
        # A Session reuses the TCP connection, which is much faster over hundreds of pages.
        self.session = requests.Session()
        if app_token:
            # Sending X-App-Token raises our Socrata rate limit considerably.
            self.session.headers["X-App-Token"] = app_token

    # On RetryableAPIError, tenacity waits 1s, 2s, 4s... (up to 60s) for up to 6 attempts,
    # then re-raises the original error so the run fails loudly instead of silently dropping data.
    @retry(
        retry=retry_if_exception_type(RetryableAPIError),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(6),
        reraise=True,
    )
    def fetch_page(self, offset, where=None):
        """Return one page (list of dicts) starting at offset, optionally filtered by SoQL where."""
        params = {
            "$limit": self.page_size,
            "$offset": offset,
            # Stable, unique ordering is REQUIRED so pages never overlap or skip rows.
            "$order": "created_date, unique_key",
        }
        if where:
            params["$where"] = where

        try:
            resp = self.session.get(self.url, params=params, timeout=self.timeout)
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise RetryableAPIError(f"network error: {exc}") from exc

        if resp.status_code == 429:
            # Respect the server's Retry-After header (default 5s) before retrying.
            try:
                wait_s = int(resp.headers.get("Retry-After", "5"))
            except ValueError:
                wait_s = 5
            log.warning("rate limited (429), sleeping %ss", wait_s)
            time.sleep(wait_s)
            raise RetryableAPIError("rate limited (429)")

        if resp.status_code >= 500:
            raise RetryableAPIError(f"server error {resp.status_code}")

        # Any other 4xx (like 400 Bad Request) is our bug: fail fast, do not retry.
        resp.raise_for_status()
        return resp.json()

    def iter_pages(self, where=None, start_offset=0):
        """Yield (rows, next_offset) page by page, starting at start_offset (used for resuming)."""
        offset = start_offset
        while True:
            rows = self.fetch_page(offset, where)
            if not rows:
                return
            offset += len(rows)
            yield rows, offset
            if len(rows) < self.page_size:
                # A short page means we reached the end of the window.
                return
