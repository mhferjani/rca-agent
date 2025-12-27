# Configuration Guide

RCA Agent can be configured through environment variables or programmatically.

## Environment Variables

All configuration can be set via environment variables. Copy `.env.example` to `.env` and customize:

### LLM Configuration

```bash
# Choose provider: "anthropic" or "openai"
LLM_PROVIDER=anthropic

# Anthropic (Claude)
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# OpenAI (GPT-4)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

### Airflow Connection

```bash
AIRFLOW_BASE_URL=http://localhost:8080
AIRFLOW_USERNAME=admin
AIRFLOW_PASSWORD=admin
AIRFLOW_TIMEOUT=30
```

### Git Repository

```bash
# Path to repository containing DAG files
GIT_REPO_PATH=/opt/airflow/dags

# How far back to search for commits
GIT_LOOKBACK_HOURS=24
```

### Source Health Checks

Configure sources to check in your code:

```python
from rca_agent.agent import AgentConfig

config = AgentConfig(
    sources=[
        {
            "name": "sales_api",
            "type": "api",
            "url": "https://api.example.com/health",
            "expected_status": 200,
        },
        {
            "name": "warehouse_db",
            "type": "database",
            "connection_string": "postgresql://user:pass@host:5432/db",
        },
    ]
)
```

### Knowledge Base

```bash
# ChromaDB persistence directory
CHROMA_PERSIST_DIR=./data/chroma

# Collection name for incidents
CHROMA_COLLECTION=rca_incidents

# Max similar incidents to retrieve
MAX_SIMILAR_INCIDENTS=5
```

### Notifications

```bash
# Slack webhook
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_CHANNEL=#data-alerts
```

### Feature Flags

```bash
ENABLE_GIT_COLLECTOR=true
ENABLE_SOURCE_HEALTH_COLLECTOR=true
ENABLE_METRICS_COLLECTOR=false
```

## Programmatic Configuration

You can also configure the agent programmatically:

```python
from rca_agent import RCAAgent
from rca_agent.agent import AgentConfig

config = AgentConfig(
    airflow_base_url="http://airflow:8080",
    airflow_username="admin",
    airflow_password="secret",
    llm_provider="anthropic",
    llm_api_key="sk-ant-...",
    git_repo_path="/opt/airflow/dags",
    max_similar_incidents=10,
    sources=[
        {"name": "api", "type": "api", "url": "https://api.example.com/health"},
    ],
)

agent = RCAAgent(config=config)
```

## Error Categories

RCA Agent classifies errors into these categories:

| Category | Description | Example Patterns |
|----------|-------------|------------------|
| `resource_exhaustion` | Memory, disk, or CPU exhaustion | OOM, heap space, disk full |
| `schema_mismatch` | Data schema issues | Column not found, type error |
| `source_unavailable` | External service down | Connection refused, 5xx |
| `data_quality` | Data validation failures | NULL constraint, duplicates |
| `permission_error` | Auth/permission issues | 403, token expired |
| `code_regression` | Bug introduced by code change | Error after recent deploy |
| `volume_anomaly` | Unexpected data volume | 0 rows, 10x volume |
| `network_error` | Network connectivity | SSL error, DNS failure |
| `configuration_error` | Misconfiguration | Invalid config value |
| `unknown` | Cannot determine | Fallback category |

## Severity Levels

- **CRITICAL**: Immediate action required, affects production
- **HIGH**: Should be addressed soon, significant impact
- **MEDIUM**: Should be investigated, moderate impact
- **LOW**: Minor issue, can be scheduled for later
