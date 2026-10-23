"""Cloud demo backend: the Tinker fine-tuned Qwen3-8B instead of local Ollama.

Used only by the public demo on Render (NG_BACKEND=tinker), which runs on
fictional examples. The real Night Guard runs locally with Gemma.
Light on purpose: tinker SDK + a tokenizer, no torch.
"""

import json
import os
import threading

from tinker import ServiceClient, types
from transformers import AutoTokenizer

BASE_MODEL = "Qwen/Qwen3-8B"
FT_PATH = os.environ.get(
    "NG_TINKER_MODEL_PATH",
    "tinker://c8aba687-d187-5640-b9ab-9e58998bc9be:train:0/sampler_weights/final",
)
IM_END = 151645  # Qwen <|im_end|>


def _clean_key():
    """Tolerate common paste mistakes in the dashboard: spaces, quotes, 'TINKER_API_KEY=' prefix."""
    raw = os.environ.get("TINKER_API_KEY", "")
    key = raw.strip().strip('"').strip("'").strip()
    if "=" in key and not key.startswith("tml-"):
        key = key.split("=", 1)[1].strip().strip('"').strip("'")
    if key and not key.startswith("tml-"):
        key = "tml-" + key.removeprefix("tml").lstrip("-")  # prefix lost when copying
    if key:
        os.environ["TINKER_API_KEY"] = key
    # Diagnostic without revealing the key.
    print(f"[night-guard] TINKER_API_KEY set={bool(key)} len={len(key)} starts_tml={key.startswith('tml-')}", flush=True)


from .env import load_env  # noqa: E402  (local runs read .env; on Render the dashboard sets it)

load_env()
_clean_key()

_lock = threading.RLock()  # re-entrant: _client() calls _get() while holding it
_state = {}


def _get(key, factory):
    with _lock:
        if key not in _state:
            _state[key] = factory()
        return _state[key]


def _tokenizer():
    return _get("tok", lambda: AutoTokenizer.from_pretrained(BASE_MODEL))


def _client(model_path):
    def make():
        sc = _get("service", ServiceClient)
        return sc.create_sampling_client(base_model=BASE_MODEL, model_path=model_path)
    return _get(f"client:{model_path}", make)


def _prompt(messages):
    """Qwen3 chat format with thinking disabled (same as tinker_cookbook's renderer)."""
    text = "".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages)
    text += "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    return types.ModelInput.from_ints(_tokenizer().encode(text, add_special_tokens=False))


def generate(messages, fine_tuned=True, max_tokens=400, temperature=0.0):
    client = _client(FT_PATH if fine_tuned else None)
    params = types.SamplingParams(max_tokens=max_tokens, temperature=temperature, stop=[IM_END])
    res = client.sample(prompt=_prompt(messages), num_samples=1, sampling_params=params).result()
    return _tokenizer().decode(res.sequences[0].tokens, skip_special_tokens=True).strip()


def classify(system, user):
    """Returns the model's JSON, or None if it can't be read (never a silent 'no risk')."""
    text = generate([{"role": "system", "content": system}, {"role": "user", "content": user}])
    s, e = text.find("{"), text.rfind("}")
    try:
        return json.loads(text[s:e + 1])
    except Exception:
        return None
