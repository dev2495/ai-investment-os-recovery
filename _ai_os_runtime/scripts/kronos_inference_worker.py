
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

KRONOS_CODE_REPO = "https://github.com/shiyu-coder/Kronos"
KRONOS_CODE_REVISION = "67b630e67f6a18c9e9be918d9b4337c960db1e9a"
KRONOS_MODEL_REPO = "NeoQuasar/Kronos-mini"
KRONOS_MODEL_REVISION = "f4e68697d9d5aed55cef5c96aabc3376bcad9f81"
KRONOS_MODEL_SHA256 = "a7d5f37e2e9fbd9891f7d7d4f72574512dd1f704fee14223e0a8cd0fbf54197c"
KRONOS_TOKENIZER_REPO = "NeoQuasar/Kronos-Tokenizer-2k"
KRONOS_TOKENIZER_REVISION = "26966d0035065a0cae0ebad7af8ece35bc1fb51c"
KRONOS_TOKENIZER_SHA256 = "b97ec46b3b72160509e289183eaf7bdf5f0dac5bb9b49522f6d46638a99a8717"


def runtime_home() -> Path:
    return Path(
        os.environ.get("AI_OS_KRONOS_HOME")
        or "/Volumes/Devarsh SSD/AI OS Data/models/kronos-runtime"
    ).expanduser()


def source_repo() -> Path:
    return Path(os.environ.get("AI_OS_KRONOS_REPO") or runtime_home() / "source" / "Kronos")


def cache_root() -> Path:
    return Path(os.environ.get("AI_OS_KRONOS_CACHE") or runtime_home() / "huggingface")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(repo: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "git command failed").strip())
    return result.stdout.strip()


def verify_source() -> dict[str, Any]:
    repo = source_repo()
    if not (repo / ".git").is_dir():
        raise RuntimeError(f"Pinned Kronos source is missing: {repo}")
    revision = git_output(repo, "rev-parse", "HEAD")
    if revision != KRONOS_CODE_REVISION:
        raise RuntimeError(
            f"Kronos source revision mismatch: expected {KRONOS_CODE_REVISION}, found {revision}"
        )
    changed = git_output(repo, "status", "--porcelain", "--", "model")
    if changed:
        raise RuntimeError("Pinned Kronos model source has local modifications.")
    return {
        "source_repo": KRONOS_CODE_REPO,
        "source_path": str(repo),
        "source_code_revision": revision,
    }


def resolve_snapshot(
    repo_id: str,
    revision: str,
    expected_sha256: str,
    *,
    allow_download: bool,
) -> dict[str, Any]:
    from huggingface_hub import snapshot_download

    snapshot = Path(
        snapshot_download(
            repo_id=repo_id,
            revision=revision,
            cache_dir=str(cache_root()),
            allow_patterns=["config.json", "model.safetensors", "README.md"],
            local_files_only=not allow_download,
        )
    )
    model_file = snapshot / "model.safetensors"
    if not model_file.is_file():
        raise RuntimeError(f"Safetensors weights are missing for {repo_id}@{revision}")
    actual_sha256 = sha256_file(model_file)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"Weight hash mismatch for {repo_id}@{revision}: "
            f"expected {expected_sha256}, found {actual_sha256}"
        )
    prohibited = [
        str(path)
        for pattern in ("*.bin", "*.pt", "*.pth", "*.pkl", "*.pickle")
        for path in snapshot.rglob(pattern)
    ]
    if prohibited:
        raise RuntimeError(f"Unsafe weight artifacts found: {prohibited}")
    return {
        "repo_id": repo_id,
        "revision": revision,
        "snapshot_path": str(snapshot),
        "weight_path": str(model_file),
        "weight_sha256": actual_sha256,
        "weight_bytes": model_file.stat().st_size,
    }


def dependency_versions() -> dict[str, str]:
    import einops
    import huggingface_hub
    import numpy
    import pandas
    import safetensors
    import torch

    return {
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "numpy": numpy.__version__,
        "pandas": pandas.__version__,
        "einops": einops.__version__,
        "huggingface_hub": huggingface_hub.__version__,
        "safetensors": safetensors.__version__,
    }


