#!/usr/bin/env python3
"""Normalize corpus JSON/JSONL records without changing quote text."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

REQUIRED = ("text", "author", "work", "source_id", "source_url", "location", "license_status")
ALLOWED_RIGHTS = {"public_domain", "user_provided_licensed", "public_domain_or_fixture"}


def read_records(path: Path) -> Iterable[Dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number}: record is not an object")
                yield value
        return
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if isinstance(value, dict):
        yield value
    elif isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                raise ValueError(f"{path}: list item is not an object")
            yield item
    else:
        raise ValueError(f"{path}: expected an object or array")


def normalize(record: Dict[str, Any], origin: str, index: int, allow_missing_rights: bool) -> Dict[str, Any]:
    missing = [key for key in REQUIRED if not str(record.get(key, "")).strip()]
    if missing:
        raise ValueError(f"{origin} record {index}: missing required fields: {', '.join(missing)}")
    status = str(record["license_status"])
    if status not in ALLOWED_RIGHTS and not allow_missing_rights:
        raise ValueError(f"{origin} record {index}: license_status {status!r} is not admitted")
    text = str(record["text"])
    stable_id = record.get("record_id")
    if not stable_id:
        digest = hashlib.sha256(
            f"{record['source_id']}\0{record['location']}\0{text}".encode("utf-8")
        ).hexdigest()[:20]
        stable_id = f"{record['source_id']}:{digest}"
    output = dict(record)
    output.update(
        {
            "record_id": stable_id,
            "text": text,
            "author": str(record["author"]),
            "work": str(record["work"]),
            "source_id": str(record["source_id"]),
            "source_url": str(record["source_url"]),
            "location": str(record["location"]),
            "license_status": status,
        }
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Input JSON or JSONL corpus files")
    parser.add_argument("--out", required=True, help="Normalized JSONL output")
    parser.add_argument("--allow-missing-rights", action="store_true", help="Keep rights_review/restricted records for review only")
    args = parser.parse_args()

    records: List[Dict[str, Any]] = []
    try:
        for name in args.inputs:
            path = Path(name)
            for index, record in enumerate(read_records(path), 1):
                records.append(normalize(record, str(path), index, args.allow_missing_rights))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ingest error: {error}", file=sys.stderr)
        return 2

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"normalized {len(records)} corpus records to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
