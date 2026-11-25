"""Socrata API client: pagination, retries with backoff, and 429 handling."""

import requests


class SocrataClient:
    """Fetches pages of records from one Socrata dataset."""

    def __init__(self, dataset_id, app_token=None, page_size=5000, timeout=30):
        self.url = f"https://data.cityofnewyork.us/resource/{dataset_id}.json"
        self.page_size = page_size
        self.timeout = timeout
        # A Session reuses the TCP connection, which is much faster over hundreds of pages.
        self.session = requests.Session()
        if app_token:
            # Sending X-App-Token throttles by app instead of IP, raising the rate limit.
            self.session.headers["X-App-Token"] = app_token

    def fetch_page(self, offset, where=None):
        """Return one page (list of dicts) starting at offset, optionally filtered by SoQL where."""
        params = {
            "$limit": self.page_size,
            "$offset": offset,
            # Stable, unique ordering prevents rows from shifting, overlapping, or getting skipped.
            "$order": "created_date, unique_key",
        }
        if where:
            params["$where"] = where

        resp = self.session.get(self.url, params=params, timeout=self.timeout)
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