def readiness(*, allow_download: bool) -> dict[str, Any]:
    try:
        versions = dependency_versions()
        source = verify_source()
        model = resolve_snapshot(
            KRONOS_MODEL_REPO,
            KRONOS_MODEL_REVISION,
            KRONOS_MODEL_SHA256,
            allow_download=allow_download,
        )
        tokenizer = resolve_snapshot(
            KRONOS_TOKENIZER_REPO,
            KRONOS_TOKENIZER_REVISION,
            KRONOS_TOKENIZER_SHA256,
            allow_download=allow_download,
        )
        import torch

        mps_available = bool(
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        )
        return {
            "ready": True,
            "runtime_home": str(runtime_home()),
            "source": source,
            "model": model,
            "tokenizer": tokenizer,
            "versions": versions,
            "mps_available": mps_available,
            "research_only": True,
            "broker_order_allowed": False,
            "synthetic_fallback_allowed": False,
        }
    except Exception as exc:
        return {
            "ready": False,
            "runtime_home": str(runtime_home()),
            "error": f"{type(exc).__name__}: {exc}",
            "research_only": True,
            "broker_order_allowed": False,
            "synthetic_fallback_allowed": False,
        }


def select_device(torch_module: Any) -> str:
    requested = str(os.environ.get("AI_OS_KRONOS_DEVICE") or "auto").lower()
    if requested == "auto":
        if hasattr(torch_module.backends, "mps") and torch_module.backends.mps.is_available():
            return "mps"
        return "cpu"
    if requested == "mps":
        if not (
            hasattr(torch_module.backends, "mps")
            and torch_module.backends.mps.is_available()
        ):
            raise RuntimeError("AI_OS_KRONOS_DEVICE=mps but MPS is unavailable.")
        return "mps"
    if requested != "cpu":
        raise ValueError("AI_OS_KRONOS_DEVICE must be auto, mps, or cpu.")
    return requested


def require_number(value: Any, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} contains a non-finite value.")
    return number


