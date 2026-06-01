#!/usr/bin/env python3
"""PostToolUse hook: ruff check --fix + ruff format on the file Claude just wrote.

Scoped to the single edited .py file (not the whole repo) so auto-generated/legacy
files aren't reformatted on every edit. Never blocks: if ruff is absent or fails, it
exits 0 so editing is never interrupted (lint is guidance here, not a gate).
"""
import json
import subprocess
import sys

try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

path = (data.get("tool_input", {}) or {}).get("file_path", "")
if not path.endswith(".py"):
    sys.exit(0)

for cmd in (["ruff", "check", "--fix", "--quiet", path],
            ["ruff", "format", "--quiet", path]):
    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        # ruff not installed — skip silently (run `pip install ruff` to enable).
        break

sys.exit(0)
