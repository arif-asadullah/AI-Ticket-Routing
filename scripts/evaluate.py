#!/usr/bin/env python3
"""
DeskMind Classification Evaluation — Fixed Test Set Benchmark.

Runs 35 hand-labeled test tickets through the full classification pipeline
and measures accuracy, per-category metrics, confidence, and timing.

Usage:
    source .venv/bin/activate
    python scripts/evaluate.py --tag baseline
    python scripts/evaluate.py --tag after_title_embed
    python scripts/evaluate.py --compare baseline after_title_embed
"""

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arango import ArangoClient
from backend.core.config import settings
from backend.services.orchestrator import classify, get_embedding_model

EVAL_DIR = Path("data/eval")
TEST_SET = EVAL_DIR / "test_tickets.json"


def connect_db():
    client = ArangoClient(hosts=settings.ARANGO_URL)
    return client.db(settings.ARANGO_DB, username=settings.ARANGO_USER, password=settings.ARANGO_PASSWORD)


def load_test_tickets():
    """Load fixed test set."""
    with open(TEST_SET) as f:
        tickets = json.load(f)
    # Filter out tickets with no expected category (vague ones) for accuracy calc
    # but still run them to measure confidence/quality
    return tickets


async def run_evaluation(db, tickets):
    """Run each ticket through the pipeline and collect results."""
    results = []
    total = len(tickets)

    # Pre-warm embedding model
    get_embedding_model()

    for i, ticket in enumerate(tickets):
        title = ticket["title"]
        description = ticket["description"]
        expected = ticket["expected_category"]
        difficulty = ticket.get("difficulty", "unknown")

        start = time.time()
        try:
            result = await classify(
                title=title,
                description=description,
                db=db,
                redis_client=None,  # Skip cache for eval
                skip_cache=True,
            )
            predicted = result["category"]
            confidence = result["confidence"]
            agreement = result["agreement"]
            quality = result["quality_score"]
            votes = result["classifier_votes"]
            elapsed = int((time.time() - start) * 1000)

            # For vague tickets (expected=null), we just check low confidence
            if expected is None:
                correct = None  # Not scored
                status = "~"
            else:
                correct = predicted == expected
                status = "+" if correct else "X"

            entry = {
                "id": ticket["id"],
                "title": title[:60],
                "expected": expected,
                "predicted": predicted,
                "correct": correct,
                "confidence": round(confidence, 4),
                "agreement": agreement,
                "quality_score": quality,
                "difficulty": difficulty,
                "votes": {k: {"category": v.get("category"), "confidence": round(v.get("confidence", 0), 3)} for k, v in votes.items()},
                "elapsed_ms": elapsed,
            }
            results.append(entry)

            exp_label = expected or "VAGUE"
            print(f"  [{i+1:2d}/{total}] {status} {exp_label:22s} -> {predicted:22s} conf={confidence:.2f} qual={quality:6s} {agreement:5s} {elapsed:5d}ms | {title[:45]}")

        except Exception as exc:
            print(f"  [{i+1:2d}/{total}] E ERROR: {exc} | {title[:45]}")
            results.append({
                "id": ticket["id"],
                "title": title[:60],
                "expected": expected,
                "predicted": None,
                "correct": False,
                "confidence": 0,
                "agreement": "0/0",
                "quality_score": "N/A",
                "difficulty": difficulty,
                "votes": {},
                "elapsed_ms": 0,
            })

    return results


