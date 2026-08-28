# Verification and provenance

## Minimum provenance ledger

For every displayed quote, preserve:

```json
{
  "quote_id": "q-001",
  "exact_text": "...",
  "source_id": "gutenberg-work-edition",
  "source_url": "https://example.org/source",
  "location": "Chapter 3, paragraph 2",
  "retrieved_at": "2026-08-28T00:00:00Z",
  "snapshot_hash": "sha256:...",
  "verification_status": "verified_exact",
  "verification_notes": []
}
```

`source_id` must identify a stable source or corpus boundary, not a query result rank; it may be shared by multiple records from the same collection. Use `record_id` (and `work_id` when available) to distinguish the exact passage and work. `location` should be human-readable and, when possible, accompanied by character offsets or a line range in the local snapshot.

## Verification levels

- Exact: the quote appears as a contiguous character sequence in the claimed source.
- Normalized warning: only whitespace or line wrapping differs; retain the warning and do not treat it as exact in strict mode.
- Unverified: the source is unavailable, location is missing, OCR is uncertain, or only a secondary attribution exists.
- Rejected: altered wording, merged fragments, wrong author/work, restricted rights, or no match.

## Common failure modes

- Famous quote lists silently modernize spelling or omit context.
- Search snippets truncate a sentence and cause the model to complete it.
- OCR introduces punctuation and character substitutions.
- A translation is mistaken for the original author's wording.
- A model combines two nearby source sentences into one fluent sentence.
- A passage is real but from a different author or edition.

The verifier should fail closed for strict quote-only mode. The composer can still mention that useful evidence was rejected, but should not smuggle rejected text into the main collage.
