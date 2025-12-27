FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY src/ src/

# Install dependencies
RUN uv pip install --system -e ".[all]"

# Create data directory
RUN mkdir -p /data/chroma

# Default command
CMD ["rca-agent", "serve", "--port", "8000"]
