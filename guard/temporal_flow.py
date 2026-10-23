"""Temporal workflow: batch evaluation that survives crashes.

Each fictional conversation is one activity with automatic retries. If Ollama,
the worker or the whole laptop goes down mid-run, the workflow resumes at the
next unfinished conversation instead of starting over.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from guard.temporal_activities import check_conversation, save_report

TASK_QUEUE = "night-guard"


def summarize(results: list[dict]) -> dict:
    tp = fp = fn = tn = stp = sfp = sfn = 0
    for r in results:
        flagged, risky = r["severity"] != "none", r["label"] == "risky"
        got, exp = set(r["got"]), set(r["expected"])
        if risky and flagged: tp += 1
        elif risky: fn += 1
        elif flagged: fp += 1
        else: tn += 1
        stp += len(got & exp); sfp += len(got - exp); sfn += len(exp - got)
    return {
        "n": len(results),
        "risky_flagged": f"{tp}/{tp + fn}",
        "false_alarms": f"{fp}/{fp + tn}",
        "signal_precision": round(stp / max(1, stp + sfp), 3),
        "signal_recall": round(stp / max(1, stp + sfn), 3),
        "retried_conversations": [r["id"] for r in results if r["attempt"] > 1],
    }


@workflow.defn
class EvalWorkflow:
    def __init__(self) -> None:
        self.done = 0
        self.total = 0

    @workflow.query
    def progress(self) -> str:
        return f"{self.done}/{self.total}"

    @workflow.run
    async def run(self, rows: list[dict]) -> dict:
        self.total = len(rows)
        results = []
        for row in rows:  # one at a time: a single laptop GPU
            r = await workflow.execute_activity(
                check_conversation,
                row,
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=3),
                    backoff_coefficient=2.0,
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=0,  # keep trying until Ollama is back
                ),
            )
            results.append(r)
            self.done += 1
        summary = summarize(results)
        report = {"model": results[0]["model"] if results else "", "summary": summary, "results": results}
        await workflow.execute_activity(save_report, report, start_to_close_timeout=timedelta(seconds=30))
        return summary
