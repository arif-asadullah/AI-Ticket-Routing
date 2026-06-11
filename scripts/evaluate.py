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

import httpx
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


def _cosine(a, b):
    """Cosine similarity between two embedding vectors (0..1 for these embeddings)."""
    a = np.array(a, dtype=np.float32)
    b = np.array(b, dtype=np.float32)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ── LLM-as-judge ──
# An independent LLM scores each routing decision WITHOUT being shown our gold
# label, so it is a second opinion rather than a re-check of our own answers.
# NOTE: uses the same local Qwen model as the classifier, so there is a known
# self-judging bias; swapping OLLAMA_MODEL/endpoint for a different/larger judge
# model would make this stricter.
JUDGE_SYSTEM_PROMPT = """You are an impartial senior IT operations reviewer auditing an AI ticket-routing system. Be critical and objective — do NOT assume the AI is correct.

The 6 valid categories are: Infrastructure, Application, Database, Network, Security, Access Management.

You will be given a support ticket and the AI's decision (assigned category + suggested resolution). Score the decision on two axes, each an integer 1-5:
- routing_score: Is the assigned category the correct team/domain for this ticket's ROOT CAUSE? (5 = clearly correct, 3 = defensible but arguable, 1 = clearly wrong)
- resolution_score: Are the suggested resolution steps relevant and actionable for THIS ticket? (5 = directly actionable, 1 = irrelevant/empty; if no resolution was provided, score 1)

Return ONLY valid JSON: {"routing_score": <1-5>, "resolution_score": <1-5>, "reasoning": "<one sentence>"}"""


