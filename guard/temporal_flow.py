"""Temporal workflow: batch evaluation that survives crashes.

Each fictional conversation is one activity with automatic retries. If Ollama,
the worker or the whole laptop goes down mid-run, the workflow resumes at the
next unfinished conversation instead of starting over.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from guard.scoring import summarize as score
    from guard.temporal_activities import check_conversation, save_report

TASK_QUEUE = "night-guard"


def summarize(results: list[dict]) -> dict:
    """Same rule as every other evaluation: unreadable analyses are errors, not detections."""
    s = score((r["id"], r["label"], r["expected"],
               {"severity": r["severity"], "analysis_status": r.get("analysis_status", "ok"), "signals": r["got"]})
              for r in results)
    s["retried_conversations"] = [r["id"] for r in results if r["attempt"] > 1]
    return s


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
