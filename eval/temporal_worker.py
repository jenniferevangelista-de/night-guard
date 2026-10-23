"""Temporal worker for Night Guard.  Run:  .venv\\Scripts\\python -m eval.temporal_worker"""

import asyncio
import concurrent.futures

from temporalio.client import Client
from temporalio.worker import Worker

from guard.temporal_activities import check_conversation, save_report
from guard.temporal_flow import TASK_QUEUE, EvalWorkflow


async def main():
    client = await Client.connect("localhost:7233")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        worker = Worker(
            client,
            task_queue=TASK_QUEUE,
            workflows=[EvalWorkflow],
            activities=[check_conversation, save_report],
            activity_executor=pool,
        )
        print("Night Guard worker ready (task queue: night-guard)", flush=True)
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
