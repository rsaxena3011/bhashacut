.PHONY: run build

# Build the Docker image
build:
	docker build -t bhashacut .

# Run the project in Docker (works from clean checkout)
# TTS hazard detector runs offline, no API key needed
# For full Apertus features, set LLM_API_KEY env var
run: build
	docker run --rm \
		-e LLM_NAME=$${LLM_NAME:-swiss-ai/apertus-8b-instruct} \
		-e LLM_BASE_URL=$${LLM_BASE_URL:-https://api.publicai.co/v1} \
		-e LLM_API_KEY=$${LLM_API_KEY} \
		bhashacut