def build_report(results, tag):
    """Build comprehensive evaluation report."""
    # Filter scorable tickets (non-vague)
    scorable = [r for r in results if r["correct"] is not None]
    vague = [r for r in results if r["correct"] is None]

    total = len(scorable)
    correct = sum(1 for r in scorable if r["correct"])
    accuracy = correct / total if total > 0 else 0
    avg_conf = np.mean([r["confidence"] for r in scorable]) if scorable else 0
    avg_time = np.mean([r["elapsed_ms"] for r in results]) if results else 0

    # Per-category metrics
    categories = sorted(set(r["expected"] for r in scorable if r["expected"]))
    per_category = {}
    for cat in categories:
        cat_results = [r for r in scorable if r["expected"] == cat]
        cat_correct = sum(1 for r in cat_results if r["correct"])
        cat_total = len(cat_results)
        cat_acc = cat_correct / cat_total if cat_total > 0 else 0
        cat_conf = np.mean([r["confidence"] for r in cat_results])
        per_category[cat] = {
            "correct": cat_correct,
            "total": cat_total,
            "accuracy": round(cat_acc, 4),
            "avg_confidence": round(float(cat_conf), 4),
        }

    # Per-difficulty metrics
    difficulties = sorted(set(r["difficulty"] for r in scorable))
    per_difficulty = {}
    for diff in difficulties:
        diff_results = [r for r in scorable if r["difficulty"] == diff]
        diff_correct = sum(1 for r in diff_results if r["correct"])
        diff_total = len(diff_results)
        per_difficulty[diff] = {
            "correct": diff_correct,
            "total": diff_total,
            "accuracy": round(diff_correct / diff_total, 4) if diff_total > 0 else 0,
        }

    # Confusion matrix
    confusion = {}
    for actual in categories:
        confusion[actual] = {}
        for predicted in categories:
            confusion[actual][predicted] = sum(
                1 for r in scorable
                if r["expected"] == actual and r["predicted"] == predicted
            )

    # Classifier-level accuracy (how often each classifier got it right)
    classifier_accuracy = {}
    for clf_name in ["llm", "knn", "centroid", "keyword"]:
        clf_correct = sum(
            1 for r in scorable
            if r["votes"].get(clf_name, {}).get("category") == r["expected"]
        )
        clf_voted = sum(1 for r in scorable if clf_name in r["votes"])
        classifier_accuracy[clf_name] = {
            "correct": clf_correct,
            "voted": clf_voted,
            "accuracy": round(clf_correct / clf_voted, 4) if clf_voted > 0 else 0,
        }

    # Misclassifications detail
    misses = [
        {
            "id": r["id"],
            "title": r["title"],
            "expected": r["expected"],
            "predicted": r["predicted"],
            "confidence": r["confidence"],
            "votes": r["votes"],
            "difficulty": r["difficulty"],
        }
        for r in scorable if not r["correct"]
    ]

    # Vague ticket analysis
    vague_analysis = [
        {
            "id": r["id"],
            "title": r["title"],
            "predicted": r["predicted"],
            "confidence": r["confidence"],
            "quality_score": r["quality_score"],
        }
        for r in vague
    ]

    now = datetime.now(timezone.utc).isoformat()

    report = {
        "tag": tag,
        "timestamp": now,
        "embedding_model": str(get_embedding_model().get_sentence_embedding_dimension()) + "d",
        "summary": {
            "total_scorable": total,
            "correct": correct,
            "accuracy": round(accuracy, 4),
            "avg_confidence": round(float(avg_conf), 4),
            "avg_processing_time_ms": round(float(avg_time), 1),
        },
        "per_category": per_category,
        "per_difficulty": per_difficulty,
        "classifier_accuracy": classifier_accuracy,
        "confusion_matrix": confusion,
        "misclassifications": misses,
        "vague_analysis": vague_analysis,
        "all_results": results,
    }

    return report


