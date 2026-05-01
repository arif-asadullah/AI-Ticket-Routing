#!/usr/bin/env python3
"""
Load all seed data + synthetic tickets into ArangoDB.

Loads:
  - data/seed/seed_data.yaml (55 tickets + infrastructure + edges)
  - data/synthetic/final/all_generated_tickets.json (800 synthetic tickets)

Computes:
  - 384-dim embeddings for tickets, resolutions, runbooks (MiniLM)
  - Category centroids (average embeddings per category)
  - Auto-generated edges (affects, assigned_to, resolved_with, triggered_by, references)

Usage:
    source .venv/bin/activate
    python scripts/seed_db.py

Idempotent: truncates and reloads all data. Safe to run multiple times.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml
from arango import ArangoClient
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# ── Paths ──
SEED_FILE = Path("data/seed/seed_data.yaml")
SYNTHETIC_FILE = Path("data/synthetic/final/all_generated_tickets.json")

# ── ArangoDB connection (reads from .env or defaults) ──
try:
    from backend.core.config import settings
    ARANGO_URL = settings.ARANGO_URL
    ARANGO_DB = settings.ARANGO_DB
    ARANGO_USER = settings.ARANGO_USER
    ARANGO_PASSWORD = settings.ARANGO_PASSWORD
except ImportError:
    import os
    ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8530")
    ARANGO_DB = os.getenv("ARANGO_DB", "ticket_agent")
    ARANGO_USER = os.getenv("ARANGO_USER", "root")
    ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")

# ── Collections to truncate ──
DOCUMENT_COLLECTIONS = [
    "tickets", "teams", "engineers", "servers", "services",
    "network_devices", "error_codes", "runbooks", "resolutions",
    "routing_rules", "audit_log", "category_centroids", "users",
]
EDGE_COLLECTIONS = [
    "hosts", "managed_by", "depends_on", "member_of",
    "affects", "assigned_to", "resolved_with", "references", "triggered_by",
]


def connect():
    """Connect to ArangoDB."""
    print(f"Connecting to ArangoDB at {ARANGO_URL}...")
    client = ArangoClient(hosts=ARANGO_URL)

    # Ensure database exists
    sys_db = client.db("_system", username=ARANGO_USER, password=ARANGO_PASSWORD)
    if not sys_db.has_database(ARANGO_DB):
        sys_db.create_database(ARANGO_DB)
        print(f"  Created database: {ARANGO_DB}")

    db = client.db(ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASSWORD)
    print(f"  Connected to database: {ARANGO_DB}")
    return db


def truncate_all(db):
    """Truncate all collections for clean reload."""
    print("\nTruncating all collections...")
    for name in DOCUMENT_COLLECTIONS + EDGE_COLLECTIONS:
        if db.has_collection(name):
            db.collection(name).truncate()
    print(f"  Truncated {len(DOCUMENT_COLLECTIONS)} document + {len(EDGE_COLLECTIONS)} edge collections")


def load_embedding_model():
    """Load MiniLM sentence transformer model."""
    print("\nLoading MiniLM embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print(f"  Model loaded (384-dim embeddings)")
    return model


def compute_embeddings(model, texts):
    """Compute embeddings for a list of texts."""
    if not texts:
        return []
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return [emb.tolist() for emb in embeddings]


def load_seed_data():
    """Load seed_data.yaml."""
    print(f"\nLoading {SEED_FILE}...")
    with open(SEED_FILE) as f:
        data = yaml.safe_load(f)
    print(f"  Loaded: {len(data.get('tickets', []))} tickets, {len(data.get('teams', []))} teams, "
          f"{len(data.get('servers', []))} servers, {len(data.get('services', []))} services")
    return data


def load_synthetic_data():
    """Load synthetic tickets."""
    if not SYNTHETIC_FILE.exists():
        print(f"\n{SYNTHETIC_FILE} not found — skipping synthetic data")
        return []
    print(f"\nLoading {SYNTHETIC_FILE}...")
    with open(SYNTHETIC_FILE) as f:
        tickets = json.load(f)
    print(f"  Loaded: {len(tickets)} synthetic tickets")
    return tickets


# ── Phase 1: Load infrastructure (non-ticket data) ──

def load_simple_collection(db, name, docs):
    """Load documents into a collection."""
    if not docs:
        return
    col = db.collection(name)
    col.import_bulk(docs, on_duplicate="replace")
    print(f"  {name}: {len(docs)} documents")


def load_edges(db, edge_data):
    """Load manual edges from seed_data.yaml."""
    if not edge_data:
        return
    total = 0
    for edge_type, edges in edge_data.items():
        if not edges:
            continue
        col = db.collection(edge_type)
        col.import_bulk(edges, on_duplicate="replace")
        total += len(edges)
        print(f"  {edge_type}: {len(edges)} edges")
    return total


# ── Phase 2: Load tickets + resolutions + auto-edges ──

def load_tickets(db, model, seed_tickets, synthetic_tickets):
    """Load all tickets with embeddings."""
    all_tickets = []

    # Prepare seed tickets
    for t in seed_tickets:
        ticket = {k: v for k, v in t.items() if k not in ("affects_servers", "affects_services", "error_codes")}
        ticket["_source"] = "seed"
        ticket.setdefault("quality_score", "HIGH")
        ticket.setdefault("secondary_category", None)
        ticket.setdefault("classifier_votes", None)
        all_tickets.append((ticket, t))  # (doc_to_insert, original_with_refs)

    # Prepare synthetic tickets
    for t in synthetic_tickets:
        ticket = {k: v for k, v in t.items() if k not in ("affects_servers", "affects_services", "error_codes")}
        ticket["_source"] = "synthetic"
        ticket.setdefault("quality_score", "HIGH")
        ticket.setdefault("secondary_category", None)
        ticket.setdefault("classifier_votes", None)
        ticket.setdefault("status", "closed")
        ticket.setdefault("created_at", "2026-03-15T10:00:00Z")
        ticket.setdefault("resolved_at", "2026-03-15T12:00:00Z")
        ticket.setdefault("submitted_by", "synthetic@company.com")
        all_tickets.append((ticket, t))

    # Compute embeddings
    print(f"\n  Computing embeddings for {len(all_tickets)} tickets...")
    descriptions = [doc["description"] for doc, _ in all_tickets]
    embeddings = []
    batch_size = 64
    for i in tqdm(range(0, len(descriptions), batch_size), desc="  Embeddings"):
        batch = descriptions[i:i + batch_size]
        batch_emb = compute_embeddings(model, batch)
        embeddings.extend(batch_emb)

    # Set embeddings and insert
    col = db.collection("tickets")
    inserted_tickets = []  # (key, original_with_refs)

    for idx, (doc, original) in enumerate(all_tickets):
        doc["embedding"] = embeddings[idx]

    docs_to_insert = [doc for doc, _ in all_tickets]
    result = col.import_bulk(docs_to_insert, on_duplicate="replace")

    # Get inserted keys
    all_docs = list(col.all())
    key_map = {}  # title -> _key
    for d in all_docs:
        key_map[d["title"]] = d["_key"]

    # Build (key, original) mapping for edge creation
    for doc, original in all_tickets:
        key = key_map.get(doc["title"])
        if key:
            inserted_tickets.append((key, original))

    print(f"  tickets: {len(all_docs)} documents with embeddings")
    return inserted_tickets, all_docs


def load_resolutions(db, model, seed_resolutions, inserted_tickets):
    """Load resolutions and create resolved_with edges."""
    col = db.collection("resolutions")
    edge_col = db.collection("resolved_with")
    ref_col = db.collection("references")

    # Build title -> ticket_key map
    title_to_key = {}
    for key, original in inserted_tickets:
        title_to_key[original["title"]] = key

    # Also create resolutions from synthetic tickets that have resolution_steps
    all_resolutions = []

    # Seed resolutions (from seed_data.yaml)
    if seed_resolutions:
        for r in seed_resolutions:
            title = r.get("ticket_title") or r.get("title", "")
            ticket_key = title_to_key.get(title)
            all_resolutions.append({
                "steps": r.get("steps", []),
                "effectiveness": r.get("effectiveness", 0.85),
                "references_runbook": r.get("references_runbook"),
                "ticket_key": ticket_key,
                "ticket_title": title,
            })

    # Synthetic ticket resolutions
    for key, original in inserted_tickets:
        if original.get("resolution_steps") and original.get("_source_file", original.get("source_model", "")) != "seed":
            all_resolutions.append({
                "steps": original["resolution_steps"],
                "effectiveness": original.get("resolution_effectiveness", 0.85),
                "references_runbook": original.get("references_runbook"),
                "ticket_key": key,
                "ticket_title": original["title"],
            })

    if not all_resolutions:
        print("  resolutions: 0 (no resolution data)")
        return

    # Compute embeddings for resolutions
    print(f"\n  Computing embeddings for {len(all_resolutions)} resolutions...")
    res_texts = [" ".join(r["steps"]) for r in all_resolutions]
    res_embeddings = []
    for i in tqdm(range(0, len(res_texts), 64), desc="  Res embeddings"):
        batch = res_texts[i:i + 64]
        batch_emb = compute_embeddings(model, batch)
        res_embeddings.extend(batch_emb)

    # Insert resolutions
    res_docs = []
    for idx, r in enumerate(all_resolutions):
        res_docs.append({
            "steps": r["steps"],
            "effectiveness": r["effectiveness"],
            "embedding": res_embeddings[idx],
        })

    col.import_bulk(res_docs, on_duplicate="replace")

    # Get resolution keys
    res_all = list(col.all())
    print(f"  resolutions: {len(res_all)} documents with embeddings")

    # Create resolved_with edges
    resolved_edges = []
    references_edges = []
    for idx, r in enumerate(all_resolutions):
        if idx < len(res_all) and r["ticket_key"]:
            res_key = res_all[idx]["_key"]
            resolved_edges.append({
                "_from": f"tickets/{r['ticket_key']}",
                "_to": f"resolutions/{res_key}",
            })
            # references edge (resolution -> runbook)
            if r.get("references_runbook"):
                references_edges.append({
                    "_from": f"resolutions/{res_key}",
                    "_to": f"runbooks/{r['references_runbook']}",
                })

    if resolved_edges:
        edge_col.import_bulk(resolved_edges, on_duplicate="replace")
        print(f"  resolved_with: {len(resolved_edges)} edges")
    if references_edges:
        ref_col.import_bulk(references_edges, on_duplicate="replace")
        print(f"  references: {len(references_edges)} edges")


def create_auto_edges(db, inserted_tickets, routing_rules):
    """Create affects, assigned_to, and triggered_by edges for all tickets."""
    affects_col = db.collection("affects")
    assigned_col = db.collection("assigned_to")
    triggered_col = db.collection("triggered_by")

    # Build routing rules lookup: (category, priority) -> team_key
    rule_map = {}
    for rule in routing_rules:
        key = (rule["category"], rule["priority"])
        rule_map[key] = rule["target_team"]

    affects_edges = []
    assigned_edges = []
    triggered_edges = []

    for ticket_key, original in tqdm(inserted_tickets, desc="  Auto-edges"):
        # affects edges (ticket -> server)
        for srv in original.get("affects_servers") or []:
            affects_edges.append({
                "_from": f"tickets/{ticket_key}",
                "_to": f"servers/{srv}",
            })
        # affects edges (ticket -> service)
        for svc in original.get("affects_services") or []:
            affects_edges.append({
                "_from": f"tickets/{ticket_key}",
                "_to": f"services/{svc}",
            })
        # assigned_to edge (ticket -> team)
        cat = original.get("category", "")
        pri = original.get("priority", "medium")
        team_key = rule_map.get((cat, pri))
        if team_key:
            assigned_edges.append({
                "_from": f"tickets/{ticket_key}",
                "_to": f"teams/{team_key}",
            })
        # triggered_by edges (error_code -> ticket)
        # Only create edges for error codes that exist in the collection (ERR-XX-XXX format)
        for err in original.get("error_codes") or []:
            if err and db.collection("error_codes").has(err):
                triggered_edges.append({
                    "_from": f"error_codes/{err}",
                    "_to": f"tickets/{ticket_key}",
                })

    if affects_edges:
        affects_col.import_bulk(affects_edges, on_duplicate="replace")
        print(f"  affects: {len(affects_edges)} edges")
    if assigned_edges:
        assigned_col.import_bulk(assigned_edges, on_duplicate="replace")
        print(f"  assigned_to: {len(assigned_edges)} edges")
    if triggered_edges:
        triggered_col.import_bulk(triggered_edges, on_duplicate="replace")
        print(f"  triggered_by: {len(triggered_edges)} edges")


# ── Phase 3: Compute centroids ──

def compute_centroids(db, all_ticket_docs):
    """Compute average embedding per category and save to category_centroids."""
    print("\nComputing category centroids...")
    col = db.collection("category_centroids")
    col.truncate()

    # Group embeddings by category
    category_embeddings = {}
    for doc in all_ticket_docs:
        cat = doc.get("category")
        emb = doc.get("embedding")
        if cat and emb:
            if cat not in category_embeddings:
                category_embeddings[cat] = []
            category_embeddings[cat].append(emb)

    now = datetime.now(timezone.utc).isoformat()
    centroids = []
    for cat, embeddings in sorted(category_embeddings.items()):
        avg = np.mean(embeddings, axis=0).tolist()
        centroids.append({
            "_key": cat.lower().replace(" ", "-"),
            "category": cat,
            "embedding": avg,
            "ticket_count": len(embeddings),
            "last_updated": now,
        })
        print(f"  {cat}: {len(embeddings)} tickets → centroid computed")

    col.import_bulk(centroids, on_duplicate="replace")
    print(f"  category_centroids: {len(centroids)} entries")


# ── Compute runbook embeddings ──

def load_users(db, users_data):
    """Load user accounts with hashed passwords."""
    if not users_data:
        return
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    docs = []
    for u in users_data:
        docs.append({
            "email": u["email"],
            "password_hash": pwd_context.hash(u["password"]),
            "role": u["role"],
            "first_name": u.get("first_name", ""),
            "last_name": u.get("last_name", ""),
            "engineer_key": u.get("engineer_key"),
            "team_key": u.get("team_key"),
            "is_active": True,
        })
    col = db.collection("users")
    col.import_bulk(docs, on_duplicate="replace")
    print(f"  users: {len(docs)} accounts (passwords hashed)")


def load_runbooks_with_embeddings(db, model, runbooks):
    """Load runbooks with embeddings."""
    if not runbooks:
        return
    texts = [f"{r['title']} {' '.join(r.get('steps', []))}" for r in runbooks]
    embeddings = compute_embeddings(model, texts)
    for i, r in enumerate(runbooks):
        r["embedding"] = embeddings[i]

    col = db.collection("runbooks")
    col.import_bulk(runbooks, on_duplicate="replace")
    print(f"  runbooks: {len(runbooks)} documents with embeddings")


# ── Main ──

def main():
    start_time = time.time()
    print("=" * 60)
    print("DeskMind Seed Database Loader")
    print("=" * 60)

    # Connect
    db = connect()

    # Truncate
    truncate_all(db)

    # Load embedding model
    model = load_embedding_model()

    # Load data files
    seed_data = load_seed_data()
    synthetic_tickets = load_synthetic_data()

    # ── Phase 1: Infrastructure ──
    print("\n── Phase 1: Loading infrastructure ──")
    load_simple_collection(db, "teams", seed_data.get("teams", []))
    load_simple_collection(db, "servers", seed_data.get("servers", []))
    load_simple_collection(db, "services", seed_data.get("services", []))
    load_simple_collection(db, "engineers", seed_data.get("engineers", []))
    load_simple_collection(db, "network_devices", seed_data.get("network_devices", []))
    load_simple_collection(db, "error_codes", seed_data.get("error_codes", []))
    load_runbooks_with_embeddings(db, model, seed_data.get("runbooks", []))
    load_simple_collection(db, "routing_rules", seed_data.get("routing_rules", []))
    load_users(db, seed_data.get("users", []))

    # Load manual edges
    print("\n  Loading manual edges...")
    load_edges(db, seed_data.get("edges", {}))

    # ── Phase 2: Tickets + Resolutions + Auto-edges ──
    print("\n── Phase 2: Loading tickets + resolutions ──")
    seed_tickets = seed_data.get("tickets", [])
    inserted_tickets, all_ticket_docs = load_tickets(db, model, seed_tickets, synthetic_tickets)

    # Load resolutions
    print("\n  Loading resolutions...")
    load_resolutions(db, model, seed_data.get("resolutions", []), inserted_tickets)

    # Create auto-edges for ALL tickets
    print("\n  Creating auto-edges for all tickets...")
    create_auto_edges(db, inserted_tickets, seed_data.get("routing_rules", []))

    # ── Phase 3: Centroids ──
    print("\n── Phase 3: Computing centroids ──")
    compute_centroids(db, all_ticket_docs)

    # ── Summary ──
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("SEED COMPLETE")
    print("=" * 60)

    # Count everything
    total_docs = 0
    total_edges = 0
    for name in DOCUMENT_COLLECTIONS:
        if db.has_collection(name):
            count = db.collection(name).count()
            total_docs += count
    for name in EDGE_COLLECTIONS:
        if db.has_collection(name):
            count = db.collection(name).count()
            total_edges += count

    print(f"  Document nodes: {total_docs}")
    print(f"  Edge connections: {total_edges}")
    print(f"  Time: {elapsed:.1f} seconds")
    print(f"\nVerify in ArangoDB UI: http://localhost:8530")


if __name__ == "__main__":
    main()
