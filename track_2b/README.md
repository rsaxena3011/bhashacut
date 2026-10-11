# BhashaCut — Track 2B: Own Project

**Hinglish video script assistant powered by Apertus, Switzerland's open LLM.**

Indian video creators constantly juggle Hindi, English, and Hinglish in scripts, voiceovers, and on-screen text. Most AI models mangle code-switching. Apertus is trained on 1800+ languages with 40% non-English tokens, making it ideal for this.

## What it does

1. **Script polishing** — Takes rough Hinglish and smooths it into natural, voiceover-ready text (Hinglish, Hindi, or English)
2. **TTS hazard detection** — Flags characters and patterns that break TTS engines (runs offline, no API needed):
   - `कार्तिक`-style conjuncts that crash some backends
   - `…` ellipsis that truncates synthesis
   - Mixed Latin/Devanagari within single words
3. **Consistency checking** — Catches character name spelling variations and terminology drift

## Quick start

```bash
cd track_2b
make run
```

This runs the TTS hazard detector on the sample script via Docker. No API key needed.

For full Apertus-powered polishing:

```bash
export LLM_API_KEY="your-publicai-key"
make run
```

Or with local Ollama (no API key needed):

```bash
export LLM_BASE_URL="http://localhost:11434/v1"
export LLM_NAME="swiss-ai/apertus-8b-instruct"
make run
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_NAME` | `swiss-ai/apertus-8b-instruct` | Apertus model to use |
| `LLM_BASE_URL` | `https://api.publicai.co/v1` | API endpoint |
| `LLM_API_KEY` | (none) | API key for the endpoint |

## Target architecture

**a) On-premise** — The TTS hazard detector runs fully offline. Apertus can be self-hosted via Ollama or vLLM. Docker container includes all dependencies.

## Project structure

```
track_2b/
├── Dockerfile          # Container definition
├── Makefile            # make run entrypoint
├── README.md           # This file
├── technical_report.md # Full technical writeup
├── src/
│   └── bhashacut.py    # Main CLI tool
├── data/
│   └── sample_script.txt  # Test script with hazard patterns
└── docs/
    └── PROJECT_README.md  # Extended documentation
```

## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

---

*Challenge description: Bring your own idea and build a working Apertus prototype that tackles a problem you care about. Submissions must use the Apertus model family. See the [Hack Apertus site](https://hackapertus.ch) for full details.*
