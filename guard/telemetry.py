"""Sentry agent tracing for Night Guard, without chat content.

Enabled only if SENTRY_DSN is set. Spans follow Sentry's AI agent conventions (gen_ai.*) so the
"agent run -> model call" tree shows up in Sentry's AI Agents view, but they carry only numbers and
labels: model name, backend, latency, number of messages, severity, signal ids. Never messages,
quotes, names or prompts. send_default_pii is off and every event is scrubbed before sending.
"""

import contextlib
import os

try:
    import sentry_sdk
except ImportError:  # the cloud demo installs a minimal set of packages
    sentry_sdk = None

ENABLED = False
SAFE_KEYS = {"model", "backend", "app", "severity", "signals", "n_messages", "status", "lang", "latency_s"}
SAFE_SPAN_KEYS = SAFE_KEYS | {"http.response.status_code", "http.request.method", "thread.id", "thread.name"}
SAFE_TOP = {"event_id", "timestamp", "start_timestamp", "level", "platform", "logger", "release", "environment",
            "sdk", "type", "transaction", "transaction_info", "measurements", "_meta"}
SAFE_FRAME = {"filename", "abs_path", "function", "module", "lineno", "colno", "in_app"}
OUR_PREFIX = "night-guard:"   # only our own fixed messages are kept as text


def _allow(event):
    """Allowlist scrubber: keep only fields known to hold no chat text; drop everything else."""
    out = {k: v for k, v in event.items() if k in SAFE_TOP}
    ctx = event.get("contexts") or {}
    out["contexts"] = {k: v for k, v in ctx.items() if k in ("trace", "runtime", "os")}
    if isinstance(out["contexts"].get("trace"), dict):
        tr = out["contexts"]["trace"]
        tr["data"] = {k: v for k, v in (tr.get("data") or {}).items() if k in SAFE_SPAN_KEYS}
    out["extra"] = {k: v for k, v in (event.get("extra") or {}).items() if k in SAFE_KEYS}
    msg = event.get("message") or (event.get("logentry") or {}).get("message") or ""
    if isinstance(msg, str) and msg.startswith(OUR_PREFIX):
        out["message"] = msg
    if event.get("exception"):
        vals = []
        for ex in (event["exception"].get("values") or []):
            frames = [{k: v for k, v in fr.items() if k in SAFE_FRAME}
                      for fr in ((ex.get("stacktrace") or {}).get("frames") or [])]
            vals.append({"type": ex.get("type"), "value": f"{ex.get('type')} (details removed)",
                         "stacktrace": {"frames": frames}, "mechanism": ex.get("mechanism")})
        out["exception"] = {"values": vals}
    if event.get("spans"):
        out["spans"] = [{**{k: v for k, v in sp.items() if k not in ("data", "tags")},
                         "data": {k: v for k, v in (sp.get("data") or {}).items() if k in SAFE_SPAN_KEYS}}
                        for sp in event["spans"]]
    return out  # request, user, breadcrumbs, server_name, tags and anything new are dropped


def _scrub(event, _hint):
    return _allow(event)


NOISY = ("/api/guard/", "/api/family/notify", "/api/health", "/web/", "/api/family/rules", "/api/auth/me")


def _sampler(ctx):
    """Keep agent runs and real requests; drop the UI's status polling (every 3 s)."""
    name = (ctx.get("transaction_context") or {}).get("name", "") or ""
    return 0.0 if any(n in name for n in NOISY) else 1.0


def init():
    global ENABLED
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn or sentry_sdk is None:
        return False
    sentry_sdk.init(
        dsn=dsn,
        traces_sampler=_sampler,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        before_send=_scrub,
        before_send_transaction=_scrub,
        max_breadcrumbs=0,
        server_name="night-guard",  # not the computer's name
        environment=os.environ.get("NG_BACKEND", "ollama"),
        release="night-guard@0.3",
    )
    ENABLED = True
    return True


@contextlib.contextmanager
def span(op, name, **data):
    """A tracing span with safe attributes only (numbers and labels)."""
    if not ENABLED:
        yield None
        return
    with sentry_sdk.start_span(op=op, name=name) as s:
        for k, v in data.items():
            s.set_data(k, v)
        yield s


@contextlib.contextmanager
def transaction(name, **data):
    if not ENABLED:
        yield None
        return
    with sentry_sdk.start_transaction(op="gen_ai.invoke_agent", name=name) as t:
        for k, v in data.items():
            t.set_data(k, v)
        yield t
