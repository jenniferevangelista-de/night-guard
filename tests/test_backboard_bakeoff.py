"""Backboard request isolation, failure budget and shared scoring; no keys or network."""
import json

import httpx
import pytest

from train import backboard_bakeoff as bakeoff


ROWS = [
    {"id": "risk", "label": "risky", "signals": ["secrecy"], "lang": "en",
     "messages": [{"from": "them", "text": "don't tell your parents"}]},
    {"id": "safe", "label": "safe", "signals": [], "lang": "en",
     "messages": [{"from": "them", "text": "gg, nice game"}]},
]


def response(http_status=200, **data):
    return httpx.Response(http_status, json=data, request=httpx.Request("POST", bakeoff.API))


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setenv("BACKBOARD_API_KEY", "fictional-test-key")
    monkeypatch.setattr(bakeoff, "load_env", lambda: None)
    monkeypatch.setattr(bakeoff.time, "sleep", lambda seconds: None)

    def no_network(*args, **kwargs):
        raise AssertionError("Unit tests must not call the network")

    monkeypatch.setattr(bakeoff.httpx, "post", no_network)


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    (tmp_path / "eval").mkdir()
    (tmp_path / "train").mkdir()
    (tmp_path / "eval" / "conversations.jsonl").write_text(
        "\n".join(json.dumps(row) for row in ROWS), encoding="utf-8")
    monkeypatch.setattr(bakeoff, "ROOT", tmp_path)
    return tmp_path


def test_each_case_creates_new_thread_with_same_prompt(monkeypatch):
    requests = []

    def post(url, **kwargs):
        requests.append((url, kwargs))
        return response(content='{"signals": [], "summary": "fine"}', status="COMPLETED",
                        thread_id=f"thread-{len(requests)}", assistant_id="generated-assistant")

    monkeypatch.setattr(bakeoff.httpx, "post", post)
    for row in ROWS:
        assert bakeoff.ask("model/test", row)[2] is None
    assert len(requests) == 2
    for url, kwargs in requests:
        assert url == "https://app.backboard.io/api/threads/messages"
        body = kwargs["json"]
        assert "thread_id" not in body and "assistant_id" not in body
        assert body["system_prompt"] == bakeoff.SYSTEM
        assert body["llm_provider"] == "openrouter" and body["model_name"] == "model/test"
        assert body["memory"] == "off" and body["web_search"] == "off"
        assert body["json_output"] is True and body["stream"] is False
    assert "don't tell" in requests[0][1]["json"]["content"]
    assert "don't tell" not in requests[1][1]["json"]["content"]


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 405, 422])
def test_permanent_error_stops_before_remaining_cases_or_models(dataset, monkeypatch, capsys, status):
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        return response(status, detail="must not expose this body or the test key")

    monkeypatch.setattr(bakeoff.httpx, "post", post)
    assert bakeoff.main(["model/first", "model/second"]) == 1
    assert len(calls) == 1
    captured = capsys.readouterr()
    assert f"HTTP {status}" in captured.err
    assert "fictional-test-key" not in captured.err and "must not expose" not in captured.err
    assert not list((dataset / "train").glob("backboard_*.json"))


def test_repeated_rate_limit_returns_explicit_error(monkeypatch):
    calls = []

    def post(*args, **kwargs):
        calls.append(1)
        return response(429)

    monkeypatch.setattr(bakeoff.httpx, "post", post)
    content, latency, error = bakeoff.ask("model/test", ROWS[0])
    assert len(calls) == 3
    assert content == "" and error == "HTTP_429" and latency >= 0


def test_temporary_server_failure_retries_then_succeeds(monkeypatch):
    replies = iter([response(503), response(content='{"signals": [], "summary": "fine"}')])
    monkeypatch.setattr(bakeoff.httpx, "post", lambda *a, **k: next(replies))
    assert bakeoff.ask("model/test", ROWS[0])[2] is None


def test_repeated_timeout_is_an_error_not_a_detection(dataset, monkeypatch):
    def post(*args, **kwargs):
        raise httpx.ReadTimeout("not logged")

    monkeypatch.setattr(bakeoff.httpx, "post", post)
    result = bakeoff.run("model/test", limit=1)
    assert result["schema_valid"] == 0
    assert result["summary"]["coverage"] == "0/1"
    assert result["summary"]["counts"]["tp"] == 0
    assert result["summary"]["errors"]["risky"] == 1
    assert result["cases"][0]["error"] == "ReadTimeout"


@pytest.mark.parametrize("reply", [[], {"content": None}, {"content": 42}])
def test_unexpected_contract_fails_fast(monkeypatch, reply):
    monkeypatch.setattr(bakeoff.httpx, "post", lambda *a, **k: httpx.Response(
        200, json=reply, request=httpx.Request("POST", bakeoff.API)))
    with pytest.raises(bakeoff.BackboardConfigError):
        bakeoff.ask("model/test", ROWS[0])


def test_smoke_exports_separately_and_keeps_same_scoring(dataset, monkeypatch, capsys):
    def post(*args, **kwargs):
        return response(content=json.dumps({"signals": [
            {"id": "secrecy", "message_index": 0, "quote": "don't tell your parents"}],
            "summary": "The contact asks for secrecy."}))

    monkeypatch.setattr(bakeoff.httpx, "post", post)
    assert bakeoff.main(["--limit", "1", "model/test"]) == 0
    result = json.loads((dataset / "train" / "backboard_test_smoke_1.json").read_text())
    assert result["n"] == 1 and result["dataset_n"] == 2 and result["evaluation"] == "smoke"
    assert result["summary"]["counts"]["tp"] == 1
    assert result["summary"]["signal_precision"] == 1
    assert "schema 1/1" in capsys.readouterr().out
    summary = (dataset / "train" / "backboard_smoke_1_summary.md").read_text()
    assert "Smoke test only" in summary and "model/test" in summary and "1/1" in summary
    assert not (dataset / "train" / "backboard_test.json").exists()


def test_invalid_model_json_is_scored_as_error(dataset, monkeypatch):
    monkeypatch.setattr(bakeoff.httpx, "post", lambda *a, **k: response(content="not JSON"))
    result = bakeoff.run("model/test")
    assert result["summary"]["coverage"] == "0/2"
    assert result["summary"]["counts"]["tp"] == result["summary"]["counts"]["tn"] == 0
    assert result["summary"]["errors"] == {"risky": 1, "safe": 1}


def test_missing_key_prevents_any_request(monkeypatch):
    monkeypatch.delenv("BACKBOARD_API_KEY")
    with pytest.raises(bakeoff.BackboardConfigError, match="BACKBOARD_API_KEY"):
        bakeoff.ask("model/test", ROWS[0])


def test_invalid_limit_exits_before_loading_env(monkeypatch):
    monkeypatch.setattr(bakeoff, "load_env", lambda: pytest.fail("must not read .env"))
    with pytest.raises(SystemExit) as exc:
        bakeoff.main(["--limit", "0"])
    assert exc.value.code == 2
