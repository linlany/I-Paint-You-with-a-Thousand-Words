#!/usr/bin/env python3
"""Create deterministic multi-facet retrieval queries from image-analysis JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


def load_json(path: str) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("analysis must be a JSON object")
    return value


def clean_terms(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        value = re.sub(r"\s+", " ", str(value)).strip()
        if not value or value.lower() in seen:
            continue
        seen.add(value.lower())
        result.append(value)
    return result


def item_texts(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    return clean_terms(
        item.get("text", "") for item in items if isinstance(item, dict)
    )


def make_queries(analysis: Dict[str, Any], author: str = "") -> List[Dict[str, Any]]:
    observations = item_texts(analysis.get("observations"))
    visual_anchors = item_texts(analysis.get("visual_anchors"))
    associations = item_texts(analysis.get("associations"))
    composition = clean_terms(analysis.get("composition", []))
    lighting = clean_terms(
        item.get("text", "")
        for item in analysis.get("observations", [])
        if isinstance(item, dict) and item.get("category") in {"lighting", "color"}
    )
    visible_text = clean_terms(
        item.get("text", "")
        for item in analysis.get("observations", [])
        if isinstance(item, dict) and item.get("category") == "text_visible"
    )

    groups = [
        ("observations", observations),
        ("visual_anchors", visual_anchors),
        ("associations", associations),
        ("composition", composition),
        ("lighting", lighting),
        ("text_visible", visible_text),
    ]
    queries: List[Dict[str, Any]] = []
    number = 1
    for facet, terms in groups:
        if not terms:
            continue
        query_terms = terms[:8]
        prefix = f"{author} " if author else ""
        queries.append(
            {
                "query_id": f"q-{number:03d}",
                "facet": facet,
                "query": (prefix + " ".join(query_terms)).strip(),
                "terms": query_terms,
                "why": f"Retrieval facet derived from image {facet}.",
                "risk": "medium" if facet == "associations" else "low",
            }
        )
        number += 1
        for term in query_terms[:4]:
            queries.append(
                {
                    "query_id": f"q-{number:03d}",
                    "facet": facet,
                    "query": (prefix + term).strip(),
                    "terms": [term],
                    "why": f"Single-signal query for the {facet} facet.",
                    "risk": "medium" if facet == "associations" else "low",
                }
            )
            number += 1
    return queries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", required=True, help="Image analysis JSON")
    parser.add_argument("--out", required=True, help="Output query JSON")
    parser.add_argument("--author", default="", help="Optional author/person corpus label")
    args = parser.parse_args()

    analysis = load_json(args.analysis)
    payload = {
        "image_id": analysis.get("image_id"),
        "author": args.author or None,
        "queries": make_queries(analysis, args.author),
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
