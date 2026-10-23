"""Fine-tune Qwen3-8B on Tinker with Night Guard's fictional training data.

Needs TINKER_API_KEY in the environment.
Run from project root:  .venv\\Scripts\\python train\\tinker_sft.py
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from guard.env import load_env  # noqa: E402

load_env()

import chz  # noqa: E402

from tinker_cookbook.renderers import TrainOnWhat
from tinker_cookbook.supervised import train
from tinker_cookbook.supervised.data import FromConversationFileBuilder
from tinker_cookbook.supervised.types import ChatDatasetBuilderCommonConfig

MODEL = "Qwen/Qwen3-8B"
RENDERER = "qwen3_disable_thinking"
HERE = Path(__file__).resolve().parent


def config():
    common = ChatDatasetBuilderCommonConfig(
        model_name_for_tokenizer=MODEL,
        renderer_name=RENDERER,
        max_length=2048,
        batch_size=8,  # smaller batches: the laptop had <1 GB RAM free during v2
        train_on_what=TrainOnWhat.LAST_ASSISTANT_MESSAGE,
    )
    dataset = FromConversationFileBuilder(
        # blobfile rejects Windows drive paths, so pass a relative POSIX-style path.
        common_config=common, file_path=os.path.relpath(HERE / "train.jsonl").replace("\\", "/"), test_size=40
    )
    return chz.Blueprint(train.Config).apply({
        "log_path": str(HERE / "runs" / "night_guard_qwen3_8b_v2"),  # v2: 14 signals, 1000 chats
        "model_name": MODEL,
        "recipe_name": "night_guard_sft",
        "renderer_name": RENDERER,
        "dataset_builder": dataset,
        "learning_rate": 2e-4,
        "lr_schedule": "linear",
        "num_epochs": 2,
        "lora_rank": 16,
        "eval_every": 10,
        "save_every": 20,
    }).make()


if __name__ == "__main__":
    asyncio.run(train.main(config()))
