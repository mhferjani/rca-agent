# Getting Started

This guide will help you get RCA Agent up and running quickly.

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- An Anthropic or OpenAI API key
- Access to an Airflow instance (optional for demo)

## Installation

### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/rca-agent.git
cd rca-agent

# Install with uv
uv sync

# Activate the virtual environment
source .venv/bin/activate
```

### Using pip

```bash
# Clone and create virtual environment
git clone https://github.com/yourusername/rca-agent.git
cd rca-agent
python -m venv .venv
source .venv/bin/activate

# Install with pip
pip install -e ".[dev]"
```

## Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` with your settings:

```bash
# Required: LLM API key
ANTHROPIC_API_KEY=sk-ant-api03-...

# Airflow connection (if using real Airflow)
AIRFLOW_BASE_URL=http://localhost:8080
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=admin

# Optional: Slack notifications
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## Quick Start

### Python API

```python
import asyncio
from rca_agent import RCAAgent, FailureEvent

async def main():
    # Initialize agent
    agent = RCAAgent()

    # Create a failure event
    event = FailureEvent(
        dag_id="etl_sales_daily",
        task_id="load_to_warehouse",
        run_id="scheduled__2024-01-15T00:00:00+00:00",
        error_message="java.lang.OutOfMemoryError: Java heap space",
    )

    # Run analysis
    report = await agent.analyze(event)

    # Print results
    print(f"Root Cause: {report.root_cause}")
    print(f"Confidence: {report.confidence:.0%}")
    print(f"Recommendations:")
    for rec in report.recommendations:
        print(f"  - {rec.action}")

asyncio.run(main())
```

### Command Line

```bash
# Analyze a specific failure
rca-agent analyze \
    --dag-id etl_sales_daily \
    --task-id load_to_warehouse \
    --run-id "scheduled__2024-01-15T00:00:00+00:00" \
    --error "java.lang.OutOfMemoryError"

# Save report to file
rca-agent analyze \
    --dag-id etl_sales_daily \
    --task-id load_to_warehouse \
    --run-id "run_001" \
    --format html \
    --output report.html
```

### Webhook Server

```bash
# Start the webhook server
rca-agent serve --port 8000

# The server exposes:
# - POST /webhook/airflow - Receive Airflow callbacks
# - POST /analyze - Manually trigger analysis
# - GET /health - Health check
```

## Next Steps

- Read the [Configuration Guide](configuration.md) for detailed settings
- Learn about [Custom Collectors](custom-collectors.md)
- Check the [API Reference](api-reference.md) for all options
