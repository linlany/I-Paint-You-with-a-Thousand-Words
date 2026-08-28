---
name: literary-image-collage
description: "Build literary image collages from user images and requested public-domain authors or historical figures by retrieving, reranking, verifying, and composing real source text; use for quote-only, provenance-aware visual descriptions rather than style imitation."
metadata:
  short-description: "Verified quote-only literary image collages"
---

# Literary Image Collage

Use this skill when a user wants an uploaded image interpreted through the real words of a named public-domain writer or historical figure. The output is a collage of verified source fragments, not an imitation of a living author and not fabricated prose attributed to anyone.

## Operating contract

- User-facing output contract: after internal analysis, retrieval, reranking, and verification, output only the final literary result. Do not expose the workflow, image-analysis JSON, query list, ranking scores, provenance table, rights discussion, validation logs, or a closing explanation unless the user explicitly asks for them.
- Default collage form is associative, fragmentary, and scene-grounded: do not force logical, causal, grammatical, emotional, or narrative coherence, but keep each selected fragment tied to at least one high-confidence visual anchor when reliable evidence exists. Abrupt transitions, repetition, contrast, gaps, and unresolved juxtaposition are valid; scene mismatch is not a substitute for creative discontinuity.
- In thousand-word/long mode, maximize the proportion of verified source text. Prefer multiple exact original-language sentences, clauses, and fragments over long stretches of newly written connective prose. The final result may translate those verified fragments into the user's language when requested or clearly useful, but keep the exact source text and translation status in the internal provenance.
- Prefer public-domain corpora and user-supplied/licensed text. Treat copyright status as a corpus-level constraint; do not bulk-copy or reconstruct non-public-domain works.
- Keep visual facts separate from interpretive associations. Never infer identity, protected traits, private facts, or a person's hidden mental state from an image.
- Require provenance for every composed fragment: exact quote, work, location, source URL or local source identifier, retrieval timestamp, and verification status. For displayed translations, also retain the source language, translated text, and translation status.
- Enforce quote-only composition by default and preserve each source fragment's boundaries. Do not smooth fragments into a unified sentence. You may add connective prose only when the user explicitly asks for it, and it must not be presented as source text.
- If a requested author is not public domain in the relevant jurisdiction, explain the limitation and offer a public-domain alternative, a user-provided corpus, or an analysis that does not reproduce the author's text.
- Do not claim that the author wrote about the pictured person or scene. Keep the retrieval-based nature in internal metadata, and mention it in the chat only when the user asks for attribution or method.

## Default workflow

1. Resolve the requested figure, corpus scope, output language, citation style, and quote mode. Infer the user's display language from the request unless the user asks for source language; ask only when a missing choice changes rights or the requested deliverable. Default to strict quote-only mode.
2. Analyze the image into structured, uncertainty-aware facts, visual anchors, scene conflicts, and associations. Use the schema and prompt in `schemas/image-analysis.schema.json` and `prompts/image-analysis.md`. Keep `observations`, `visual_anchors`, `scene_conflicts`, and `associations` distinct.
3. Resolve a corpus manifest. Use `config/example.yaml` as the starting point and read `references/corpus-and-rights.md` for public-domain and source-quality checks.
4. Retrieve from multiple query facets (objects/actions, setting/light, composition, affective atmosphere, and abstract concepts). Give concrete visual anchors priority over abstract associations. Use `scripts/build_queries.py` to make deterministic query candidates and `scripts/retrieve.py` for the local lexical baseline; replace it with a vetted hybrid/vector backend when available.
5. Rerank candidate passages for semantic fit, general coverage, scene fit, quote completeness, source quality, diversity, and contradiction risk. Apply the scene gate before selecting famous or merely thematic lines: hard conflicts are rejected by default, while soft conflicts are penalized. Diversify by work/article, not by corpus or collection `source_id`: prefer one fragment per work initially, progressively down-rank additional fragments from the same work, and still allow them when they are materially better or evidence is scarce. `scripts/rerank.py` reads configured weights, scene settings, and diversity settings from `--config` and provides a dependency-free baseline; an embedding or cross-encoder may be plugged in without removing the baseline checks.
6. Verify exactness before composition. Run `scripts/verify_quotes.py` against the source corpus or source snapshots. Reject altered, merged, or unlocatable text. Record normalized matching only as a warning, never as proof of exactness.
7. Compose with `prompts/composition.md` as an associative fragment montage unless the user explicitly requests a coherent narrative. Nonlinear ordering does not waive scene fit: prefer fragments covering different visual anchors, and do not use a concrete passage that conflicts with the scene merely because it is famous. Validate the result using `schemas/collage-output.schema.json` plus `scripts/verify_quotes.py --report` or an equivalent verifier. Every displayed quote must map to a verified source record.
8. Render only the final collage/description to the user. Keep the provenance ledger, uncertainty notes, corpus/license notes, and observation/interpretation distinction in the internal result or sidecar data. Include them in the chat only when the user explicitly requests sources, verification, or an explanation.

## Resource routing

- Read `references/corpus-and-rights.md` for corpus admission, public-domain boundaries, source hierarchy, and attribution.
- Read `references/retrieval-and-reranking.md` when implementing or tuning search, hybrid retrieval, diversity, or scoring.
- Read `references/verification-and-provenance.md` when exact quoting, OCR, translations, snapshots, or auditability matter.
- Use `config/example.yaml`, `schemas/*.json`, `prompts/*.md`, and `scripts/*.py` as the runnable contract for integrations.

## Failure behavior

- No reliable corpus or no exact source match: return only a brief failure message or a clearly marked partial final result; never fill gaps with invented text or add a process explanation.
- Ambiguous attribution, translation-only evidence, OCR uncertainty, or a low-confidence match: label it explicitly and do not mark it `verified_exact`.
- Image contains a real person: describe only visible, non-sensitive features and composition. Avoid face recognition or identity claims unless the user supplied the identity and it is relevant to the task.

The bundled scripts use only the Python standard library and run offline. They are a baseline skeleton: production deployments should add a vetted corpus index, a retrieval provider, immutable source snapshots, rate limiting, and tests for the selected jurisdiction and language.
