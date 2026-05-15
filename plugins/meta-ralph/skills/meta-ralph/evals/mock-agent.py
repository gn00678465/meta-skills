#!/usr/bin/env python3
"""Mock agent binary for runner evals.

Dumps received argv to argv_dump.json in the current working directory and exits 0.
The driver spawns this as `python <abs-path-to-this-script> <runner.args...>`, so
sys.argv[0] is this script's path and sys.argv[1:] is what we capture.

JSON encoding preserves embedded newlines / special characters in args exactly,
which lets the harness detect cross-runtime drift in newline handling.
"""
import json
import sys
from pathlib import Path


def main() -> int:
    dump_path = Path("argv_dump.json")
    payload = {"argv": sys.argv[1:]}
    tmp = dump_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(dump_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
