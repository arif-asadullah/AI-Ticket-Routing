#!/usr/bin/env python3
"""
Tune classifier weights for the 4-classifier ensemble (ATR-55).

Tests different weight combinations on eval tickets and finds the optimal set.
Does NOT call the full pipeline — uses cached classifier votes from a previous
eval run to instantly compute accuracy for each weight combination.

Steps:
1. Run eval_classifier.py first to get classifier votes for each ticket
2. This script reads those votes and re-aggregates with different weights
3. Tests thousands of weight combinations in seconds
4. Reports the best weights

Usage:
    # First, run eval to collect votes (if not already done):
    python scripts/eval_classifier.py --count 50 --seed 42

    # Then tune weights:
    python scripts/tune_weights.py
"""

import json
import sys
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_eval_results():
    """Load eval results with classifier votes."""
    with open("data/eval_results_50.json") as f:
        data = json.load(f)
    return data["results"]


def aggregate_with_weights(votes, weights):
    """Re-aggregate classifier votes with given weights. Returns predicted category."""
    category_scores = {}

    for classifier, weight in weights.items():
        if classifier not in votes or votes[classifier] is None:
            continue
        cat = votes[classifier]
        if cat is None:
            continue
        category_scores[cat] = category_scores.get(cat, 0) + weight

    if not category_scores:
        return None

    # Normalize weights for active classifiers
    return max(category_scores, key=category_scores.get)


def evaluate_weights(results, weights):
    """Compute accuracy for a given weight set."""
    correct = 0
    total = 0

    for r in results:
        if r["ground_truth"] is None:
            continue
        total += 1
        predicted = aggregate_with_weights(r["votes"], weights)
        if predicted == r["ground_truth"]:
            correct += 1

    return correct / total if total > 0 else 0, correct, total


def main():
    print("=" * 60)
    print("DeskMind Weight Tuning")
    print("=" * 60)
    print()

    results = load_eval_results()
    print(f"Loaded {len(results)} eval results")

    # Current weights
    current = {"llm": 0.40, "knn": 0.30, "centroid": 0.20, "keyword": 0.10}
    current_acc, current_correct, current_total = evaluate_weights(results, current)
    print(f"\nCurrent weights: LLM={current['llm']}, KNN={current['knn']}, CEN={current['centroid']}, KEY={current['keyword']}")
    print(f"Current accuracy: {current_acc:.1%} ({current_correct}/{current_total})")
    print()

    # Test all weight combinations (step 0.05, must sum to 1.0)
    print("Testing weight combinations (step=0.05)...")
    steps = [i / 20 for i in range(1, 20)]  # 0.05 to 0.95

    best_acc = 0
    best_weights = None
    best_correct = 0
    tested = 0
    all_results = []

    for llm_w in steps:
        for knn_w in steps:
            for cen_w in steps:
                key_w = round(1.0 - llm_w - knn_w - cen_w, 2)
                if key_w < 0.05 or key_w > 0.95:
                    continue
                if abs(llm_w + knn_w + cen_w + key_w - 1.0) > 0.001:
                    continue

                weights = {"llm": llm_w, "knn": knn_w, "centroid": cen_w, "keyword": key_w}
                acc, correct, total = evaluate_weights(results, weights)
                tested += 1

                all_results.append({
                    "weights": weights,
                    "accuracy": acc,
                    "correct": correct,
                })

                if acc > best_acc or (acc == best_acc and correct > best_correct):
                    best_acc = acc
                    best_weights = weights.copy()
                    best_correct = correct

    print(f"Tested {tested} combinations")
    print()

    # Sort and show top 10
    all_results.sort(key=lambda x: (-x["accuracy"], -x["correct"]))

    print("TOP 10 WEIGHT COMBINATIONS:")
    print(f"{'Rank':<5} {'LLM':>5} {'KNN':>5} {'CEN':>5} {'KEY':>5} {'Accuracy':>9} {'Correct':>8}")
    print("-" * 48)
    for i, r in enumerate(all_results[:10]):
        w = r["weights"]
        marker = " ←" if w == current else ""
        print(f"{i+1:<5} {w['llm']:>5.2f} {w['knn']:>5.2f} {w['centroid']:>5.2f} {w['keyword']:>5.2f} {r['accuracy']:>8.1%} {r['correct']:>8}{marker}")

    print()
    print(f"BEST WEIGHTS: LLM={best_weights['llm']}, KNN={best_weights['knn']}, CEN={best_weights['centroid']}, KEY={best_weights['keyword']}")
    print(f"BEST ACCURACY: {best_acc:.1%} ({best_correct}/{current_total})")
    print()

    # Compare with current
    improvement = best_acc - current_acc
    if improvement > 0:
        print(f"IMPROVEMENT: +{improvement:.1%} over current weights")
    elif improvement == 0:
        print("NO IMPROVEMENT — current weights are already optimal (or tied)")
    else:
        print(f"Current weights are better by {-improvement:.1%}")

    print()

    # Show accuracy by agreement level for best weights
    print("BEST WEIGHTS — ACCURACY BY AGREEMENT:")
    agreement_buckets = defaultdict(list)
    for r in results:
        if r["ground_truth"] is None:
            continue
        predicted = aggregate_with_weights(r["votes"], best_weights)
        correct = predicted == r["ground_truth"]

        # Count how many classifiers agree with the prediction
        votes = r["votes"]
        agreeing = sum(1 for v in votes.values() if v == predicted)
        total_voters = sum(1 for v in votes.values() if v is not None)
        agreement_buckets[f"{agreeing}/{total_voters}"].append(correct)

    for ag in sorted(agreement_buckets.keys()):
        items = agreement_buckets[ag]
        acc = sum(items) / len(items)
        print(f"  {ag}: {len(items)} tickets, {acc:.0%} accuracy")

    # Save results
    output = {
        "current_weights": current,
        "current_accuracy": current_acc,
        "best_weights": best_weights,
        "best_accuracy": best_acc,
        "improvement": improvement,
        "tested_combinations": tested,
        "top_10": all_results[:10],
    }

    with open("data/weight_tuning_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to data/weight_tuning_results.json")


if __name__ == "__main__":
    main()
