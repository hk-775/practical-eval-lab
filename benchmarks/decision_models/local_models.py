"""Pinned local model loading. Heavy dependencies live in runtime/uv.lock only."""

from __future__ import annotations

import importlib.metadata
import json
import shutil
import tempfile
from pathlib import Path

from .adapters import CandidateError
from .contract import ROOT


def load_local(name, info):
    import torch
    from huggingface_hub import snapshot_download

    device = info["device"]
    if device == "mps" and not torch.backends.mps.is_available():
        raise CandidateError("mps_unavailable")
    if device == "cuda" and not torch.cuda.is_available():
        raise CandidateError("cuda_unavailable")
    torch.manual_seed(0)

    def synchronize():
        if device == "mps":
            torch.mps.synchronize()
        elif device == "cuda":
            torch.cuda.synchronize()

    info = dict(info)
    info["packages"] = {p: importlib.metadata.version(p) for p in
                        ("torch", "transformers", "huggingface-hub", "strands-decider", "laya")}
    import hashlib
    info["runtime_lock_sha256"] = hashlib.sha256((ROOT / "runtime/uv.lock").read_bytes()).hexdigest()
    info["compile"] = False
    if name == "laya":
        from laya import Agent
        agent = Agent(info["model"], revision=info["revision"], device=device,
                      compile=False, fast=False)
        if str(agent.device) != device:
            raise CandidateError("device_changed")
        info["dtype"] = str(next(agent.model.parameters()).dtype)
        info["checkpoint_routing"] = "disabled"
        info["effective_temperatures"] = {
            "default": agent.temperature, "by_options": agent.temperature_by_options,
        }
        info["temperature_note"] = (
            "Upstream runtime clamps checkpoint temperatures outside its supported range. "
            "The choice:11+ bucket is affected in this checkpoint; this dataset has 2–4 options."
        )

        def predict(request):
            result = agent.system_one(request["state"], request["questions"],
                                      max_len=info["context_tokens"], head_max_len=info["head_tokens"])
            if str(agent.device) != device:
                raise CandidateError("device_changed")
            usage = result.get("usage", {})
            if usage.get("truncated") or usage.get("state_tokens_dropped") or usage.get("options"):
                raise CandidateError("input_truncated_or_options_collapsed")
            result["model"] = info["model"]
            return result
        return predict, info, synchronize

    from strands_decider.modeling import StrandsDeciderModel
    from strands_decider.infer import EngineConfig, SystemOneEngine
    from strands_decider.schema import SystemOneRequest

    checkpoint = snapshot_download(info["model"], revision=info["revision"],
                                   allow_patterns=["*.json", "*.safetensors", "*.jinja",
                                                   "lora/*", "LICENSE.md"])
    backbone = snapshot_download(info["base_model"], revision=info["base_revision"],
                                 allow_patterns=["*.json", "*.safetensors", "*.jinja"])
    # The upstream loader does not read provenance.base_model_revision. Resolve
    # that revision ourselves and point a temporary config at its local snapshot.
    # Cached upstream files and weights are never rewritten.
    with tempfile.TemporaryDirectory(prefix="decision-checkpoint-") as directory:
        copied = Path(directory) / "checkpoint"
        shutil.copytree(checkpoint, copied)
        path = copied / "hobson_config.json"
        config = json.loads(path.read_text(encoding="utf-8"))
        config["base_model"] = backbone
        path.write_text(json.dumps(config), encoding="utf-8")
        model = StrandsDeciderModel.load(str(copied))
    engine = SystemOneEngine(model, EngineConfig(device=device, strict_window=True,
                                                model_name=info["model"]))
    info["dtype"] = str(next(engine.model.torso.parameters()).dtype)
    info["strict_window"] = True
    info["shared_prefix_cache"] = True
    info["effective_temperatures"] = {
        "default": engine.model.config.temperature,
        "by_kind": engine.model.config.temperature_by_kind,
    }

    def predict(request):
        # strict_window refuses overflow instead of silently cutting the state.
        result = engine.evaluate(SystemOneRequest.model_validate(request))
        return result.model_dump()

    return predict, info, synchronize
