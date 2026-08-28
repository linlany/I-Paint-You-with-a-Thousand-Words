# Corpus admission and rights

## Corpus admission checklist

Before retrieval, record:

- target author/person and unambiguous `author_id`
- work title and edition/version
- language and whether the text is an original or translation
- source URL or local source identifier
- retrieval date and, ideally, immutable snapshot hash
- jurisdiction used for the rights decision
- `license_status`: `public_domain`, `user_provided_licensed`, `rights_review`, or `restricted`

Only `public_domain` and `user_provided_licensed` should enter a strict quote-only production corpus unless a rights reviewer explicitly approves another status. A file named “public domain” is not evidence by itself: translations, editions, annotations, scans, and local laws can differ.

## Source quality hierarchy

1. Official archive or rights holder's open edition
2. Established digital library with edition and provenance metadata
3. Institutional repository or research edition with a stable identifier
4. Search snippets, quote websites, social posts, and unattributed images — discovery hints only, never evidence

The source used for retrieval and the source used for verification can differ, but the verification source must be authoritative enough for the claimed status. Preserve both identifiers when they differ.

## Historical figures

For speeches, letters, diaries, and aphorisms, attribute the words to the exact document or edition, not merely to the person. For disputed authorship, mark the passage `rights_review` or `unverified` and keep it out of strict composition.

## Translations and editions

Store original-language text separately from translations. A translation can be displayed as an editorial translation or parallel text, but it must not be presented as a verbatim original quote. If the user requests output in another language, preserve the source quote and label any translation as `translation_by` or `editorial_translation`.

## Minimizing reproduction

Retrieve only the fragments needed for the requested collage. Avoid building a substitute copy of an entire restricted work. For non-public-domain authors, offer one of: a user-supplied licensed corpus, a public-domain author with a related theme, or a high-level non-quoting discussion.
