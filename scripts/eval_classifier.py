#!/usr/bin/env python3
"""
Evaluate the 4-classifier ensemble on held-out tickets.

Steps:
1. Pick N random tickets from synthetic data (stratified by category)
2. Remove them from ArangoDB (so they're not in training data)
3. Run each through the classification pipeline
4. Compare predicted category vs ground truth
5. Print accuracy, confusion matrix, per-category metrics
6. Restore the tickets back to ArangoDB

Usage:
    source .venv/bin/activate
    python scripts/eval_classifier.py --count 50
"""

import argparse
import asyncio
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arango import ArangoClient
from backend.core.config import settings
from backend.services.orchestrator import classify


def connect_db():
    client = ArangoClient(hosts=settings.ARANGO_URL)
    return client.db(settings.ARANGO_DB, username=settings.ARANGO_USER, password=settings.ARANGO_PASSWORD)


def select_eval_tickets(count=50):
    """Select stratified random tickets from synthetic data."""
    with open("data/synthetic/final/all_generated_tickets.json") as f:
        all_tickets = json.load(f)

    # Group by category
    by_category = defaultdict(list)
    for t in all_tickets:
        if t.get("category"):
            by_category[t["category"]].append(t)

    # Stratified sampling — proportional to category size
    total = sum(len(v) for v in by_category.values())
    eval_tickets = []

    for cat, tickets in by_category.items():
        n = max(1, round(count * len(tickets) / total))
        sampled = random.sample(tickets, min(n, len(tickets)))
        eval_tickets.extend(sampled)

    # Trim to exact count
    random.shuffle(eval_tickets)
    eval_tickets = eval_tickets[:count]

    print(f"Selected {len(eval_tickets)} eval tickets:")
    cat_counts = Counter(t["category"] for t in eval_tickets)
    for cat, n in sorted(cat_counts.items()):
        print(f"  {cat}: {n}")

    return eval_tickets


def find_and_remove_from_db(db, eval_tickets):
    """Find matching tickets in ArangoDB and temporarily remove them."""
    removed = []
    collection = db.collection("tickets")

    for t in eval_tickets:
        # Find by title match
        cursor = db.aql.execute(
            'FOR ticket IN tickets FILTER ticket.title == @title LIMIT 1 RETURN ticket',
            bind_vars={"title": t["title"]},
        )
        doc = next(cursor, None)
        if doc:
            removed.append(doc)
            collection.delete(doc["_key"])

    print(f"Removed {len(removed)} tickets from DB for evaluation")
    return removed


def restore_to_db(db, removed_docs):
    """Restore removed tickets back to ArangoDB."""
    collection = db.collection("tickets")
    for doc in removed_docs:
        # Clean ArangoDB metadata
        clean = {k: v for k, v in doc.items() if not k.startswith("_") or k == "_key"}
        try:
            collection.insert(clean)
        except Exception:
            pass  # May already exist if re-run
    print(f"Restored {len(removed_docs)} tickets to DB")


async def run_evaluation(db, eval_tickets):
    """Run each ticket through the classifier and collect results."""
    results = []
    total = len(eval_tickets)

    for i, ticket in enumerate(eval_tickets):
        title = ticket["title"]
        description = ticket.get("description", "")
        ground_truth = ticket["category"]

        start = time.time()
        try:
            result = await classify(
                title=title,
                description=description,
                db=db,
                redis_client=None,
            )
            predicted = result["category"]
            confidence = result["confidence"]
            agreement = result["agreement"]
            votes = result["classifier_votes"]
            elapsed = int((time.time() - start) * 1000)

            correct = predicted == ground_truth
            results.append({
                "title": title[:60],
                "ground_truth": ground_truth,
                "predicted": predicted,
                "correct": correct,
                "confidence": confidence,
                "agreement": agreement,
                "votes": {k: v.get("category") for k, v in votes.items()},
                "elapsed_ms": elapsed,
            })

            status = "✓" if correct else "✗"
            print(f"  [{i+1}/{total}] {status} {ground_truth:22} → {predicted:22} ({confidence:.1%}, {agreement}, {elapsed}ms) {title[:40]}")

        except Exception as exc:
            print(f"  [{i+1}/{total}] ERROR: {exc} — {title[:40]}")
            results.append({
                "title": title[:60],
                "ground_truth": ground_truth,
                "predicted": None,
                "correct": False,
                "confidence": 0,
                "agreement": "0/0",
                "votes": {},
                "elapsed_ms": 0,
            })

    return results


