"""Public demo budget checks use only fake model/provider calls."""
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from guard.demo_budget import DemoBudget
from guard import server


def test_hourly_global_and_client_limits_expire_without_refunding_provider_errors():
    now = [0.0]
    budget = DemoBudget(hourly=3, per_client=2, concurrent=1, clock=lambda: now[0])
    with pytest.raises(ValueError):
        with budget.reserve("a"):
            raise ValueError("simulated provider failure")
    with budget.reserve("a"):
        pass
    with pytest.raises(HTTPException) as exc:
        with budget.reserve("a"):
            pytest.fail("per-client limit bypassed")
    assert exc.value.status_code == 429 and exc.value.headers["Retry-After"] == "3600"
    with budget.reserve("b"):
        pass
    with pytest.raises(HTTPException):
        with budget.reserve("c"):
            pytest.fail("global limit bypassed")
    now[0] = 3600
    with budget.reserve("a"):
        pass


def test_simultaneous_requests_cannot_overrun_concurrency_or_leak_slots():
    budget = DemoBudget(hourly=30, per_client=30, concurrent=2)
    held = threading.Event()
    release = threading.Event()
    entrants = []
    lock = threading.Lock()

    def attempt(i):
        try:
            with budget.reserve(str(i)):
                with lock:
                    entrants.append(i)
                    if len(entrants) == 2:
                        held.set()
                assert release.wait(5)
                return 200
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=12) as pool:
        first = [pool.submit(attempt, i) for i in range(2)]
        assert held.wait(5)
        rejected = list(pool.map(attempt, range(2, 12)))
        release.set()
        assert [f.result() for f in first] == [200, 200]
    assert rejected == [429] * 10
    with budget.reserve("after"):
        pass


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setattr(server, "DEMO", True)
    monkeypatch.setattr(server, "_analysis_budget", DemoBudget(hourly=3, per_client=2, concurrent=1))
    monkeypatch.setattr(server, "_link_budget", DemoBudget(hourly=3, per_client=2, concurrent=1))
    calls = []

    def fake_model(messages, lang="en"):
        calls.append(messages)
        return {"severity": "none", "signals": [], "links": [], "summary": "fictional test"}

    monkeypatch.setattr(server, "analyze", fake_model)
    return TestClient(server.app), calls


def test_api_analysis_limit_prevents_model_calls_and_does_not_trust_forwarded_header(demo):
    client, calls = demo
    body = {"messages": [{"from": "them", "text": "fictional"}]}
    for i in range(2):
        assert client.post("/api/analyze", json=body).status_code == 200
    response = client.post("/api/analyze", json=body, headers={"X-Forwarded-For": "different-client"})
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0
    assert len(calls) == 2


@pytest.mark.parametrize("body", [
    {"messages": [{"from": "them", "text": "x" * 2000}] * 3},
    {"messages": [{"from": "them", "text": "x" * 60, "name": "n" * 60}] * 40},
    # Two-digit message indexes and CONTACT separators count toward the limit.
    {"messages": [{"from": "them", "text": "x" * 54}] * 60},
    {"text": "fictional", "lang": "x" * 13},
    {"text": "fictional", "app": "x" * 61},
])
def test_oversized_model_inputs_are_rejected_before_model_or_budget(demo, body):
    client, calls = demo
    assert client.post("/api/analyze", json=body).status_code == 422
    assert calls == [] and not server._analysis_budget._calls


def test_local_analysis_retains_structured_capacity_without_cloud_quota(demo, monkeypatch):
    client, calls = demo
    monkeypatch.setattr(server, "DEMO", False)
    body = {"messages": [{"from": "them", "text": "x" * 2000}] * 3}
    assert all(client.post("/api/analyze", json=body).status_code == 200 for _ in range(4))
    assert len(calls) == 4 and not server._analysis_budget._calls


def test_demo_link_limit_prevents_external_provider_calls(demo, monkeypatch):
    from guard import link_check
    client, _ = demo
    calls = []
    monkeypatch.setattr(link_check, "enabled", lambda: {"browserbase": True, "serpapi": True})
    monkeypatch.setattr(link_check, "check_link", lambda *args: calls.append(args) or {"status": "fictional"})
    body = {"url": "https://fictional.example"}
    assert client.post("/api/link/check", json=body).status_code == 200
    assert client.post("/api/link/check", json=body).status_code == 200
    assert client.post("/api/link/check", json=body).status_code == 429
    assert len(calls) == 2
