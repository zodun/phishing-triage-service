from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import yaml

from app.classifier import Classifier
from app.config import get_settings
from evals.rubric import Case, CaseResult, score_case

ROOT = Path(__file__).parent
REPORTS = ROOT.parent / "reports"


def load_cases(path: Path) -> list[Case]:
    return [
        Case.from_json(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def run(cases: list[Case]) -> list[CaseResult]:
    settings = get_settings()
    if settings.llm_fake:
        print("WARNING: LLM_FAKE is set - eval numbers are not meaningful", file=sys.stderr)
    clf = Classifier(settings)

    results: list[CaseResult] = []
    for case in cases:
        start = time.perf_counter()
        resp = clf.classify(case.text, request_id=f"eval-{case.id}")
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        invalid = any(g.code == "invalid_json" for g in resp.guardrails)
        results.append(
            score_case(case, predicted=resp.label, invalid_json=invalid, latency_ms=latency_ms)
        )
    return results


def aggregate(results: list[CaseResult]) -> dict[str, float]:
    n = len(results) or 1
    legit_n = sum(1 for r in results if r.expected == "legit") or 1
    inj_n = sum(1 for r in results if r.injection) or 1
    latencies = sorted(r.latency_ms for r in results)
    p95 = latencies[int(round(0.95 * (len(latencies) - 1)))] if latencies else 0.0
    return {
        "cases": float(len(results)),
        "accuracy": sum(r.correct for r in results) / n,
        "false_positive_rate": sum(r.false_positive for r in results) / legit_n,
        "invalid_json_rate": sum(r.invalid_json for r in results) / n,
        "injection_bypass_rate": sum(r.injection_bypassed for r in results) / inj_n,
        "p50_latency_ms": statistics.median(latencies) if latencies else 0.0,
        "p95_latency_ms": p95,
    }


_CHECKS = [
    ("accuracy", "min_accuracy", "min"),
    ("false_positive_rate", "max_false_positive_rate", "max"),
    ("invalid_json_rate", "max_invalid_json_rate", "max"),
    ("injection_bypass_rate", "max_injection_bypass_rate", "max"),
    ("p95_latency_ms", "max_p95_latency_ms", "max"),
]


def gate(metrics: dict[str, float], thresholds: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for metric, key, direction in _CHECKS:
        if key not in thresholds:
            continue
        value, limit = metrics[metric], float(thresholds[key])
        if direction == "min" and value < limit:
            failures.append(f"{metric}={value:.3f} < {key}={limit}")
        if direction == "max" and value > limit:
            failures.append(f"{metric}={value:.3f} > {key}={limit}")
    return failures


def write_reports(
    results: list[CaseResult], metrics: dict[str, float], failures: list[str]
) -> None:
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "eval_report.json").write_text(
        json.dumps(
            {"metrics": metrics, "failures": failures, "cases": [r.__dict__ for r in results]},
            indent=2,
        )
    )
    lines = ["# Evaluation report", "", "| metric | value |", "| --- | --- |"]
    lines += [f"| {k} | {v:.3f} |" for k, v in metrics.items()]
    lines += [
        "",
        "| case | expected | predicted | ok | injection | bypassed | invalid json | ms |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        lines.append(
            f"| {r.id} | {r.expected} | {r.predicted} | {'Y' if r.correct else 'N'} | "
            f"{r.injection} | {r.injection_bypassed} | {r.invalid_json} | {r.latency_ms:.0f} |"
        )
    if failures:
        lines += ["", "## Threshold failures", *[f"- {f}" for f in failures]]
    (REPORTS / "eval_report.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the phishing-triage evaluation suite")
    parser.add_argument("--dataset", type=Path, default=ROOT / "dataset.jsonl")
    parser.add_argument("--thresholds", type=Path, default=ROOT / "thresholds.yaml")
    parser.add_argument(
        "--fail-under-thresholds",
        action="store_true",
        help="exit non-zero if any threshold is breached",
    )
    args = parser.parse_args()

    results = run(load_cases(args.dataset))
    metrics = aggregate(results)
    thresholds = yaml.safe_load(args.thresholds.read_text()) if args.thresholds.exists() else {}
    failures = gate(metrics, thresholds or {})
    write_reports(results, metrics, failures)

    print(json.dumps(metrics, indent=2))
    for failure in failures:
        print(f"THRESHOLD FAIL: {failure}", file=sys.stderr)
    return 1 if (failures and args.fail_under_thresholds) else 0


if __name__ == "__main__":
    raise SystemExit(main())
