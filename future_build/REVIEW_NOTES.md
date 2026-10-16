# BhashaCut v2 - Opus 5.5 Code Review Summary
Review date: 2026-10-11. Model: Opus 5.5, Max effort, Notion AI.
Full chat: https://app.notion.com/chat?t=3f613e88d42180049f3d00a9548783eb&wfv=chat
Code: bhashacut_v2.py in this folder. Verified locally 2026-10-11: compiles, danda false-positive gone, all ellipsis forms found, mixed-script detection correct.

## 8 bugs found in the submitted v1 code (all reproduced by Opus)
1. False positive with dandas: the Devanagari range covered ।, ॥, digits, so "यह OK।" was flagged as mixed script.
2. Excerpt could leave out the problem: [:80] always kept the first 80 chars; a hazard at column 151 was invisible, no column reported.
3. One hit per rule per line: re.search stops at first match; "a… b… c…" gave 1 issue, not 3.
4. Slicing broke Devanagari: cutting at [:80] could split a conjunct, leaving a bare virama.
5. Line numbers disagreed with editors: splitlines() also breaks on \x0b, \x0c, \x85, U+2028, U+2029 (common in pasted text).
6. Mock mode turned on silently: missing env var in production quietly returned fake output; keyless local servers (vLLM/Ollama) got mocked instead of called.
7. Blank env vars counted as set; "Mock" or "mock\n" not recognised as mock.
8. Regex backtracked badly on long lines: 1.1s for 10k chars, 4.5s for 20k. Rewrite: 0.02s for 200k.

## Missed edge cases now covered in v2
- ZWJ/ZWNJ variants of lexicon words; NFC normalisation (nukta precomposed vs decomposed).
- Ellipsis forms: …, ..., . . .
- IAST letters next to Devanagari; Latin + ZWJ + Devanagari.
- Invisible characters (ZWSP, soft hyphen, BOM, bidi marks, stray ZWJ) - the most common TTS breaker after copy-paste.

## What v2 adds
- Rule IDs (TTS001-TTS004), severities, columns, fix suggestions.
- Configurable per-engine lexicon via build_rules().
- CLI mode with exit codes for CI (1 on ERROR, 2 on unreadable file).
- Real LLM client (stdlib urllib): timeout, retries with Retry-After, typed errors (ConfigError, LLMError), key never leaked in repr.
- Mock is opt-in only (LLM_API_KEY=mock or mock=True).

## Deliberate breaking changes vs v1
- TTS_HAZARDS replaced by DEFAULT_RULES / build_rules(lexicon).
- Mock mode requires explicit opt-in.
- LLM_MODEL read first, LLM_NAME still works as fallback.
- ScriptIssue is frozen (immutable, hashable).

## Future ideas from the review (not implemented)
- Rules for numbers/currency/percent, abbreviations, emoji, overly long sentences.
- Skip non-spoken text (source tags, stage directions, SSML).
