import pytest
import requests
from tenacity import wait_none

from pipeline.api_client import SocrataClient


class FakeResponse:
    def __init__(self, status, payload=None, headers=None):
        self.status_code = status
        self._payload = payload or []
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")


def test_fetch_page_retries_on_500_then_succeeds(monkeypatch):
    monkeypatch.setattr(SocrataClient.fetch_page.retry, "wait", wait_none())
    client = SocrataClient("abc", page_size=2)
    responses = iter(
        [
            FakeResponse(500),
            FakeResponse(500),
            FakeResponse(200, [{"unique_key": "1"}]),
        ]
    )
    monkeypatch.setattr(client.session, "get", lambda *a, **k: next(responses))
    assert client.fetch_page(0) == [{"unique_key": "1"}]


def test_fetch_page_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(SocrataClient.fetch_page.retry, "wait", wait_none())
    monkeypatch.setattr("pipeline.api_client.time.sleep", lambda s: None)
    client = SocrataClient("abc", page_size=2)
    responses = iter(
        [
            FakeResponse(429, headers={"Retry-After": "1"}),
            FakeResponse(200, [{"unique_key": "2"}]),
        ]
    )
    monkeypatch.setattr(client.session, "get", lambda *a, **k: next(responses))
    assert client.fetch_page(0) == [{"unique_key": "2"}]


def test_fetch_page_does_not_retry_on_400(monkeypatch):
    client = SocrataClient("abc")
    monkeypatch.setattr(client.session, "get", lambda *a, **k: FakeResponse(400))
    with pytest.raises(RuntimeError):
        client.fetch_page(0)


def test_fetch_page_retries_on_incomplete_read(monkeypatch):
    """A truncated response (the April failure) must be retried, not crash the run."""
    monkeypatch.setattr(SocrataClient.fetch_page.retry, "wait", wait_none())
    client = SocrataClient("abc")
    items = iter(
        [
            requests.exceptions.ChunkedEncodingError("IncompleteRead"),
            FakeResponse(200, [{"unique_key": "1"}]),
        ]
    )

    def fake_get(*args, **kwargs):
        item = next(items)
        if isinstance(item, Exception):
            raise item  # simulate the connection dying mid-response
        return item

    monkeypatch.setattr(client.session, "get", fake_get)
    assert client.fetch_page(0) == [{"unique_key": "1"}]