def print_report(results):
    """Print evaluation metrics."""
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / total if total > 0 else 0

    print("\n" + "=" * 70)
    print("EVALUATION REPORT")
    print("=" * 70)
    print(f"Total tickets: {total}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {accuracy:.1%}")
    print()

    # Per-category metrics
    categories = sorted(set(r["ground_truth"] for r in results))
    print(f"{'Category':<22} {'Correct':>8} {'Total':>6} {'Accuracy':>9} {'Avg Conf':>9}")
    print("-" * 58)

    for cat in categories:
        cat_results = [r for r in results if r["ground_truth"] == cat]
        cat_correct = sum(1 for r in cat_results if r["correct"])
        cat_total = len(cat_results)
        cat_acc = cat_correct / cat_total if cat_total > 0 else 0
        cat_conf = np.mean([r["confidence"] for r in cat_results]) if cat_results else 0
        print(f"{cat:<22} {cat_correct:>8} {cat_total:>6} {cat_acc:>8.1%} {cat_conf:>8.1%}")

    print()

    # Confusion matrix
    print("CONFUSION MATRIX (rows=actual, cols=predicted)")
    print(f"{'':>22}", end="")
    for cat in categories:
        print(f" {cat[:8]:>8}", end="")
    print()

    for actual in categories:
        print(f"{actual:<22}", end="")
        for predicted in categories:
            count = sum(1 for r in results if r["ground_truth"] == actual and r["predicted"] == predicted)
            print(f" {count:>8}", end="")
        print()

    print()

    # Misclassifications
    misses = [r for r in results if not r["correct"]]
    if misses:
        print(f"MISCLASSIFICATIONS ({len(misses)}):")
        for r in misses:
            print(f"  {r['ground_truth']:>22} → {r['predicted']:<22} conf={r['confidence']:.0%} votes={r['votes']} | {r['title']}")

    # Classifier agreement analysis
    print("\nCLASSIFIER AGREEMENT:")
    agreement_counts = Counter(r["agreement"] for r in results)
    for ag, cnt in sorted(agreement_counts.items()):
        ag_results = [r for r in results if r["agreement"] == ag]
        ag_acc = sum(1 for r in ag_results if r["correct"]) / len(ag_results)
        print(f"  {ag}: {cnt} tickets, {ag_acc:.0%} accuracy")

    # Average processing time
    avg_ms = np.mean([r["elapsed_ms"] for r in results])
    print(f"\nAvg processing time: {avg_ms:.0f}ms")

    return {
        "accuracy": accuracy,
        "total": total,
        "correct": correct,
        "per_category": {
            cat: {
                "correct": sum(1 for r in results if r["ground_truth"] == cat and r["correct"]),
                "total": sum(1 for r in results if r["ground_truth"] == cat),
            }
            for cat in categories
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate classifier accuracy")
    parser.add_argument("--count", type=int, default=50, help="Number of eval tickets")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)

    print("=" * 70)
    print("DeskMind Classifier Evaluation")
    print("=" * 70)
    print()

    # Connect
    db = connect_db()
    print(f"Connected to ArangoDB: {settings.ARANGO_DB}")

    # Select eval tickets
    eval_tickets = select_eval_tickets(args.count)
    print()

    # Remove from DB (so classifier can't cheat by finding itself)
    removed = find_and_remove_from_db(db, eval_tickets)
    print()

    # Run evaluation
    print("Running classification pipeline on eval tickets...")
    print()
    try:
        results = asyncio.run(run_evaluation(db, eval_tickets))
    finally:
        # Always restore tickets
        restore_to_db(db, removed)

    # Print report
    report = print_report(results)

    # Save results
    output_file = f"data/eval_results_{args.count}.json"
    with open(output_file, "w") as f:
        json.dump({"results": results, "summary": report}, f, indent=2)
    print(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    main()