def print_report(report):
    """Pretty-print the evaluation report to console."""
    s = report["summary"]
    tag = report["tag"]

    print()
    print("=" * 72)
    print(f"  DeskMind Classification Evaluation")
    print(f"  Tag: {tag} | {report['timestamp'][:19]} | Embedding: {report['embedding_model']}")
    print("=" * 72)
    print()
    print(f"  Overall Accuracy:    {s['correct']}/{s['total_scorable']} ({s['accuracy']:.1%})")
    print(f"  Avg Confidence:      {s['avg_confidence']:.3f}")
    print(f"  Avg Processing Time: {s['avg_processing_time_ms']:.0f}ms")
    print()

    # Per-category table
    print(f"  {'Category':<22} {'Correct':>8} {'Total':>6} {'Accuracy':>9} {'Avg Conf':>9}")
    print(f"  {'-'*56}")
    for cat, m in sorted(report["per_category"].items()):
        print(f"  {cat:<22} {m['correct']:>8} {m['total']:>6} {m['accuracy']:>8.1%} {m['avg_confidence']:>8.3f}")
    print()

    # Per-difficulty
    print(f"  {'Difficulty':<22} {'Correct':>8} {'Total':>6} {'Accuracy':>9}")
    print(f"  {'-'*47}")
    for diff, m in sorted(report["per_difficulty"].items()):
        print(f"  {diff:<22} {m['correct']:>8} {m['total']:>6} {m['accuracy']:>8.1%}")
    print()

    # Classifier individual accuracy
    print(f"  {'Classifier':<22} {'Correct':>8} {'Voted':>6} {'Accuracy':>9}")
    print(f"  {'-'*47}")
    for clf, m in sorted(report["classifier_accuracy"].items()):
        print(f"  {clf:<22} {m['correct']:>8} {m['voted']:>6} {m['accuracy']:>8.1%}")
    print()

    # Confusion matrix
    cats = sorted(report["confusion_matrix"].keys())
    print("  Confusion Matrix (rows=expected, cols=predicted):")
    header = "  " + f"{'':>22}" + "".join(f" {c[:7]:>7}" for c in cats)
    print(header)
    for actual in cats:
        row = f"  {actual:<22}"
        for predicted in cats:
            cnt = report["confusion_matrix"][actual].get(predicted, 0)
            marker = f" {cnt:>7}" if cnt == 0 else f" {cnt:>7}"
            row += marker
        print(row)
    print()

    # Misclassifications
    misses = report["misclassifications"]
    if misses:
        print(f"  Misclassifications ({len(misses)}):")
        for m in misses:
            votes_str = " ".join(f"{k}={v['category']}" for k, v in m["votes"].items())
            print(f"    [{m['difficulty']:>15}] {m['expected']:>22} -> {m['predicted']:<22} conf={m['confidence']:.2f} | {votes_str}")
        print()

    # Vague tickets
    vague = report["vague_analysis"]
    if vague:
        print(f"  Vague Ticket Analysis ({len(vague)}):")
        for v in vague:
            print(f"    predicted={v['predicted']:<22} conf={v['confidence']:.2f} quality={v['quality_score']} | {v['title']}")
        print()

    print("=" * 72)


