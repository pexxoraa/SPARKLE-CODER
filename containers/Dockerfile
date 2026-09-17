FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv nodejs npm git ripgrep \
    build-essential cmake curl ca-certificates unzip \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
CMD ["sh"]
