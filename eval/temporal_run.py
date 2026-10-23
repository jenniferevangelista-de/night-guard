"""Start (or re-attach to) the durable evaluation.

  .venv\\Scripts\\python -m eval.temporal_run            # start and wait
  .venv\\Scripts\\python -m eval.temporal_run --status   # just show progress
"""

import asyncio
import json
import sys
from pathlib import Path

from temporalio.client import Client, WorkflowExecutionStatus

from guard.detector import MODEL
from guard.temporal_flow import TASK_QUEUE, EvalWorkflow

ROOT = Path(__file__).resolve().parent.parent
WF_ID = f"night-guard-eval-{MODEL.replace(':', '-')}"


async def main():
    client = await Client.connect("localhost:7233")
    handle = client.get_workflow_handle(WF_ID)
    try:
        desc = await handle.describe()
        running = desc.status == WorkflowExecutionStatus.RUNNING
    except Exception:
        running = False

    if "--status" in sys.argv:
        print("progress:", await handle.query(EvalWorkflow.progress) if running else "not running")
        return

    if running:
        print(f"Re-attaching to running workflow {WF_ID}: {await handle.query(EvalWorkflow.progress)} done")
    else:
        rows = [json.loads(l) for l in (ROOT / "eval" / "conversations.jsonl").open(encoding="utf-8")]
        handle = await client.start_workflow(EvalWorkflow.run, rows, id=WF_ID, task_queue=TASK_QUEUE)
        print(f"Started {WF_ID} with {len(rows)} conversations")
    print(json.dumps(await handle.result(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