def compare_reports(tags):
    """Load and compare multiple evaluation runs side by side."""
    reports = []
    for tag in tags:
        path = EVAL_DIR / f"eval_{tag}.json"
        if not path.exists():
            print(f"  Error: {path} not found. Run evaluation with --tag {tag} first.")
            return
        with open(path) as f:
            reports.append(json.load(f))

    print()
    print("=" * 90)
    print("  DeskMind Improvement Comparison Report")
    print("=" * 90)
    print()

    # Summary comparison table
    print(f"  {'Tag':<25} {'Accuracy':>10} {'Delta':>8} {'Avg Conf':>10} {'Avg Time':>10}")
    print(f"  {'-'*65}")
    baseline_acc = reports[0]["summary"]["accuracy"]
    for r in reports:
        s = r["summary"]
        delta = s["accuracy"] - baseline_acc
        delta_str = f"+{delta:.1%}" if delta > 0 else f"{delta:.1%}" if delta < 0 else "---"
        if r == reports[0]:
            delta_str = "baseline"
        print(f"  {r['tag']:<25} {s['accuracy']:>9.1%} {delta_str:>8} {s['avg_confidence']:>9.3f} {s['avg_processing_time_ms']:>8.0f}ms")
    print()

    # Per-category comparison
    cats = sorted(reports[0]["per_category"].keys())
    print(f"  Per-Category Accuracy Comparison:")
    header = f"  {'Category':<22}" + "".join(f" {r['tag'][:12]:>12}" for r in reports)
    print(header)
    print(f"  {'-'*(22 + 13 * len(reports))}")
    for cat in cats:
        row = f"  {cat:<22}"
        for r in reports:
            m = r["per_category"].get(cat, {"accuracy": 0})
            row += f" {m['accuracy']:>11.1%}"
        print(row)
    print()

    # Individual classifier accuracy comparison
    clfs = ["llm", "knn", "centroid", "keyword"]
    print(f"  Individual Classifier Accuracy:")
    header = f"  {'Classifier':<22}" + "".join(f" {r['tag'][:12]:>12}" for r in reports)
    print(header)
    print(f"  {'-'*(22 + 13 * len(reports))}")
    for clf in clfs:
        row = f"  {clf:<22}"
        for r in reports:
            m = r["classifier_accuracy"].get(clf, {"accuracy": 0})
            row += f" {m['accuracy']:>11.1%}"
        print(row)
    print()

    # Misclassification diff
    if len(reports) >= 2:
        base_miss_ids = {m["id"] for m in reports[0]["misclassifications"]}
        latest_miss_ids = {m["id"] for m in reports[-1]["misclassifications"]}
        fixed = base_miss_ids - latest_miss_ids
        regressed = latest_miss_ids - base_miss_ids

        if fixed:
            print(f"  Fixed (were wrong, now correct): {len(fixed)} tickets")
            for mid in sorted(fixed):
                m = next(x for x in reports[0]["misclassifications"] if x["id"] == mid)
                print(f"    #{mid}: {m['expected']} (was predicted as {m['predicted']})")

        if regressed:
            print(f"  Regressions (were correct, now wrong): {len(regressed)} tickets")
            for mid in sorted(regressed):
                m = next(x for x in reports[-1]["misclassifications"] if x["id"] == mid)
                print(f"    #{mid}: {m['expected']} (now predicted as {m['predicted']})")

        if not fixed and not regressed:
            print("  No changes in misclassifications between runs.")
        print()

    print("=" * 90)

    # Save comparison
    comparison_path = EVAL_DIR / f"comparison_{'_vs_'.join(tags)}.json"
    comparison = {
        "tags": tags,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": [{"tag": r["tag"], **r["summary"]} for r in reports],
        "per_category": {cat: {r["tag"]: r["per_category"].get(cat, {}) for r in reports} for cat in cats},
        "classifier_accuracy": {clf: {r["tag"]: r["classifier_accuracy"].get(clf, {}) for r in reports} for clf in clfs},
    }
    with open(comparison_path, "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"  Comparison saved to {comparison_path}")


def main():
    parser = argparse.ArgumentParser(description="DeskMind Classification Evaluation Benchmark")
    parser.add_argument("--tag", type=str, default="baseline", help="Tag for this evaluation run (e.g., baseline, after_title_embed)")
    parser.add_argument("--compare", nargs="+", help="Compare multiple evaluation runs by tag")
    args = parser.parse_args()

    if args.compare:
        compare_reports(args.compare)
        return

    print("=" * 72)
    print(f"  DeskMind Evaluation Benchmark — Tag: {args.tag}")
    print("=" * 72)
    print()

    # Load test set
    tickets = load_test_tickets()
    print(f"  Loaded {len(tickets)} test tickets from {TEST_SET}")

    cats = Counter(t["expected_category"] or "VAGUE" for t in tickets)
    for cat, n in sorted(cats.items()):
        print(f"    {cat}: {n}")
    print()

    # Connect to DB
    db = connect_db()
    print(f"  Connected to ArangoDB: {settings.ARANGO_DB}")
    print()

    # Run evaluation
    print("  Running classification pipeline...")
    print()
    results = asyncio.run(run_evaluation(db, tickets))

    # Build and print report
    report = build_report(results, args.tag)
    print_report(report)

    # Save results
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    output_path = EVAL_DIR / f"eval_{args.tag}.json"
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"  Results saved to {output_path}")
    print()


if __name__ == "__main__":
    main()
