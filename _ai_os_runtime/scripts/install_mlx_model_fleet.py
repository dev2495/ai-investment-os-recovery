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


MODEL_ID = "mlx-community/Qwen3.5-9B-4bit"
REVISION = "8b2b98c00a6b4d291155e4890773ca8f769aee53"
INTERNAL_ROOT = Path.home() / "Library/Application Support/AIOS"
ROOT = Path(os.environ.get("AI_OS_MLX_MODEL_ROOT", str(INTERNAL_ROOT / "models"))).expanduser()
CACHE_ROOT = Path(os.environ.get("HF_HOME", str(INTERNAL_ROOT / "huggingface"))).expanduser()
TARGET = ROOT / "qwen3.5-9b-4bit-8b2b98c"


def main() -> int:
    resolved_root = ROOT.resolve()
    allowed_internal = INTERNAL_ROOT.resolve()
    if not (str(resolved_root).startswith(str(allowed_internal)) or str(resolved_root).startswith("/Volumes/")):
        raise SystemExit("MLX model root must stay inside the AIOS application directory or an external volume")
    ROOT.mkdir(parents=True, exist_ok=True)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    resolved = None
    for attempt in range(1, 6):
        try:
            resolved = snapshot_download(
                repo_id=MODEL_ID,
                revision=REVISION,
                local_dir=TARGET,
                cache_dir=str(CACHE_ROOT),
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
