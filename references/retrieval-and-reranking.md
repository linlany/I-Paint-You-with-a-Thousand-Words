# Retrieval and reranking

## Query facets

Use multiple independently traceable facets:

- `observations`: visible objects, actions, people count, setting
- `associations`: atmosphere, theme, waiting, distance, solitude, transition
- `composition`: window, foreground/background, framing, negative space, gaze direction
- `lighting`: dusk, shadow, reflected light, color temperature, contrast
- `text_visible`: exact visible text only, if any
- `visual_anchors`: dominant concrete cues that should be covered by the selected fragments
- `scene_conflicts`: concrete incompatible cues, each marked `soft` or `hard`

Keep query IDs so the provenance ledger can explain why a passage was retrieved. A passage matching only a high-level metaphor should not outrank a complete, source-quality passage matching several concrete cues unless the user asks for an abstract result.

## Hybrid retrieval

If available, combine lexical and embedding retrieval. Lexical search preserves names and concrete objects; embeddings help with paraphrase and thematic concepts. Keep raw scores and normalize them before blending. Do not use image-to-text similarity as proof that a passage is relevant or authentic.

## Baseline scoring

The bundled reranker computes a dependency-free approximation:

```text
total =
  0.20 * semantic_fit +
  0.15 * visual_coverage +
  0.25 * scene_fit +
  0.15 * source_quality +
  0.10 * quote_completeness +
  0.15 * diversity -
  0.20 * contradiction_risk
```

Each score is expected to be in [0, 1]. `diversity` is applied with a greedy selection penalty for repeated work/document identity and exact duplicate records. Do not treat a collection-level `source_id` as an article or work identity: several works may legitimately share one corpus source. Keep the score components in output for auditability; a final score without components is not useful for debugging.

`scene_fit` should be computed from `visual_anchors` or supplied by a vetted semantic backend. `lighting` must participate in the general coverage terms. The baseline accepts `--config config/example.yaml`; its `rerank.weights` and `scene_matching` values must be applied rather than treated as documentation only.

## Diversity and restraint

Use fewer strong fragments rather than padding the result. Cap quotes by count and length. Avoid selecting many passages from one work when other works provide equivalent coverage. If the candidate list does not support a visual concept, leave that concept unresolved.

Treat work-level diversity as a soft preference, not a hard cap. The first passage from a work receives full diversity credit; additional passages from that work are progressively down-ranked, but remain eligible when they are materially better or when the candidate pool is sparse. Prefer one fragment per work initially, while allowing a second fragment when it adds stronger scene coverage or a distinctive cue.

## Contradiction risk

Penalize a passage if it asserts a concrete fact that conflicts with the image analysis, such as day versus night, indoor versus outdoor, or multiple people versus one. Reject a `hard` conflict above the configured threshold by default. Treat unobserved but poetically plausible items such as rain, rivers, boats, or mountains as `soft` conflicts unless the image analysis marks them as genuinely incompatible. Abstract poetic tension is not automatically a contradiction, but it should not be mistaken for visual evidence.
