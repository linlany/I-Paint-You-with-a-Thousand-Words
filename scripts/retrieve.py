#!/usr/bin/env python3
"""Retrieve local corpus records with a transparent lexical baseline."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set, Tuple

WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
ADMITTED_RIGHTS = {"public_domain", "user_provided_licensed", "public_domain_or_fixture"}


def tokens(value: str) -> Set[str]:
    return {token.lower() for token in WORD_RE.findall(value)}


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    values: List[Dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: record is not an object")
            values.append(value)
    return values


def load_queries(path: str) -> List[Dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if isinstance(value, dict):
        value = value.get("queries", [])
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("queries must be an array or an object containing a queries array")
    return value


def retrieve(records: Iterable[Dict[str, Any]], queries: Iterable[Dict[str, Any]], top_k_per_facet: int, include_unadmitted: bool) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    for query in queries:
        facet = str(query.get("facet", "unknown"))
        query_terms = tokens(" ".join(str(item) for item in query.get("terms", []) if item))
        if not query_terms:
            query_terms = tokens(str(query.get("query", "")))
        scored: List[Tuple[float, str, Dict[str, Any]]] = []
        for record in records:
            rights = str(record.get("license_status", ""))
            if not include_unadmitted and rights not in ADMITTED_RIGHTS:
                continue
            text = str(record.get("text", ""))
            text_terms = tokens(text)
            overlap = len(query_terms & text_terms) / max(1, len(query_terms))
            phrase_bonus = 0.20 if str(query.get("query", "")).strip().lower() in text.lower() else 0.0
            score = min(1.0, overlap + phrase_bonus)
            if score <= 0:
                continue
            key = str(record.get("record_id") or f"{record.get('source_id', '')}:{record.get('location', '')}:{text}")
            scored.append((score, key, record))
        scored.sort(key=lambda item: (-item[0], item[1]))
        for score, key, record in scored[: max(0, top_k_per_facet)]:
            candidate = by_key.setdefault(key, dict(record))
            facets = set(candidate.get("query_facets", []))
            facets.add(facet)
            candidate["candidate_id"] = key
            candidate["query_facets"] = sorted(facets)
            candidate["retrieval_score"] = max(float(candidate.get("retrieval_score", 0.0)), round(score, 6))
            candidate["semantic_score"] = candidate["retrieval_score"]
            if "source_quality" not in candidate:
                candidate["source_quality"] = 1.0 if str(record.get("license_status")) in ADMITTED_RIGHTS else 0.0
            by_key[key] = candidate
    return sorted(by_key.values(), key=lambda item: (-float(item.get("retrieval_score", 0.0)), str(item.get("record_id", ""))))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True, help="Normalized corpus JSONL")
    parser.add_argument("--queries", required=True, help="Query JSON from build_queries.py")
    parser.add_argument("--out", required=True, help="Candidate JSONL output")
    parser.add_argument("--top-k-per-facet", type=int, default=12)
    parser.add_argument("--include-unadmitted", action="store_true", help="Include rights_review/restricted records for review")
    args = parser.parse_args()

    candidates = retrieve(load_jsonl(args.corpus), load_queries(args.queries), args.top_k_per_facet, args.include_unadmitted)
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for item in candidates:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
