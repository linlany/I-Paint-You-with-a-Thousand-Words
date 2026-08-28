import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_queries  # noqa: E402
import ingest_corpus  # noqa: E402
import retrieve  # noqa: E402
import rerank  # noqa: E402
import verify_quotes  # noqa: E402


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.analysis = json.loads((ROOT / "examples" / "image-analysis.json").read_text(encoding="utf-8"))
        self.candidates = []
        for line in (ROOT / "examples" / "candidates.jsonl").read_text(encoding="utf-8").splitlines():
            self.candidates.append(json.loads(line))
        self.collage = json.loads((ROOT / "examples" / "collage-output.json").read_text(encoding="utf-8"))
        self.corpus = verify_quotes.load_corpus(str(ROOT / "examples" / "fixture-corpus.jsonl"))

    def test_build_queries_has_multiple_facets(self):
        queries = build_queries.make_queries(self.analysis)
        self.assertGreaterEqual(len(queries), 6)
        self.assertGreaterEqual(len({item["facet"] for item in queries}), 3)
        self.assertTrue(any(item["facet"] == "visual_anchors" for item in queries))

    def test_ingest_preserves_exact_text_and_adds_id(self):
        record = self.corpus[0]
        normalized = ingest_corpus.normalize(record, "fixture", 1, False)
        self.assertEqual(normalized["text"], record["text"])
        self.assertTrue(normalized["record_id"].startswith("fixture-corpus:"))

    def test_rerank_penalizes_contradiction(self):
        ranked = rerank.select(
            self.candidates,
            self.analysis,
            max_quotes=3,
            min_score=-1,
            scene_config={"require_anchor_match": False},
        )
        ids = [item["candidate_id"] for item in ranked]
        self.assertNotIn("c-999", ids)
        self.assertEqual([item["rank"] for item in ranked], [1, 2, 3])

    def test_analysis_terms_includes_lighting_and_cjk_tokens(self):
        terms = rerank.analysis_terms(self.analysis)
        self.assertIn("pale", terms)
        self.assertIn("夜", rerank.tokens(["深夜的窗"]))

    def test_scene_gate_rejects_hard_conflict(self):
        analysis = {
            "observations": [],
            "associations": [],
            "visual_anchors": [{"text": "open field", "confidence": 1.0}],
            "scene_conflicts": [{"text": "indoor room", "confidence": 1.0, "severity": "hard"}],
            "composition": [],
            "uncertainties": [],
        }
        candidates = [
            {"candidate_id": "field", "text": "The open field lay beneath a wide sky.", "semantic_score": 0.50, "source_quality": 1.0},
            {"candidate_id": "room", "text": "Inside the indoor room, rain fell at noon.", "semantic_score": 0.99, "source_quality": 1.0},
        ]
        ranked = rerank.select(candidates, analysis, max_quotes=1, min_score=-1)
        self.assertEqual([item["candidate_id"] for item in ranked], ["field"])
        self.assertGreater(ranked[0]["score_components"]["scene_fit"], 0.5)

    def test_config_weights_are_applied(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.yaml"
            config_path.write_text(
                "rerank:\n  weights:\n    semantic_fit: 0.01\n    scene_fit: 0.91\ndiversity:\n  same_work_penalty: 0.62\nscene_matching:\n  require_anchor_match: true\n",
                encoding="utf-8",
            )
            weights, scene_config, diversity_config = rerank.load_settings(str(config_path))
        self.assertAlmostEqual(weights["semantic_fit"], 0.01)
        self.assertAlmostEqual(weights["scene_fit"], 0.91)
        self.assertTrue(scene_config["require_anchor_match"])
        self.assertAlmostEqual(diversity_config["same_work_penalty"], 0.62)

    def test_diversity_prefers_new_work_but_allows_repeats(self):
        analysis = {
            "observations": [],
            "associations": [],
            "visual_anchors": [{"text": "open field", "confidence": 1.0}],
            "scene_conflicts": [],
            "composition": [],
            "uncertainties": [],
        }
        candidates = [
            {
                "candidate_id": "a1",
                "text": "The open field beneath a wide sky.",
                "source_id": "same-corpus",
                "work": "Work A",
                "work_id": "work-a",
                "semantic_score": 0.95,
                "source_quality": 1.0,
            },
            {
                "candidate_id": "a2",
                "text": "The open field waited in silence.",
                "source_id": "same-corpus",
                "work": "Work A",
                "work_id": "work-a",
                "semantic_score": 0.94,
                "source_quality": 1.0,
            },
            {
                "candidate_id": "b1",
                "text": "The open field darkened toward evening.",
                "source_id": "same-corpus",
                "work": "Work B",
                "work_id": "work-b",
                "semantic_score": 0.80,
                "source_quality": 1.0,
            },
        ]
        ranked = rerank.select(candidates, analysis, max_quotes=2, min_score=-1)
        self.assertEqual([item["candidate_id"] for item in ranked], ["a1", "b1"])
        ranked_with_repeat = rerank.select(candidates[:2], analysis, max_quotes=2, min_score=-1)
        self.assertEqual(len(ranked_with_repeat), 2)

    def test_local_retriever_returns_facet_traces(self):
        queries = build_queries.make_queries(self.analysis)
        candidates = retrieve.retrieve(self.corpus, queries, top_k_per_facet=3, include_unadmitted=False)
        self.assertTrue(candidates)
        self.assertTrue(all(item.get("query_facets") for item in candidates))
        self.assertTrue(any("lighting" in item["query_facets"] for item in candidates))

    def test_exact_verification_passes_fixture(self):
        report = verify_quotes.verify(self.collage, self.corpus, allow_normalized=False, require_location=True)
        self.assertTrue(report["ok"], report)
        self.assertTrue(all(item["status"] == "verified_exact" for item in report["results"]))

    def test_modified_quote_fails_closed(self):
        collage = json.loads(json.dumps(self.collage))
        collage["provenance"][0]["exact_text"] = "At the window, the night gathered softly."
        report = verify_quotes.verify(collage, self.corpus, allow_normalized=False, require_location=True)
        self.assertFalse(report["ok"])
        self.assertEqual(report["results"][0]["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
