#!/usr/bin/env python3
"""Verify collage provenance against an exact corpus snapshot."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: str) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_corpus(path: str) -> List[Dict[str, Any]]:
    if Path(path).suffix.lower() == ".jsonl":
        records = []
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number}: corpus record is not an object")
                records.append(value)
        return records
    value = load_json(path)
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    raise ValueError("corpus must be JSON object, JSON array, or JSONL")


def compact_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def verify(collage: Dict[str, Any], corpus: List[Dict[str, Any]], allow_normalized: bool, require_location: bool) -> Dict[str, Any]:
    by_source: Dict[str, List[Dict[str, Any]]] = {}
    for record in corpus:
        by_source.setdefault(str(record.get("source_id", "")), []).append(record)

    results: List[Dict[str, Any]] = []
    seen_ids = set()
    for provenance in collage.get("provenance", []) or []:
        if not isinstance(provenance, dict):
            results.append({"quote_id": None, "status": "rejected", "notes": ["provenance item is not an object"]})
            continue
        quote_id = provenance.get("quote_id")
        text = str(provenance.get("exact_text", ""))
        source_id = str(provenance.get("source_id", ""))
        notes: List[str] = []
        status = "verified_exact"
        if not quote_id or quote_id in seen_ids:
            status = "rejected"
            notes.append("quote_id is missing or duplicated")
        seen_ids.add(quote_id)
        if not text:
            status = "rejected"
            notes.append("exact_text is empty")
        matches = by_source.get(source_id, [])
        if not matches:
            status = "rejected"
            notes.append("source_id not found in corpus")
        eligible = [record for record in matches if record.get("license_status") in {"public_domain", "user_provided_licensed", "public_domain_or_fixture"}]
        if matches and not eligible:
            status = "rejected"
            notes.append("source license status is not admitted")
        exact_records = [record for record in eligible if text in str(record.get("text", ""))]
        if exact_records:
            if require_location and not any(str(record.get("location", "")) == str(provenance.get("location", "")) for record in exact_records):
                status = "unverified"
                notes.append("exact text found, but location does not match corpus metadata")
        elif eligible and allow_normalized:
            normalized = compact_whitespace(text)
            if any(normalized in compact_whitespace(str(record.get("text", ""))) for record in eligible):
                status = "verified_normalized_warning"
                notes.append("matched only after whitespace normalization")
            else:
                status = "rejected"
                notes.append("exact text not found in the claimed source")
        elif eligible:
            status = "rejected"
            notes.append("exact text not found in the claimed source")
        results.append(
            {
                "quote_id": quote_id,
                "source_id": source_id,
                "status": status,
                "notes": notes,
            }
        )

    displayed_ids = {
        quote_id
        for section in collage.get("sections", []) or []
        if isinstance(section, dict)
        for quote_id in section.get("quote_ids", []) or []
    }
    provenance_ids = {item.get("quote_id") for item in collage.get("provenance", []) or [] if isinstance(item, dict)}
    missing = sorted(str(item) for item in displayed_ids - provenance_ids)
    if missing:
        results.append({"quote_id": None, "status": "rejected", "notes": [f"section references missing quote_ids: {', '.join(missing)}"]})
    ok = bool(results) and all(item.get("status") == "verified_exact" for item in results)
    if not results and not displayed_ids:
        ok = False
    return {"ok": ok, "checked": len(results), "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--collage", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--allow-normalized", action="store_true", help="Report normalized matches as warnings")
    parser.add_argument("--no-location-check", action="store_true")
    parser.add_argument("--no-fail", action="store_true", help="Write the report but return success for review workflows")
    args = parser.parse_args()

    try:
        corpus = load_corpus(args.corpus)
        collage = load_json(args.collage)
        if not isinstance(collage, dict):
            raise ValueError("collage must be a JSON object")
        report = verify(collage, corpus, args.allow_normalized, not args.no_location_check)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"verification error: {error}", file=sys.stderr)
        return 2

    output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return 0 if report["ok"] or args.no_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
