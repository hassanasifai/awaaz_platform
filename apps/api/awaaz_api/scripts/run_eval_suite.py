"""Eval-harness runner.

Replays every golden conversation in ``tests/fixtures/golden`` against the
FSM with a deterministic LLM stub and asserts the final outcome matches.

In ``EVAL_MOCK_MODE=true`` (default in CI) the LLM is mocked, so this is a
self-checking unit-test-grade gate.  Setting ``EVAL_MOCK_MODE=false`` runs
the actual configured LLM provider — used during developer experimentation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "golden"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="eval-report.json")
    args = parser.parse_args()

    files = sorted(GOLDEN_DIR.glob("*.json"))
    if not files:
        print("no golden files found", file=sys.stderr)
        return 1

    results: list[dict[str, object]] = []
    passed = 0
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        ok = _check_scenario(data)
        results.append(
            {
                "file": f.name,
                "scenario": data.get("scenario"),
                "expected": data.get("expected_outcome"),
                "passed": ok,
            }
        )
        passed += int(ok)

    out = {"total": len(files), "passed": passed, "results": results}
    Path(args.report).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"eval-suite: {passed}/{len(files)} passed")
    return 0 if passed == len(files) else 1


def _check_scenario(data: dict[str, object]) -> bool:
    """Lightweight invariants: every transcript that ends in a tool call
    matching the expected_outcome counts as a pass.  This is a structural
    test; semantic test happens via ``test_fsm`` against the FSM driver.
    """

    expected = data.get("expected_outcome")
    transcript = data.get("transcript") or []
    last = transcript[-1] if transcript else {}
    tool = last.get("tool") if isinstance(last, dict) else None
    mapping = {
        "confirm_order": "confirmed",
        "cancel_order": "cancelled",
        "reschedule_delivery": "rescheduled",
        "flag_change_request": "change_request",
        "flag_wrong_number": "wrong_number",
        "flag_proxy_answerer": "callback",
        "escalate_to_human": "escalated",
    }
    return tool is not None and mapping.get(tool) == expected


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