def run_inference(request: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    expected_model_revision = str(request.get("model_revision") or "")
    if expected_model_revision != KRONOS_MODEL_REVISION:
        raise ValueError(
            f"Only pinned model revision {KRONOS_MODEL_REVISION} is allowed."
        )
    rows = request.get("rows")
    if not isinstance(rows, list) or len(rows) < 32:
        raise ValueError("At least 32 point-in-time OHLCV rows are required.")
    future_timestamps = request.get("future_timestamps")
    horizon = int(request.get("horizon") or 0)
    path_count = int(request.get("path_count") or 0)
    if not isinstance(future_timestamps, list) or len(future_timestamps) != horizon:
        raise ValueError("future_timestamps must match the requested horizon.")
    if not 1 <= horizon <= 256:
        raise ValueError("horizon must be between 1 and 256.")
    if not 20 <= path_count <= 256:
        raise ValueError("path_count must be between 20 and 256.")

    ready = readiness(allow_download=False)
    if not ready.get("ready"):
        raise RuntimeError(str(ready.get("error") or "Kronos runtime is not ready."))

    import numpy as np
    import pandas as pd
    import torch

    repo = source_repo()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    from model import Kronos, KronosPredictor, KronosTokenizer

    frame_rows: list[dict[str, Any]] = []
    timestamps: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"OHLCV row {index} is not an object.")
        timestamps.append(str(row["ts"]))
        open_value = require_number(row["open"], "open")
        high_value = require_number(row["high"], "high")
        low_value = require_number(row["low"], "low")
        close_value = require_number(row["close"], "close")
        volume_value = require_number(row["volume"], "volume")
        if volume_value < 0:
            raise ValueError(f"Input volume is negative at row {index}.")
        if high_value < max(open_value, close_value, low_value):
            raise ValueError(f"Input OHLC relation is invalid at row {index}.")
        if low_value > min(open_value, close_value, high_value):
            raise ValueError(f"Input OHLC relation is invalid at row {index}.")
        frame_rows.append(
            {
                "open": open_value,
                "high": high_value,
                "low": low_value,
                "close": close_value,
                "volume": volume_value,
                "amount": volume_value
                * ((open_value + high_value + low_value + close_value) / 4.0),
            }
        )

    frame = pd.DataFrame(frame_rows)
    x_timestamps = pd.Series(pd.to_datetime(timestamps, utc=True))
    y_timestamps = pd.Series(pd.to_datetime(future_timestamps, utc=True))

    model_snapshot = Path(ready["model"]["snapshot_path"])
    tokenizer_snapshot = Path(ready["tokenizer"]["snapshot_path"])
    tokenizer = KronosTokenizer.from_pretrained(str(tokenizer_snapshot))
    model = Kronos.from_pretrained(str(model_snapshot))
    model.eval()
    tokenizer.eval()

    device = select_device(torch)
    if device == "cpu":
        thread_limit = max(1, min(int(os.environ.get("AI_OS_KRONOS_CPU_THREADS") or 4), 8))
        torch.set_num_threads(thread_limit)

    predictor = KronosPredictor(model, tokenizer, device=device, max_context=2048)
    temperature = float(request.get("temperature") or 1.0)
    top_p = float(request.get("top_p") or 0.9)
    seed_base = int(request.get("seed_base") or 20260729)
    batch_size = max(
        1,
        min(int(os.environ.get("AI_OS_KRONOS_PATH_BATCH") or 5), path_count),
    )

    path_outputs: list[dict[str, Any]] = []
    for start_index in range(0, path_count, batch_size):
        current_count = min(batch_size, path_count - start_index)
        torch.manual_seed(seed_base + start_index)
        np.random.seed((seed_base + start_index) % (2**32 - 1))
        predicted = predictor.predict_batch(
            df_list=[frame] * current_count,
            x_timestamp_list=[x_timestamps] * current_count,
            y_timestamp_list=[y_timestamps] * current_count,
            pred_len=horizon,
            T=temperature,
            top_k=0,
            top_p=top_p,
            sample_count=1,
            verbose=False,
        )
        for local_index, prediction in enumerate(predicted):
            points: list[dict[str, Any]] = []
            for step_index, (_, row) in enumerate(prediction.iterrows(), start=1):
                point = {
                    "step_index": step_index,
                    "forecast_ts": future_timestamps[step_index - 1],
                    "open": require_number(row["open"], "forecast open"),
                    "high": require_number(row["high"], "forecast high"),
                    "low": require_number(row["low"], "forecast low"),
                    "close": require_number(row["close"], "forecast close"),
                    "volume": require_number(row["volume"], "forecast volume"),
                    "amount": require_number(row["amount"], "forecast amount"),
                }
                point["ohlc_valid"] = bool(
                    point["high"] >= max(point["open"], point["close"], point["low"])
                    and point["low"] <= min(point["open"], point["close"], point["high"])
                )
                point["volume_valid"] = bool(point["volume"] >= 0)
                points.append(point)
            path_outputs.append(
                {
                    "path_index": start_index + local_index + 1,
                    "seed_group": seed_base + start_index,
                    "points": points,
                }
            )

    if len(path_outputs) != path_count:
        raise RuntimeError("Kronos returned an incomplete path set.")

    return {
        "status": "completed",
        "device": device,
        "paths": path_outputs,
        "path_count": path_count,
        "horizon": horizon,
        "temperature": temperature,
        "top_p": top_p,
        "seed_base": seed_base,
        "source_code_revision": KRONOS_CODE_REVISION,
        "model_repo": KRONOS_MODEL_REPO,
        "model_revision": KRONOS_MODEL_REVISION,
        "model_sha256": KRONOS_MODEL_SHA256,
        "tokenizer_repo": KRONOS_TOKENIZER_REPO,
        "tokenizer_revision": KRONOS_TOKENIZER_REVISION,
        "tokenizer_sha256": KRONOS_TOKENIZER_SHA256,
        "runtime_versions": ready["versions"],
        "research_only": True,
        "direct_signal": False,
        "broker_order_allowed": False,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolated pinned Kronos inference worker.")
    parser.add_argument("--readiness", action="store_true")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--request")
    arguments = parser.parse_args()

    if arguments.readiness or arguments.prepare:
        result = readiness(allow_download=arguments.prepare)
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("ready") else 1
    if not arguments.request:
        parser.error("--request is required for inference")
    request_path = Path(arguments.request)
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
        result = run_inference(request)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                    "research_only": True,
                    "synthetic_fallback_used": False,
                    "broker_order_allowed": False,
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
