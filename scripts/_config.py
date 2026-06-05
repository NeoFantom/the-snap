"""Shared config loader. Reads ./config.json, override with $FO_CONFIG."""
import json
import os
import sys

def load(path=None):
    path = path or os.environ.get("FO_CONFIG") or "config.json"
    if not os.path.exists(path):
        sys.exit(f"config not found: {path}  (copy scripts/config.example.json to config.json and edit)")
    raw = json.load(open(path, encoding="utf-8"))
    # strip _comment keys at any depth
    def clean(x):
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items() if not k.startswith("_comment")}
        if isinstance(x, list):
            return [clean(v) for v in x if not (isinstance(v, dict) and any(k.startswith("_comment") for k in v))]
        return x
    return clean(raw)
