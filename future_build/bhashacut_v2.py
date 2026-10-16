"""BhashaCut — TTS-hazard linter for Hindi (Devanagari) scripts, plus a minimal
OpenAI-compatible LLM client. Stdlib only; Python 3.10+.

Source: Opus 5.5 code review (Max effort, Notion AI, 2026-10-11).
Saved for future BhashaCut build. NOT the submitted Hack Apertus version.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

# ── Character classes ─────────────────────────────────────────────────────────
# Explicit code points on purpose: Python's `re` does not count Devanagari
# matras/virama as \w, so \w+ and \b split Hindi words ("नमस्ते" -> "नमस", "त").
DEV = r"\u0900-\u0963\u0971-\u097f\u1cd0-\u1cff\ua8e0-\ua8ff"  # letters+marks; no । ॥ digits ॰
LATIN = r"A-Za-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u024f\u1e00-\u1eff"  # incl. IAST ā ś ṛ ṣ
JOIN = r"\u200c\u200d"  # ZWNJ/ZWJ: legitimate only *inside* Devanagari words
INVISIBLE_CHARS = (r"\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u00ad\u200b\u200e\u200f"
                   r"\u2028\u2029\u202a-\u202e\u2060\u2066-\u2069\ufeff")

_NEWLINE = re.compile(r"\r\n|\r|\n")
_VIRAMA = "\u094d"
_JOINERS = "\u200c\u200d"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


Finder = Callable[[str], Iterable[tuple[int, int]]]  # line -> (start, end) spans


@dataclass(frozen=True, slots=True)
class Rule:
    rule_id: str
    severity: Severity
    message: str
    suggestion: str
    find: Finder


@dataclass(frozen=True, slots=True)
class ScriptIssue:
    # First four fields unchanged, so existing positional construction still works.
    line_num: int                      # 1-based
    category: str                      # "tts_hazard"
    text: str                          # excerpt centred on the hit; never splits a conjunct
    detail: str
    col: int = 0                       # 1-based, code points of the NFC-normalised line
    match: str = ""                    # exact offending substring
    rule_id: str = ""
    severity: Severity = Severity.WARNING
    suggestion: str = ""


# ── Rules ─────────────────────────────────────────────────────────────────────
def _regex_finder(pattern: re.Pattern[str]) -> Finder:
    return lambda line: (m.span() for m in pattern.finditer(line) if m.end() > m.start())


_LETTER_RUN = re.compile(rf"[{LATIN}{DEV}{JOIN}]+")
_HAS_LATIN = re.compile(rf"[{LATIN}]")
_HAS_DEV = re.compile(rf"[{DEV}]")
_ELLIPSIS = re.compile(r"…|\.(?:[ \t]?\.){2,}")  # "…", "...", ". . ."
_INVISIBLE = re.compile(rf"[{INVISIBLE_CHARS}]|(?<![{DEV}])[{JOIN}]|[{JOIN}](?![{DEV}])")


def _mixed_script(line: str) -> Iterator[tuple[int, int]]:
    """Maximal letter runs that contain both scripts. Linear time, no backtracking."""
    for m in _LETTER_RUN.finditer(line):
        if _HAS_LATIN.search(m.group()) and _HAS_DEV.search(m.group()):
            yield m.span()


def _lexicon_pattern(word: str) -> re.Pattern[str]:
    """Match `word` even with ZWJ/ZWNJ inside it, widened to the whole word so
    inflections (कार्तिकेय, कार्तिकी) are reported as full tokens."""
    core = f"[{JOIN}]?".join(map(re.escape, unicodedata.normalize("NFC", word.strip())))
    return re.compile(rf"[{DEV}{JOIN}]*{core}[{DEV}{JOIN}]*")


# Words your TTS engine is known to mangle (word -> note). Extend per engine.
DEFAULT_LEXICON: Mapping[str, str] = MappingProxyType({
    "कार्तिक": "Conjunct breaks some TTS engines.",
})


def build_rules(lexicon: Mapping[str, str] | None = None) -> tuple[Rule, ...]:
    """Default rule set; pass `lexicon` to replace the problem-word list."""
    words = DEFAULT_LEXICON if lexicon is None else lexicon
    lexicon_rules = tuple(
        Rule("TTS001", Severity.WARNING, note,
             "Respell phonetically, or use SSML <sub>/<phoneme> if your engine supports it.",
             _regex_finder(_lexicon_pattern(word)))
        for word, note in words.items() if word.strip()
    )
    return lexicon_rules + (
        Rule("TTS002", Severity.ERROR, "Ellipsis truncates synthesis.",
             "Use a comma or danda (।), or an SSML <break>.", _regex_finder(_ELLIPSIS)),
        Rule("TTS003", Severity.WARNING, "Mixed script in single word.",
             "Add a space between scripts, or transliterate the Latin part.", _mixed_script),
        Rule("TTS004", Severity.WARNING, "Invisible or control character.",
             "Delete it (usually pasted in from docs, PDFs or chat apps).",
             _regex_finder(_INVISIBLE)),
    )


DEFAULT_RULES: tuple[Rule, ...] = build_rules()


# ── Linting ───────────────────────────────────────────────────────────────────
def _splits_cluster(text: str, i: int) -> bool:
    """True if cutting `text` at index i would detach a mark or conjunct from its base."""
    if not 0 < i < len(text):
        return False
    cur, prev = text[i], text[i - 1]
    return (unicodedata.category(cur)[0] == "M"
            or cur in _JOINERS or prev in _JOINERS
            or (prev == _VIRAMA and unicodedata.category(cur)[0] == "L"))


def _excerpt(line: str, start: int, end: int, width: int = 80) -> str:
    """~`width`-char window that always contains the hit and never splits a cluster."""
    if len(line) <= width:
        return line.strip(" \t")
    pad = max(0, (width - (end - start)) // 2)
    lo = max(0, min(start - pad, len(line) - width))
    hi = min(len(line), max(lo + width, end))
    while _splits_cluster(line, lo):
        lo -= 1
    while _splits_cluster(line, hi):
        hi += 1
    return line[lo:hi].strip(" \t")


def find_tts_hazards(script: str, rules: Sequence[Rule] | None = None) -> list[ScriptIssue]:
    """Every hazard in `script`, sorted by (line, column).

    Lines are split on LF, CRLF and CR only, so numbers match your editor. Each
    line is NFC-normalised before matching; columns refer to that form.
    """
    if isinstance(script, (bytes, bytearray)):
        raise TypeError("script is bytes; decode it first, e.g. data.decode('utf-8-sig')")
    if not isinstance(script, str):
        raise TypeError(f"script must be str, not {type(script).__name__}")
    active = DEFAULT_RULES if rules is None else rules
    issues: list[ScriptIssue] = []
    for line_num, raw in enumerate(_NEWLINE.split(script), start=1):
        line = unicodedata.normalize("NFC", raw)
        for rule in active:
            for start, end in rule.find(line):
                issues.append(ScriptIssue(
                    line_num, "tts_hazard", _excerpt(line, start, end), rule.message,
                    col=start + 1, match=line[start:end], rule_id=rule.rule_id,
                    severity=rule.severity, suggestion=rule.suggestion))
    issues.sort(key=lambda issue: (issue.line_num, issue.col))
    return issues


# ── LLM client ────────────────────────────────────────────────────────────────
class ConfigError(ValueError):
    """Invalid BhashaCut configuration."""


class LLMError(RuntimeError):
    """The LLM request failed or returned something unusable."""


def _env(*names: str, default: str = "") -> str:
    """First non-blank variable among `names`; blank counts as unset."""
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return default


def _retry_delay(retry_after: str | None, attempt: int) -> float:
    """Numeric Retry-After (capped at 30 s), else exponential backoff."""
    try:
        if retry_after:
            return max(0.0, min(float(retry_after), 30.0))
    except ValueError:  # HTTP-date form: fall back to backoff
        pass
    return min(2.0 ** attempt, 30.0)


class BhashaCut:
    DEFAULT_MODEL = "swiss-ai/apertus-v1.5-8b"
    DEFAULT_BASE_URL = "https://api.publicai.co/v1"
    RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, *, mock: bool | None = None,
                 timeout: float = 60.0, max_retries: int = 2,
                 rules: Sequence[Rule] | None = None) -> None:
        key = (api_key or "").strip() or _env("LLM_API_KEY")
        is_mock_key = key.lower() == "mock"
        # Mock is opt-in only (mock=True or LLM_API_KEY=mock). A missing key no longer
        # silently produces fake output, and keyless local servers still work.
        self.mock_mode = is_mock_key if mock is None else mock
        self.api_key = "" if is_mock_key else key
        self.base_url = ((base_url or "").strip()
                         or _env("LLM_BASE_URL", default=self.DEFAULT_BASE_URL)).rstrip("/")
        self.model = (model or "").strip() or _env("LLM_MODEL", "LLM_NAME",
                                                   default=self.DEFAULT_MODEL)
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.rules = DEFAULT_RULES if rules is None else tuple(rules)
        if not self.mock_mode:
            parts = urllib.parse.urlsplit(self.base_url)
            if parts.scheme not in ("http", "https") or not parts.netloc:
                raise ConfigError(f"LLM base URL must be http(s)://host/..., got {self.base_url!r}")

    def __repr__(self) -> str:  # never leak the key into logs or tracebacks
        return (f"BhashaCut(base_url={self.base_url!r}, model={self.model!r}, "
                f"mock_mode={self.mock_mode}, api_key={'***' if self.api_key else None})")

    def check_tts_hazards(self, script: str) -> list[ScriptIssue]:
        return find_tts_hazards(script, self.rules)

    def chat(self, prompt: str, *, system: str | None = None,
             temperature: float = 0.2, max_tokens: int | None = None) -> str:
        """One-shot call to an OpenAI-compatible /chat/completions endpoint."""
        if self.mock_mode:
            return f"[MOCK {self.model}] {prompt[:120]}"
        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {"model": self.model, "messages": messages,
                                   "temperature": temperature}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        body = self._post_json("/chat/completions", payload)
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LLMError(f"Unexpected response: {json.dumps(body, ensure_ascii=False)[:300]}") from None
        if not isinstance(content, str) or not content.strip():
            raise LLMError("Model returned no text content.")
        return content.strip()

    def _post_json(self, path: str, payload: dict[str, Any]) -> Any:
        url = self.base_url + path
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        for attempt in range(self.max_retries + 1):
            final = attempt == self.max_retries
            try:
                request = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                break
            except urllib.error.HTTPError as exc:  # must precede URLError (its parent)
                if exc.code in self.RETRYABLE_STATUS and not final:
                    time.sleep(_retry_delay((exc.headers or {}).get("Retry-After"), attempt))
                    continue
                detail = exc.read().decode("utf-8", "replace")[:300]
                hint = (" Check LLM_API_KEY (or set LLM_API_KEY=mock for offline runs)."
                        if exc.code in (401, 403) else "")
                raise LLMError(f"HTTP {exc.code} from {url}: {detail}{hint}") from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError,
                    http.client.HTTPException) as exc:
                if not final:
                    time.sleep(_retry_delay(None, attempt))
                    continue
                raise LLMError(f"Could not reach {url}: {exc}") from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError as exc:  # JSONDecodeError and UnicodeDecodeError
            raise LLMError(f"Non-JSON response from {url}: {raw[:200]!r}") from exc


# ── CLI ───────────────────────────────────────────────────────────────────────
def main(argv: Sequence[str] | None = None) -> int:
    """`python bhashacut.py script.txt ...` → exit 1 on any ERROR, 2 on unreadable files."""
    parser = argparse.ArgumentParser(description="Lint Hindi scripts for TTS hazards.")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args(argv)
    exit_code = 0
    for path in args.files:
        try:
            with open(path, encoding="utf-8-sig") as fh:  # utf-8-sig drops a leading BOM
                text = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            print(f"{path}: cannot read as UTF-8 ({exc})", file=sys.stderr)
            exit_code = 2
            continue
        for issue in find_tts_hazards(text):
            print(f"{path}:{issue.line_num}:{issue.col}: {issue.severity.value} "
                  f"{issue.rule_id} {issue.match!r} — {issue.detail}")
            if issue.severity is Severity.ERROR:
                exit_code = max(exit_code, 1)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
