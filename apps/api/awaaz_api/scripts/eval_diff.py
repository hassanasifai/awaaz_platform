"""Compare an eval report against a baseline.

Used by the nightly GH Action to gate merges on a max regression threshold.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--max-regression", type=float, default=0.05)
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text())
    baseline_path = Path(args.baseline)
    if not baseline_path.exists():
        print(f"no baseline at {baseline_path}; saving current as baseline.")
        baseline_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    baseline = json.loads(baseline_path.read_text())

    cur_rate = report["passed"] / max(report["total"], 1)
    base_rate = baseline["passed"] / max(baseline["total"], 1)
    regression = max(0.0, base_rate - cur_rate)
    print(f"current={cur_rate:.3f} baseline={base_rate:.3f} regression={regression:.3f}")
    return 0 if regression <= args.max_regression else 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
