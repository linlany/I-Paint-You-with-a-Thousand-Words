#!/usr/bin/env python3
"""Rerank candidate passages with an auditable, dependency-free baseline."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
CJK_RUN_RE = re.compile(r"[\u3400-\u9fff]+")
DEFAULT_WEIGHTS = {
    "semantic_fit": 0.20,
    "visual_coverage": 0.15,
    "scene_fit": 0.25,
    "source_quality": 0.15,
    "quote_completeness": 0.10,
    "diversity": 0.15,
    "contradiction_risk": -0.20,
}
DEFAULT_DIVERSITY_CONFIG = {
    "same_work_penalty": 0.45,
    "same_record_penalty": 0.15,
    "floor": 0.20,
}
DEFAULT_SCENE_CONFIG = {
    "require_anchor_match": True,
    "min_scene_fit": 0.15,
    "hard_conflict_threshold": 0.80,
}
SOURCE_QUALITY = {
    "public_domain": 1.0,
    "user_provided_licensed": 1.0,
    "public_domain_or_fixture": 0.9,
    "rights_review": 0.3,
    "restricted": 0.0,
}


def load_json(path: str) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("analysis must be an object")
    return value


def load_json_lines(path: str) -> List[Dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        values = []
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: candidate is not an object")
            values.append(value)
    return values


def tokens(values: Iterable[str]) -> Set[str]:
    result: Set[str] = set()
    for value in values:
        text = str(value)
        result.update(token.lower() for token in WORD_RE.findall(text))
        # WORD_RE treats an uninterrupted Chinese sentence as one token. Add
        # characters and adjacent character pairs so the offline baseline is
        # useful for Chinese corpora as well as Latin-script corpora.
        for run in CJK_RUN_RE.findall(text):
            result.update(run)
            result.update(run[index:index + 2] for index in range(len(run) - 1))
    return result


def analysis_terms(analysis: Dict[str, Any]) -> Set[str]:
    values: List[str] = []
    for key in ("observations", "associations"):
        for item in analysis.get(key, []) or []:
            if isinstance(item, dict):
                values.append(str(item.get("text", "")))
    for key in ("composition", "lighting", "visual_anchors"):
        for item in analysis.get(key, []) or []:
            if isinstance(item, dict):
                values.append(str(item.get("text", "")))
            else:
                values.append(str(item))
    return tokens(values)


def number(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _items(value: Any) -> List[Mapping[str, Any]]:
    result: List[Mapping[str, Any]] = []
    for item in value or []:
        if isinstance(item, Mapping):
            result.append(item)
        else:
            result.append({"text": str(item)})
    return result


def _normalized(value: str) -> str:
    return re.sub(r"\s+", "", str(value)).lower()


def _identity_key(item: Mapping[str, Any], fields: Sequence[str]) -> str:
    for field in fields:
        value = str(item.get(field, "")).strip()
        if value:
            return f"{field}:{_normalized(value)}"
    return ""


def _match_score(candidate_text: str, label: str) -> float:
    label_normalized = _normalized(label)
    candidate_normalized = _normalized(candidate_text)
    if not label_normalized:
        return 0.0
    if label_normalized in candidate_normalized:
        return 1.0
    label_terms = tokens([label])
    if not label_terms:
        return 0.0
    candidate_terms = tokens([candidate_text])
    return len(label_terms & candidate_terms) / len(label_terms)


def _weighted_match(candidate_text: str, items: Sequence[Mapping[str, Any]]) -> float:
    if not items:
        return 0.0
    weighted_total = 0.0
    weight_total = 0.0
    for item in items:
        label = str(item.get("text", "")).strip()
        if not label:
            continue
        weight = number(item.get("confidence", 1.0), 1.0)
        weighted_total += _match_score(candidate_text, label) * weight
        weight_total += weight
    return weighted_total / weight_total if weight_total else 0.0


def _scene_anchors(analysis: Dict[str, Any]) -> List[Mapping[str, Any]]:
    explicit = _items(analysis.get("visual_anchors"))
    if explicit:
        return explicit
    # Backward-compatible fallback for older image-analysis JSON files.
    allowed_categories = {"setting", "lighting", "color", "composition", "texture", "object"}
    return [
        item for item in _items(analysis.get("observations"))
        if not item.get("category") or item.get("category") in allowed_categories
    ]


def _scene_fit(candidate: Dict[str, Any], analysis: Dict[str, Any]) -> float:
    if "scene_fit" in candidate:
        return number(candidate.get("scene_fit"))
    return _weighted_match(str(candidate.get("text", "")), _scene_anchors(analysis))


def _scene_conflict(candidate: Dict[str, Any], analysis: Dict[str, Any]) -> float:
    supplied = max(
        number(candidate.get("contradiction_risk", 0.0)),
        number(candidate.get("visual_conflict", 0.0)),
    )
    inferred = _weighted_match(
        str(candidate.get("text", "")),
        _items(analysis.get("scene_conflicts")),
    )
    return max(supplied, inferred)


def _has_hard_conflict(candidate: Dict[str, Any], analysis: Dict[str, Any], scene_config: Mapping[str, Any]) -> bool:
    threshold = number(scene_config.get("hard_conflict_threshold", 0.80), 0.80)
    candidate_text = str(candidate.get("text", ""))
    for item in _items(analysis.get("scene_conflicts")):
        severity = str(item.get("severity", "soft")).lower()
        confidence = number(item.get("confidence", 1.0), 1.0)
        if severity == "hard" and confidence >= threshold and _match_score(candidate_text, str(item.get("text", ""))) >= 0.5:
            return True
    return False


def score_parts(
    candidate: Dict[str, Any],
    analysis: Dict[str, Any],
    terms: Set[str],
    selected: Sequence[Dict[str, Any]],
    diversity_config: Optional[Mapping[str, Any]] = None,
) -> Dict[str, float]:
    text_terms = tokens([str(candidate.get("text", ""))])
    coverage = len(text_terms & terms) / max(1, len(terms))
    semantic = number(candidate.get("semantic_score", candidate.get("retrieval_score", coverage)), coverage)
    quality = number(candidate.get("source_quality", SOURCE_QUALITY.get(candidate.get("license_status"), 0.5)), 0.5)
    complete = number(candidate.get("quote_completeness", 1.0 if re.search(r"[.!?。！？]$", str(candidate.get("text", "").strip())) else 0.7), 0.7)
    active_diversity = dict(DEFAULT_DIVERSITY_CONFIG)
    if diversity_config:
        active_diversity.update(diversity_config)
    work_fields = ("work_id", "work", "document_id", "article_id")
    record_fields = ("record_id", "candidate_id")
    work_key = _identity_key(candidate, work_fields)
    record_key = _identity_key(candidate, record_fields)
    repeated_work = sum(
        1 for item in selected
        if work_key and _identity_key(item, work_fields) == work_key
    )
    repeated_record = sum(
        1 for item in selected
        if record_key and _identity_key(item, record_fields) == record_key
    )
    same_work_penalty = number(active_diversity.get("same_work_penalty", 0.45), 0.45)
    same_record_penalty = number(active_diversity.get("same_record_penalty", 0.15), 0.15)
    diversity_floor = number(active_diversity.get("floor", 0.20), 0.20)
    diversity = max(
        diversity_floor,
        1.0 - same_work_penalty * repeated_work - same_record_penalty * repeated_record,
    )
    scene_fit = _scene_fit(candidate, analysis)
    contradiction = _scene_conflict(candidate, analysis)
    return {
        "semantic_fit": semantic,
        "visual_coverage": number(coverage),
        "scene_fit": scene_fit,
        "source_quality": quality,
        "quote_completeness": complete,
        "diversity": diversity,
        "same_work_repeats": float(repeated_work),
        "same_record_repeats": float(repeated_record),
        "scene_conflict": contradiction,
        "contradiction_risk": contradiction,
    }


def total(parts: Dict[str, float], weights: Dict[str, float]) -> float:
    return sum(parts.get(key, 0.0) * weight for key, weight in weights.items())


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.lower() in {"null", "none"}:
        return None
    if (value.startswith("\"") and value.endswith("\"")) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def _load_simple_yaml(path: str) -> Dict[str, Any]:
    """Read the mapping subset used by config/example.yaml without PyYAML."""
    root: Dict[str, Any] = {}
    stack: List[Tuple[int, Dict[str, Any]]] = [(-1, root)]
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        stripped = raw_line.strip()
        if stripped.startswith("-") or ":" not in stripped:
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        key, raw_value = stripped.split(":", 1)
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if not raw_value.strip():
            child: Dict[str, Any] = {}
            parent[key.strip()] = child
            stack.append((indent, child))
        else:
            parent[key.strip()] = _parse_scalar(raw_value.split(" #", 1)[0])
    return root


def load_settings(
    config_path: Optional[str] = None,
    weights_json: Optional[str] = None,
) -> Tuple[Dict[str, float], Dict[str, Any], Dict[str, Any]]:
    data: Dict[str, Any] = {}
    if config_path:
        path = Path(config_path)
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = _load_simple_yaml(str(path))
    weights = dict(DEFAULT_WEIGHTS)
    configured_weights = ((data.get("rerank") or {}).get("weights") or {})
    for key, value in configured_weights.items():
        if key in weights:
            try:
                weights[key] = float(value)
            except (TypeError, ValueError):
                pass
    if weights_json:
        raw = json.loads(Path(weights_json).read_text(encoding="utf-8"))
        raw = raw.get("weights", raw) if isinstance(raw, dict) else {}
        for key, value in raw.items():
            if key in weights:
                weights[key] = float(value)
    scene_config = dict(DEFAULT_SCENE_CONFIG)
    configured_scene = data.get("scene_matching") or {}
    scene_config.update(configured_scene)
    diversity_config = dict(DEFAULT_DIVERSITY_CONFIG)
    configured_diversity = data.get("diversity") or ((data.get("rerank") or {}).get("diversity") or {})
    diversity_config.update(configured_diversity)
    return weights, scene_config, diversity_config


def select(
    candidates: List[Dict[str, Any]],
    analysis: Dict[str, Any],
    max_quotes: int,
    min_score: float,
    weights: Optional[Mapping[str, float]] = None,
    scene_config: Optional[Mapping[str, Any]] = None,
    diversity_config: Optional[Mapping[str, Any]] = None,
    allow_scene_conflicts: bool = False,
) -> List[Dict[str, Any]]:
    active_weights = dict(DEFAULT_WEIGHTS)
    if weights:
        active_weights.update({key: float(value) for key, value in weights.items() if key in active_weights})
    active_scene_config = dict(DEFAULT_SCENE_CONFIG)
    if scene_config:
        active_scene_config.update(scene_config)
    active_diversity_config = dict(DEFAULT_DIVERSITY_CONFIG)
    if diversity_config:
        active_diversity_config.update(diversity_config)
    terms = analysis_terms(analysis)
    anchors = _scene_anchors(analysis)
    require_anchor = bool(active_scene_config.get("require_anchor_match", False))
    min_scene_fit = number(active_scene_config.get("min_scene_fit", 0.15), 0.15)
    remaining = [
        candidate for candidate in candidates
        if allow_scene_conflicts or not _has_hard_conflict(candidate, analysis, active_scene_config)
    ]
    selected: List[Dict[str, Any]] = []
    while remaining and len(selected) < max_quotes:
        scored = []
        for candidate in remaining:
            parts = score_parts(candidate, analysis, terms, selected, active_diversity_config)
            if require_anchor and anchors and parts["scene_fit"] < min_scene_fit:
                continue
            score = total(parts, active_weights)
            scored.append((score, str(candidate.get("candidate_id", "")), candidate, parts))
        if not scored:
            break
        scored.sort(key=lambda item: (-item[0], item[1]))
        score, _, candidate, parts = scored[0]
        remaining.remove(candidate)
        if score < min_score:
            break
        result = dict(candidate)
        result.update({"rerank_score": round(score, 6), "score_components": {k: round(v, 6) for k, v in parts.items()}})
        result["rank"] = len(selected) + 1
        selected.append(result)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--candidates", required=True, help="JSONL candidate passages")
    parser.add_argument("--out", required=True, help="JSONL ranked output")
    parser.add_argument("--max-quotes", type=int, default=12)
    parser.add_argument("--min-score", type=float, default=-1.0)
    parser.add_argument("--config", help="YAML/JSON config; rerank.weights and scene_matching are applied")
    parser.add_argument("--weights-json", help="Optional JSON object overriding rerank weights")
    parser.add_argument("--min-scene-fit", type=float, help="Override scene_matching.min_scene_fit")
    parser.add_argument("--allow-scene-conflicts", action="store_true", help="Allow candidates matching hard scene conflicts")
    args = parser.parse_args()

    analysis = load_json(args.analysis)
    candidates = load_json_lines(args.candidates)
    weights, scene_config, diversity_config = load_settings(args.config, args.weights_json)
    if args.min_scene_fit is not None:
        scene_config["min_scene_fit"] = args.min_scene_fit
    ranked = select(
        candidates,
        analysis,
        max(0, args.max_quotes),
        args.min_score,
        weights=weights,
        scene_config=scene_config,
        diversity_config=diversity_config,
        allow_scene_conflicts=args.allow_scene_conflicts,
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for item in ranked:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
