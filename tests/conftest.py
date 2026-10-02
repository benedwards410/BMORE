import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, status=200, body=None, text=None):
        self.status_code = status
        self._body = body
        self.text = text if text is not None else json.dumps(body or {})

    def json(self):
        return self._body if self._body is not None else json.loads(self.text)


class FakeHttp:
    """Route requests by URL substring to canned responses; records every call."""

    def __init__(self, routes: dict[str, FakeResponse]):
        self.routes = routes
        self.calls: list[tuple[str, str, dict]] = []

    def _route(self, method, url, kw):
        self.calls.append((method, url, kw))
        for needle, resp in self.routes.items():
            if needle in url:
                return resp
        return FakeResponse(404, text="not found")

    def get(self, url, **kw):
        return self._route("GET", url, kw)

    def post(self, url, **kw):
        return self._route("POST", url, kw)


def load(name):
    p = FIXTURES / name
    return json.loads(p.read_text()) if p.suffix == ".json" else p.read_text()


@pytest.fixture
def fixture():
    return load
