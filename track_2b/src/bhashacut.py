"""
BhashaCut: Hinglish Video Script Assistant powered by Apertus v1.5.

Uses Switzerland's open Apertus LLM (Apache 2.0) to polish Hindi/English
mixed video scripts, flag TTS hazards, and check terminology consistency.

Apertus v1.5 is trained on 1800+ languages with strong multilingual support,
making it ideal for Hinglish code-switching that trips up most models.

API: OpenAI-compatible. Works with:
- Public AI Inference Utility: https://api.publicai.co/v1 (needs LLM_API_KEY)
- Local Ollama: http://localhost:11434/v1 (model: swiss-ai/apertus-v1.5-8b)
- Any OpenAI-compatible Apertus endpoint

Environment variables (per Hack Apertus template):
- LLM_NAME: model ID (default: swiss-ai/apertus-v1.5-8b)
- LLM_BASE_URL: API endpoint (default: https://api.publicai.co/v1)
- LLM_API_KEY: API key (or "mock" for fixture mode)
"""

from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# TTS hazard patterns (from real production experience)
TTS_HAZARDS = [
    (r'कार्तिक', 'Contains र्तिक conjunct that breaks some TTS engines. Consider ZWJ insertion.'),
    (r'…', 'Ellipsis character truncates synthesis in some backends. Split into separate calls.'),
    (r'[A-Za-z]+[ऀ-ॿ]+|[ऀ-ॿ]+[A-Za-z]+', 'Mixed Latin/Devanagari in single word. May cause pronunciation issues.'),
]


@dataclass
class ScriptIssue:
    line_num: int
    category: str  # 'tts_hazard', 'mixed_script', 'terminology', 'suggestion'
    text: str
    detail: str


class BhashaCut:
    """Hinglish script assistant using Apertus v1.5."""

    # Apertus v1.5 model IDs (per Hack Apertus Track 2B resources)
    DEFAULT_MODEL = "swiss-ai/apertus-v1.5-8b"
    # Legacy alias mapping for compatibility
    MODEL_ALIASES = {
        "swiss-ai/apertus-8b-instruct": "swiss-ai/apertus-v1.5-8b",
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        # Per Hack Apertus template: LLM_NAME, LLM_BASE_URL, LLM_API_KEY
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "https://api.publicai.co/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        raw_model = model or os.environ.get("LLM_NAME", self.DEFAULT_MODEL)
        # Map legacy aliases to v1.5
        self.model = self.MODEL_ALIASES.get(raw_model, raw_model)

        # Fixture/mock mode: allows make run without API key
        self.mock_mode = self.api_key == "mock" or not self.api_key

        if not self.mock_mode and OpenAI is None:
            raise ImportError("pip install openai to use BhashaCut")

        if not self.mock_mode:
            self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        else:
            self.client = None

    def _chat(self, system: str, user: str, max_tokens: int = 1000) -> str:
        if self.mock_mode:
            # Fixture mode: return deterministic placeholder for make run without API key
            return f"[MOCK Apertus v1.5 response - set LLM_API_KEY for live inference]\nSystem: {system[:80]}..."
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.3,
        )
        return resp.choices[0].message.content or ""

    def check_tts_hazards(self, script: str) -> list[ScriptIssue]:
        """Flag known TTS hazards line by line."""
        issues = []
        for i, line in enumerate(script.splitlines(), 1):
            for pattern, detail in TTS_HAZARDS:
                if re.search(pattern, line):
                    issues.append(ScriptIssue(
                        line_num=i,
                        category='tts_hazard',
                        text=line.strip()[:80],
                        detail=detail,
                    ))
        return issues

    def polish(self, script: str, target: str = "hinglish") -> dict:
        """
        Polish a rough script using Apertus v1.5, with TTS hazard gate on output.

        target: 'hinglish' (natural code-switch), 'hindi' (pure Devanagari),
                'english' (pure English)

        Returns dict with polished text and TTS hazards found in the output.
        """
        system = (
            "You are BhashaCut, an expert video script editor for Indian content creators. "
            "You polish Hindi-English mixed (Hinglish) scripts for voiceover and on-screen text. "
            "Preserve the speaker's intent, energy, and cultural references. "
            "Fix grammar, smooth code-switching, and ensure natural flow. "
            "Avoid TTS-unfriendly characters: do not use the ellipsis character, "
            "avoid problematic conjuncts, keep script consistent within words."
        )
        target_instruction = {
            "hinglish": "Polish into natural Hinglish (Hindi in Devanagari mixed with English where natural).",
            "hindi": "Convert into pure Hindi using Devanagari script.",
            "english": "Convert into pure English.",
        }.get(target, "Polish into natural Hinglish.")

        user = f"{target_instruction}\n\nScript:\n{script}"
        polished = self._chat(system, user, max_tokens=2000)

        # TTS gate: scan model output for hazards (not just input)
        output_hazards = self.check_tts_hazards(polished)

        return {
            "polished_script": polished,
            "tts_hazards_in_output": [
                {"line": h.line_num, "text": h.text, "detail": h.detail}
                for h in output_hazards
            ],
        }

    def check_consistency(self, script: str) -> str:
        """Check character names and terminology consistency using Apertus."""
        system = (
            "You are a script consistency checker. Read the video script and list: "
            "1. All character/proper names mentioned, flagging spelling variations. "
            "2. Key terminology, flagging inconsistent usage. "
            "3. Any continuity issues. Be concise and specific with line references."
        )
        return self._chat(system, f"Script:\n{script}", max_tokens=1500)

    def full_report(self, script: str, target: str = "hinglish") -> dict:
        """Run all checks and return a structured report."""
        hazards = self.check_tts_hazards(script)
        polish_result = self.polish(script, target)
        return {
            "tts_hazards_in_input": [
                {"line": h.line_num, "category": h.category, "text": h.text, "detail": h.detail}
                for h in hazards
            ],
            "polished_script": polish_result["polished_script"],
            "tts_hazards_in_output": polish_result["tts_hazards_in_output"],
            "consistency_notes": self.check_consistency(script),
            "model": self.model,
            "mock_mode": self.mock_mode,
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="BhashaCut: Hinglish script assistant on Apertus")
    parser.add_argument("script_file", help="Path to script .txt file")
    parser.add_argument("--target", default="hinglish", choices=["hinglish", "hindi", "english"])
    parser.add_argument("--hazards-only", action="store_true", help="Only run TTS hazard check (no API needed)")
    args = parser.parse_args()

    with open(args.script_file) as f:
        script = f.read()

    if args.hazards_only:
        # No API needed for hazard check
        issues = []
        for i, line in enumerate(script.splitlines(), 1):
            for pattern, detail in TTS_HAZARDS:
                if re.search(pattern, line):
                    issues.append(f"Line {i}: {detail}\n  > {line.strip()[:80]}")
        print("\n".join(issues) if issues else "No TTS hazards found.")
        return

    bc = BhashaCut()
    report = bc.full_report(script, args.target)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
