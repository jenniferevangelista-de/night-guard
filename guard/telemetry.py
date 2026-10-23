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


def _scrub(event, _hint):
    """Drop anything that could contain chat text before an event leaves the computer."""
    event.pop("request", None)
    for k in ("extra", "contexts"):
        if isinstance(event.get(k), dict):
            event[k] = {kk: vv for kk, vv in event[k].items() if kk in SAFE_KEYS or kk in ("trace", "runtime", "os")}
    for ex in (event.get("exception") or {}).get("values", []):
        for fr in (ex.get("stacktrace") or {}).get("frames", []):
            fr.pop("vars", None)  # local variables could hold messages
    return event


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