def _parse_judge_json(text: str) -> dict:
    """Parse JSON from the judge LLM response (tolerant of code fences/prose)."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3].strip()
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                return {}
    return {}


async def judge_decision(title, description, predicted, resolution_steps):
    """Ask an independent LLM to score the routing + resolution decision. Returns dict or None."""
    res_text = "; ".join(resolution_steps) if resolution_steps else "none provided"
    user_prompt = (
        f"TICKET:\nTitle: {title}\nDescription: {description}\n\n"
        f"AI DECISION:\nAssigned category: {predicted}\nSuggested resolution: {res_text}\n\n"
        f"Score the decision."
    )
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/v1/chat/completions",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0,
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        data = _parse_judge_json(content)
        rs = max(1, min(5, int(data.get("routing_score", 0) or 0)))
        res_s = max(1, min(5, int(data.get("resolution_score", 0) or 0)))
        return {"routing_score": rs, "resolution_score": res_s, "reasoning": str(data.get("reasoning", ""))[:200]}
    except Exception:
        return None


def load_test_tickets():
    """Load fixed test set."""
    with open(TEST_SET) as f:
        tickets = json.load(f)
    # Filter out tickets with no expected category (vague ones) for accuracy calc
    # but still run them to measure confidence/quality
    return tickets


# ── Train/test leak prevention (holdout) ──
# Test tickets (or near-duplicate copies) may live inside the `tickets`
# collection that the KNN/centroid classifiers retrieve from. Scoring against a
# corpus that contains the answer inflates accuracy. These helpers temporarily
# remove contaminants, recompute centroids on the cleaned corpus, and ALWAYS
# restore afterward (crash-safe via an on-disk recovery snapshot).

HOLDOUT_SNAPSHOT = EVAL_DIR / ".holdout_snapshot.json"
HOLDOUT_SIM_THRESHOLD = 0.95


def find_contaminants(db, tickets, model):
    """Return {ticket_key: full_doc} for DB tickets equal to / near-duplicate of any test ticket."""
    from backend.services.orchestrator import preprocess_text
    snapshots = {}
    for tk in tickets:
        title = tk["title"]
        desc = tk["description"]
        # 1) Exact title match (catches verbatim seed/synthetic duplicates)
        cur = db.aql.execute(
            "FOR t IN tickets FILTER t.title == @title RETURN t",
            bind_vars={"title": title},
        )
        for d in cur:
            snapshots[d["_key"]] = d
        # 2) Near-duplicate by embedding similarity (catches paraphrases)
        emb = model.encode(preprocess_text(title, desc)).tolist()
        cur = db.aql.execute(
            "FOR t IN tickets FILTER t.embedding != null "
            "LET sim = COSINE_SIMILARITY(t.embedding, @emb) FILTER sim >= @thr RETURN t",
            bind_vars={"emb": emb, "thr": HOLDOUT_SIM_THRESHOLD},
        )
        for d in cur:
            snapshots[d["_key"]] = d
    return snapshots


def _strip_meta(doc):
    """Keep _key but drop _id/_rev so the doc can be re-inserted."""
    return {k: v for k, v in doc.items() if k not in ("_id", "_rev")}


def remove_contaminants(db, snapshots):
    """Delete contaminant tickets. Returns list of keys that FAILED to delete (logged, not silent)."""
    col = db.collection("tickets")
    failed = []
    for key in snapshots:
        try:
            col.delete(key)
        except Exception as exc:
            failed.append(key)
            print(f"    [warn] failed to remove {key}: {exc}")
    return failed


def restore_contaminants(db, snapshots):
    """Re-insert removed tickets and VERIFY each is present. Returns list of keys that failed to restore."""
    col = db.collection("tickets")
    failed = []
    for key, doc in snapshots.items():
        try:
            col.insert(_strip_meta(doc), overwrite=True)
        except Exception as exc:
            print(f"    [warn] insert failed for {key}: {exc}")
        # Verify the doc is actually back before trusting the restore
        try:
            if not col.has(key):
                failed.append(key)
        except Exception:
            failed.append(key)
    return failed


def _recover_if_interrupted(db):
    """If a previous holdout run was killed mid-way, restore from the on-disk snapshot.
    The snapshot is deleted ONLY after a fully-verified restore — otherwise it is kept
    so a later run can retry (prevents permanent data loss)."""
    if not HOLDOUT_SNAPSHOT.exists():
        return
    try:
        with open(HOLDOUT_SNAPSHOT) as f:
            snaps = json.load(f)
    except Exception as exc:
        print(f"  [recovery] Could not read snapshot ({exc}); keeping it for manual inspection.")
        return
    if not snaps:
        HOLDOUT_SNAPSHOT.unlink(missing_ok=True)
        return

    print(f"  [recovery] Previous run left {len(snaps)} tickets removed — restoring...")
    failed = restore_contaminants(db, snaps)
    if failed:
        print(f"  [recovery] WARNING: {len(failed)}/{len(snaps)} ticket(s) NOT restored — KEEPING snapshot for retry: {failed[:5]}")
        return  # keep snapshot; do NOT delete the only backup
    try:
        from backend.services.corrections import recompute_centroids
        recompute_centroids(db)
    except Exception as exc:
        print(f"  [recovery] Tickets restored but centroid recompute failed ({exc}); keeping snapshot.")
        return
    HOLDOUT_SNAPSHOT.unlink(missing_ok=True)
    print(f"  [recovery] Restored {len(snaps)} tickets + recomputed centroids")


async def run_evaluation(db, tickets, judge=True):
    """Run each ticket through the pipeline and collect results."""
    results = []
    total = len(tickets)

    # Embedding model (reused for resolution semantic-similarity scoring)
    model = get_embedding_model()

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

            # ── Semantic similarity scoring of the suggested resolution ──
            # Measures how on-topic the proposed fix is vs the ticket problem
            # (cosine of embeddings, 0..1). Prefer AI-generated steps if present.
            res_steps = None
            ai_gen = result.get("ai_generated_resolution")
            if ai_gen and ai_gen.get("steps"):
                res_steps = ai_gen["steps"]
            elif result.get("suggested_resolution"):
                res_steps = result["suggested_resolution"]

            resolution_sim = None
            if res_steps:
                prob_emb = model.encode(f"{title}. {description}")
                res_emb = model.encode(" ".join(res_steps))
                resolution_sim = round(_cosine(prob_emb, res_emb), 4)

            # ── LLM-as-judge: independent second opinion on the decision ──
            judge_result = None
            if judge:
                judge_result = await judge_decision(title, description, predicted, res_steps)

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
                "resolution_semantic_sim": resolution_sim,
                "judge": judge_result,
                "votes": {k: {"category": v.get("category"), "confidence": round(v.get("confidence", 0), 3)} for k, v in votes.items()},
                "elapsed_ms": elapsed,
            }
            results.append(entry)

            if judge_result:
                print(f"            judge: routing={judge_result['routing_score']}/5 resolution={judge_result['resolution_score']}/5")

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

    # Semantic similarity scoring of suggested resolutions (over all tickets that got one)
    res_sims = [r["resolution_semantic_sim"] for r in results if r.get("resolution_semantic_sim") is not None]
    resolution_semantic_sim = round(float(np.mean(res_sims)), 4) if res_sims else 0.0
    resolution_coverage = len(res_sims)

    # LLM-as-judge aggregate (independent reviewer scores, 1-5)
    judged = [r["judge"] for r in results if r.get("judge")]
    if judged:
        judge_routing = round(float(np.mean([j["routing_score"] for j in judged])), 3)
        judge_resolution = round(float(np.mean([j["resolution_score"] for j in judged])), 3)
        judge_pass_rate = round(sum(1 for j in judged if j["routing_score"] >= 4) / len(judged), 4)
        judge_coverage = len(judged)
    else:
        judge_routing = judge_resolution = judge_pass_rate = 0.0
        judge_coverage = 0

    # Per-category metrics: precision, recall, F1 (computed from TP/FP/FN).
    # NOTE: the previous "accuracy" key here was really RECALL (TP/(TP+FN)) and
    # ignored false positives. We now report precision/recall/F1 properly.
    categories = sorted(set(r["expected"] for r in scorable if r["expected"]))
    per_category = {}
    for cat in categories:
        tp = sum(1 for r in scorable if r["expected"] == cat and r["predicted"] == cat)
        fp = sum(1 for r in scorable if r["expected"] != cat and r["predicted"] == cat)
        fn = sum(1 for r in scorable if r["expected"] == cat and r["predicted"] != cat)
        support = tp + fn  # number of tickets whose TRUE label is cat
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
        cat_conf = np.mean([r["confidence"] for r in scorable if r["expected"] == cat]) if support else 0
        per_category[cat] = {
            "support": support,
            "correct": tp,
            "total": support,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "accuracy": round(recall, 4),  # kept for backward-compat (equals recall)
            "avg_confidence": round(float(cat_conf), 4),
        }

    # Macro F1 (unweighted mean across classes) and weighted F1 (by support)
    if per_category:
        macro_precision = round(float(np.mean([m["precision"] for m in per_category.values()])), 4)
        macro_recall = round(float(np.mean([m["recall"] for m in per_category.values()])), 4)
        macro_f1 = round(float(np.mean([m["f1"] for m in per_category.values()])), 4)
        total_support = sum(m["support"] for m in per_category.values()) or 1
        weighted_f1 = round(float(sum(m["f1"] * m["support"] for m in per_category.values()) / total_support), 4)
    else:
        macro_precision = macro_recall = macro_f1 = weighted_f1 = 0.0

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
            "macro_precision": macro_precision,
            "macro_recall": macro_recall,
            "macro_f1": macro_f1,
            "weighted_f1": weighted_f1,
            "resolution_semantic_sim": resolution_semantic_sim,
            "resolution_coverage": resolution_coverage,
            "llm_judge_routing": judge_routing,
            "llm_judge_resolution": judge_resolution,
            "llm_judge_pass_rate": judge_pass_rate,
            "llm_judge_coverage": judge_coverage,
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
    if "holdout" in report:
        ho = report["holdout"]
        print(f"  Holdout: {'ON (leak-free)' if ho else 'OFF (train/test leak)'} | contaminants removed: {report.get('contaminants_removed', 0)}")
    print("=" * 72)
    print()
    print(f"  Overall Accuracy:    {s['correct']}/{s['total_scorable']} ({s['accuracy']:.1%})")
    print(f"  Macro F1:            {s.get('macro_f1', 0):.3f}   (macro P: {s.get('macro_precision', 0):.3f}  macro R: {s.get('macro_recall', 0):.3f})")
    print(f"  Weighted F1:         {s.get('weighted_f1', 0):.3f}")
    if s.get("resolution_coverage"):
        print(f"  Resolution Sem.Sim:  {s.get('resolution_semantic_sim', 0):.3f}  (over {s['resolution_coverage']} tickets with a suggested fix)")
    if s.get("llm_judge_coverage"):
        print(f"  LLM-as-Judge:        routing {s.get('llm_judge_routing', 0):.2f}/5  resolution {s.get('llm_judge_resolution', 0):.2f}/5  pass-rate {s.get('llm_judge_pass_rate', 0):.1%}  (over {s['llm_judge_coverage']} tickets)")
    print(f"  Avg Confidence:      {s['avg_confidence']:.3f}")
    print(f"  Avg Processing Time: {s['avg_processing_time_ms']:.0f}ms")
    print()

    # Per-category table — precision / recall / F1 (the real metrics, not just recall)
    print(f"  {'Category':<22} {'Prec':>7} {'Recall':>7} {'F1':>7} {'Support':>8}")
    print(f"  {'-'*54}")
    for cat, m in sorted(report["per_category"].items()):
        print(f"  {cat:<22} {m.get('precision', 0):>6.1%} {m.get('recall', 0):>6.1%} {m.get('f1', 0):>6.1%} {m.get('support', m.get('total', 0)):>8}")
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
    print(f"  {'Tag':<25} {'Accuracy':>10} {'Delta':>8} {'MacroF1':>9} {'Avg Conf':>10} {'Avg Time':>10}")
    print(f"  {'-'*75}")
    baseline_acc = reports[0]["summary"]["accuracy"]
    for r in reports:
        s = r["summary"]
        delta = s["accuracy"] - baseline_acc
        delta_str = f"+{delta:.1%}" if delta > 0 else f"{delta:.1%}" if delta < 0 else "---"
        if r == reports[0]:
            delta_str = "baseline"
        print(f"  {r['tag']:<25} {s['accuracy']:>9.1%} {delta_str:>8} {s.get('macro_f1', 0):>9.3f} {s['avg_confidence']:>9.3f} {s['avg_processing_time_ms']:>8.0f}ms")
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
    parser.add_argument("--no-judge", action="store_true", help="Skip the LLM-as-judge pass (faster iteration; default is judge ON)")
    parser.add_argument("--no-holdout", action="store_true", help="Skip removing test-set contaminants from the corpus (faster, but leaks train/test; default is holdout ON)")
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

    judge = not args.no_judge
    holdout = not args.no_holdout

    # ── Holdout: remove test-set contaminants so the benchmark measures generalization ──
    snapshots = {}
    if holdout:
        from backend.services.corrections import recompute_centroids
        _recover_if_interrupted(db)  # restore any leftovers from a prior crashed run
        model = get_embedding_model()
        print("  Holdout ON — scanning corpus for test-set contaminants...")
        snapshots = find_contaminants(db, tickets, model)
        print(f"    Found {len(snapshots)} contaminant ticket(s) in corpus (exact title or >= {HOLDOUT_SIM_THRESHOLD} similar)")
        if snapshots:
            # Persist a recovery snapshot to disk BEFORE deleting (crash safety)
            with open(HOLDOUT_SNAPSHOT, "w") as f:
                json.dump(snapshots, f)
            remove_contaminants(db, snapshots)
            recompute_centroids(db)
            print(f"    Removed {len(snapshots)} ticket(s) and recomputed centroids on cleaned corpus")
    else:
        print("  Holdout OFF — WARNING: corpus may contain test tickets (train/test leak, optimistic numbers)")
    print()

    # Run evaluation (always restore in finally, even on crash)
    print(f"  Running classification pipeline... (LLM-as-judge: {'ON' if judge else 'OFF'})")
    print()
    try:
        results = asyncio.run(run_evaluation(db, tickets, judge=judge))
    finally:
        if holdout and snapshots:
            from backend.services.corrections import recompute_centroids
            failed = restore_contaminants(db, snapshots)
            if failed:
                # Restore incomplete — KEEP the snapshot so a re-run can recover.
                print(f"\n  WARNING: {len(failed)}/{len(snapshots)} ticket(s) failed to restore.")
                print(f"  Snapshot KEPT at {HOLDOUT_SNAPSHOT} — re-run evaluate.py to retry recovery.")
            else:
                recompute_centroids(db)
                HOLDOUT_SNAPSHOT.unlink(missing_ok=True)
                print(f"\n  Restored {len(snapshots)} ticket(s) + recomputed original centroids")

    # Build and print report
    report = build_report(results, args.tag)
    report["holdout"] = holdout
    report["contaminants_removed"] = len(snapshots)
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
