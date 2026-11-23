"""Exercise Phase 0 failure, repair, checkpoint, and reporting in isolation."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


DEFECTIVE = """def prepare_status(value):
    return value
"""

REPAIRED = """def prepare_status(value):
    return value.strip()
"""

TEST = """import unittest

from fixture import prepare_status


class StatusTest(unittest.TestCase):
    def test_removes_surrounding_whitespace(self):
        self.assertEqual(prepare_status(" ready "), "ready")
"""


def write_atomic(path, content):
    with tempfile.NamedTemporaryFile(
        dir=path.parent, mode="w", encoding="utf-8", delete=False
    ) as output:
        temporary_path = Path(output.name)
        output.write(content)
    temporary_path.replace(path)


def save_checkpoint(output_dir, state):
    write_atomic(output_dir / "state.json", json.dumps(state, indent=2) + "\n")


def run_test(output_dir, fixture_dir, attempt):
    result = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "-v", "test_fixture"],
        cwd=fixture_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    log = f"Exit code {result.returncode}\n\n{result.stdout}"
    name = f"attempt-{attempt}.log"
    write_atomic(output_dir / name, log)
    return result.returncode, result.stdout


def write_report(output_dir, state):
    rows = [
        f"| {attempt['number']} | {attempt['outcome']} | {attempt['exit_code']} | "
        f"[Test output](attempt-{attempt['number']}.log) |"
        for attempt in state["attempts"]
    ]
    report = [
        "# Phase 0 harness smoke exercise",
        "",
        "This exercise runs one unchanged unittest against a disposable Python fixture.",
        "The fixture's repair trims surrounding whitespace from a status string.",
        "",
        f"Checkpoint status `{state['status']}`.",
        "",
        "| Attempt | Observed outcome | Exit code | Evidence |",
        "| --- | --- | --- | --- |",
        *rows,
        "",
        "[Saved checkpoint](state.json)",
        "",
    ]
    write_atomic(output_dir / "report.md", "\n".join(report))


def exercise(output_dir, pause_after_failure):
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = output_dir / "state.json"
    state = {"status": "NEW", "attempts": []}
    if checkpoint.exists():
        state = json.loads(checkpoint.read_text(encoding="utf-8"))
        for attempt in state["attempts"]:
            evidence = output_dir / f"attempt-{attempt['number']}.log"
            if not evidence.is_file():
                print(f"Missing checkpoint evidence: {evidence}", file=sys.stderr)
                return 1
        print(f"Loaded checkpoint {state['status']}")

    if state["status"] in {"DONE", "BLOCKED"}:
        write_report(output_dir, state)
        return int(state["status"] == "BLOCKED")

    with tempfile.TemporaryDirectory(prefix="metalflow-smoke-") as fixture:
        fixture_dir = Path(fixture)
        implementation = fixture_dir / "fixture.py"
        implementation.write_text(DEFECTIVE, encoding="utf-8")
        (fixture_dir / "test_fixture.py").write_text(TEST, encoding="utf-8")

        if state["status"] == "NEW":
            code, log = run_test(output_dir, fixture_dir, 1)
            expected = (
                code == 1
                and "Ran 1 test" in log
                and "FAILED (failures=1)" in log
                and "AssertionError: ' ready ' != 'ready'" in log
            )
            state["attempts"].append(
                {
                    "number": 1,
                    "outcome": "EXPECTED FAILURE" if expected else "UNEXPECTED RESULT",
                    "exit_code": code,
                }
            )
            state["status"] = "REPAIR_PENDING" if expected else "BLOCKED"
            save_checkpoint(output_dir, state)
            write_report(output_dir, state)
            if not expected:
                return 1
        if pause_after_failure:
            print("Saved failing test checkpoint. Run again without --pause-after-failure.")
            return 0

        implementation.write_text(REPAIRED, encoding="utf-8")
        code, log = run_test(output_dir, fixture_dir, 2)
        passed = code == 0 and "Ran 1 test" in log and log.rstrip().endswith("OK")
        state["attempts"].append(
            {"number": 2, "outcome": "PASSED" if passed else "UNEXPECTED RESULT", "exit_code": code}
        )
        state["status"] = "DONE" if passed else "BLOCKED"
        save_checkpoint(output_dir, state)
        write_report(output_dir, state)
        print(f"Saved smoke exercise checkpoint {state['status']}")
        return int(not passed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--pause-after-failure", action="store_true")
    options = parser.parse_args()
    return exercise(options.output_dir, options.pause_after_failure)


if __name__ == "__main__":
    sys.exit(main())
