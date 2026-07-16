#!/usr/bin/env python3
from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "600")
os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")

from huggingface_hub import snapshot_download
from huggingface_hub.errors import HfHubHTTPError
from httpx import TimeoutException


MODEL_ID = "DreamFoundries/Qwen3.5-9B-4bit"
REVISION = "20353927abe35e90c459ee908fac8806e5edd455"
ROOT = Path(os.environ.get("AI_OS_MLX_MODEL_ROOT", "/Volumes/Devarsh SSD/AI OS Data/mlx/models"))
TARGET = ROOT / "qwen3.5-9b-4bit-20353927"


def main() -> int:
    if not str(ROOT).startswith("/Volumes/") and os.environ.get("AI_OS_ALLOW_INTERNAL_MODEL_STORE") != "1":
        raise SystemExit("MLX model root must be on an external volume")
    ROOT.mkdir(parents=True, exist_ok=True)
    resolved = None
    for attempt in range(1, 6):
        try:
            resolved = snapshot_download(
                repo_id=MODEL_ID,
                revision=REVISION,
                local_dir=TARGET,
                cache_dir=os.environ.get("HF_HOME", "/Volumes/Devarsh SSD/AI OS Data/huggingface"),
                max_workers=1,
            )
            break
        except (HfHubHTTPError, TimeoutException):
            if attempt == 5:
                raise
            delay = 10 * (2 ** (attempt - 1))
            print(f"Hugging Face transfer failed; resuming in {delay}s (attempt {attempt + 1}/5)", flush=True)
            time.sleep(delay)
    if resolved is None:
        raise RuntimeError("MLX snapshot download did not produce a local path")
    print(f"mlx_model_path={resolved}")
    print(f"mlx_model_revision={REVISION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
