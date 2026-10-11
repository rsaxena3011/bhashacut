# BhashaCut

**Hinglish video script assistant powered by Apertus, Switzerland's open LLM.**

Indian video creators constantly juggle Hindi, English, and Hinglish in scripts, voiceovers, and on-screen text. Most AI models mangle code-switching. Apertus is trained on 1800+ languages with strong multilingual support, making it ideal for this.

## What it does

1. **Script polishing** - Takes rough Hinglish and smooths it into natural, voiceover-ready text (or pure Hindi / pure English)
2. **TTS hazard detection** - Flags characters and patterns that break TTS engines (no API needed, runs offline):
   - `कार्तिक`-style conjuncts that crash some backends
   - `…` ellipsis that truncates synthesis
   - Mixed Latin/Devanagari within single words
3. **Consistency checking** - Catches character name spelling variations and terminology drift

## Why Apertus?

- **Fully open** (Apache 2.0): weights, code, training data, checkpoints. Sovereign deployability.
- **Multilingual by design**: 40% non-English training tokens, 1800+ languages.
- **No vendor lock-in**: runs on Public AI, local Ollama, or self-hosted vLLM.

## Quick start

```bash
pip install openai

# TTS hazard check only (no API key needed)
python src/bhashacut.py my_script.txt --hazards-only

# Full polish (needs Apertus endpoint)
export PUBLICAI_API_KEY="your-key"  # from https://publicai.co
python src/bhashacut.py my_script.txt --target hinglish
```

### Local Ollama (no key, offline)

```bash
ollama pull MichelRosselli/apertus:8b-instruct-2509-q4_k_m
export APERTUS_BASE_URL="http://localhost:11434/v1"
export APERTUS_MODEL="MichelRosselli/apertus:8b-instruct-2509-q4_k_m"
python src/bhashacut.py my_script.txt
```

## Hack Apertus - Track 2B: Own Project

Built for [Hack Apertus](https://hackapertus.devpost.com/) Online Hackathon (Oct 1-16, 2026).

**Judging criteria addressed:**
- **Purposeful use of AI**: Solves a real problem for 100M+ Indian content creators wrestling with multilingual scripts
- **Technical rigour**: Rule-based TTS hazard detection + LLM polishing with constrained prompts, evaluated on real production scripts
- **Value & scalability**: Zero marginal cost per script after setup; works for any Indian language pair
- **Sovereign deployability**: Apache 2.0 model, self-hostable, no data leaves your infrastructure
- **Implementation feasibility**: Single-file Python, OpenAI-compatible API, works today

## License

MIT
