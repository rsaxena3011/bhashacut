FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir openai

# Copy source code
COPY src/ ./src/
COPY data/ ./data/

# Default: run TTS hazard check on sample script (works offline, no API key needed)
# For full Apertus features, set LLM_API_KEY environment variable
CMD ["python", "src/bhashacut.py", "data/sample_script.txt", "--hazards-only"]
