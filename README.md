# 🔍 RCA Agent

[![CI](https://github.com/yourusername/rca-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/rca-agent/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> **Intelligent Root Cause Analysis Agent for Data Engineering Pipelines**

An autonomous agent that diagnoses pipeline failures in seconds instead of hours. When a pipeline fails, RCA Agent collects context from multiple sources, analyzes logs with LLM intelligence, and produces actionable diagnostic reports.

## 🎯 Problem Statement

When a data pipeline fails in production, Data Engineers typically spend **30 minutes to 2+ hours** on manual investigation:

1. Finding the failed task in Airflow/Dagster
2. Reading through verbose, poorly formatted logs
3. Checking for recent deployments (git blame, CI history)
4. Verifying source health (API status, schema changes, volume anomalies)
5. Reviewing infrastructure metrics (memory, CPU, connections)
6. Correlating with past similar incidents

**RCA Agent automates this entire workflow**, reducing MTTR from hours to seconds.

## ✨ Features

- 🔄 **Multi-source Context Collection** - Aggregates logs, metadata, git history, and source health
- 🧠 **LLM-powered Analysis** - Intelligent root cause identification using Claude, GPT-4, or Mistral
- 📚 **Historical Learning** - RAG-based retrieval of similar past incidents with ChromaDB
- 🏷️ **Error Classification** - Automatic categorization (OOM, schema mismatch, timeout, etc.)
- 📊 **Structured Reports** - Markdown/HTML/JSON reports with confidence scores and recommendations
- 🔔 **Slack Notifications** - Enriched alerts with actionable context
- 🔌 **Extensible Architecture** - Pluggable collectors, analyzers, and LLM providers
- 🛡️ **Fallback Analysis** - Pattern-based analysis when LLM is unavailable

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRIGGER                                  │
│         Airflow webhook / CLI / API on pipeline failure         │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   COLLECTORS (parallel)                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │  Airflow    │ │    Git      │ │   Source    │ │  Metrics  │ │
│  │  Collector  │ │  Collector  │ │   Health    │ │ Collector │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘ │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ANALYSIS ENGINE                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐   │
│  │   Pattern   │ │     RAG     │ │      LLM Analyzer       │   │
│  │   Matcher   │ │  (ChromaDB) │ │ (Claude/GPT-4/Mistral)  │   │
│  └─────────────┘ └─────────────┘ └─────────────────────────┘   │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   RCA REPORT                                    │
│  • Error category    • Root cause       • Confidence score      │
│  • Evidence          • Recommendations  • Similar incidents     │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- An LLM API key (Anthropic, OpenAI, or Mistral)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/rca-agent.git
cd rca-agent

# Install with make
make install

# Or with pip
pip install -e .

# Copy environment template and configure
cp .env.example .env
```

### Configuration

Edit `.env` with your LLM provider:

```bash
# Choose ONE provider
LLM_PROVIDER=mistral
MISTRAL_API_KEY=your_api_key
MISTRAL_MODEL=open-mistral-7b

# Or use Anthropic
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-...

# Or use OpenAI
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...
```

### Run Demo

```bash
# Run OOM scenario demo
rca-agent demo --scenario oom

# Other scenarios
rca-agent demo --scenario schema-break
rca-agent demo --scenario source-timeout
rca-agent demo --scenario code-regression
```

### Example Output

```
╭───────── ✅ Analysis Complete ─────────╮
│ Category: resource_exhaustion          │
│ Severity: high                         │
│ Confidence: 95%                        │
│ Root Cause: Java heap space exhaustion │
╰────────────────────────────────────────╯
```

## 📖 Usage

### CLI

```bash
# Analyze a specific failure
rca-agent analyze --dag-id etl_sales_daily --task-id load_to_warehouse --run-id "scheduled__2024-01-15"

# Start webhook server (receives Airflow callbacks)
rca-agent serve --port 8000

# View incident statistics
rca-agent stats

# Export report to file
rca-agent demo --scenario oom --format html --output report.html
```

### Python API

```python
from rca_agent import RCAAgent
from rca_agent.models import FailureEvent

# Initialize agent
agent = RCAAgent()

# Analyze a failure
event = FailureEvent(
    dag_id="etl_sales_daily",
    task_id="load_to_warehouse",
    run_id="scheduled__2024-01-15T00:00:00+00:00",
    error_message="java.lang.OutOfMemoryError: Java heap space"
)

# Get diagnosis
report = await agent.analyze(event)
print(f"Root Cause: {report.root_cause}")
print(f"Confidence: {report.confidence}%")
print(f"Category: {report.category}")
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `LLM_PROVIDER` | LLM provider: `anthropic`, `openai`, `mistral`, `ollama` | Yes |
| `ANTHROPIC_API_KEY` | Anthropic API key | If using Anthropic |
| `OPENAI_API_KEY` | OpenAI API key | If using OpenAI |
| `MISTRAL_API_KEY` | Mistral API key | If using Mistral |
| `AIRFLOW_BASE_URL` | Airflow webserver URL | For Airflow integration |
| `AIRFLOW_USERNAME` | Airflow username | For Airflow integration |
| `AIRFLOW_PASSWORD` | Airflow password | For Airflow integration |
| `SLACK_WEBHOOK_URL` | Slack webhook for notifications | Optional |
| `GIT_REPO_PATH` | Path to DAGs repository | Optional |

### Supported LLM Providers

| Provider | Models | Free Tier |
|----------|--------|-----------|
| **Mistral** | `open-mistral-7b`, `open-mixtral-8x7b`, `mistral-small` | ✅ 1B tokens/month |
| **Anthropic** | `claude-sonnet-4-20250514`, `claude-3-haiku` | ❌ |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini` | ❌ |
| **Ollama** | `mistral`, `llama3`, `codellama` | ✅ Local |

### Error Categories

| Category | Signals |
|----------|---------|
| `resource_exhaustion` | OOM, heap space, disk full, timeout |
| `schema_mismatch` | Column not found, type error, parsing failed |
| `source_unavailable` | Connection refused, 5xx, upstream timeout |
| `data_quality` | Null constraint, unique violation, assertion failed |
| `permission_error` | 403, token expired, role missing |
| `code_regression` | Error after recent deployment |
| `configuration_error` | Missing config, invalid parameter |

## 📁 Project Structure

```
rca-agent/
├── src/rca_agent/
│   ├── cli.py              # CLI interface (Typer)
│   ├── main.py             # Main entry point
│   ├── agent/              # LangGraph workflow
│   │   ├── graph.py        # Agent graph definition
│   │   ├── nodes.py        # Graph nodes
│   │   └── state.py        # Agent state
│   ├── collectors/         # Data collectors
│   │   ├── airflow.py      # Airflow API collector
│   │   ├── git.py          # Git history collector
│   │   └── source_health.py
│   ├── analyzers/          # Analysis components
│   │   ├── llm_analyzer.py # Multi-provider LLM analysis
│   │   └── pattern_matcher.py
│   ├── knowledge/          # Knowledge base
│   │   └── incident_store.py  # ChromaDB storage
│   ├── models/             # Pydantic models
│   │   ├── context.py
│   │   ├── events.py
│   │   └── reports.py
│   ├── actions/            # Output actions
│   │   ├── formatters.py   # Report formatters
│   │   └── slack.py
│   └── api/
│       └── webhook.py      # FastAPI webhook server
├── tests/
├── docs/
├── demo/
│   ├── docker-compose.yml
│   └── dags/
├── .github/
│   └── workflows/
│       └── ci.yml
├── Makefile
├── pyproject.toml
└── .env.example
```

## 🛠️ Development

### Using Make

```bash
make help           # Show all commands

# Installation
make install        # Install base dependencies
make install-dev    # Install with dev tools
make install-all    # Install everything

# Quality
make test           # Run tests
make coverage       # Run tests with coverage
make lint           # Check code style
make format         # Format code
make typecheck      # Type checking
make check          # Run all checks

# Documentation
make docs           # Generate documentation
make docs-serve     # Serve docs locally

# Run
make demo           # Run demo scenario
make run            # Start webhook server
```

### Docker Demo

```bash
# Start Airflow + RCA Agent
make docker-up

# View logs
make docker-logs

# Stop
make docker-down
```

## 📚 Documentation

Full documentation available at [rca-agent.readthedocs.io](https://rca-agent.readthedocs.io)

- [Getting Started](docs/source/getting-started.md)
- [Configuration Guide](docs/source/configuration.md)
- [API Reference](docs/source/api-reference.md)
- [Custom Collectors](docs/source/custom-collectors.md)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent workflow framework
- [ChromaDB](https://github.com/chroma-core/chroma) - Vector storage for RAG
- [Mistral AI](https://mistral.ai/) - Free tier LLM API
- [Apache Airflow](https://airflow.apache.org/) - Pipeline orchestration

---

**Built with ❤️ for Data Engineers who are tired of debugging at 3 AM**
