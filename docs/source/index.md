# RCA Agent Documentation

**Intelligent Root Cause Analysis for Data Engineering Pipelines**

```{toctree}
:maxdepth: 2
:caption: Contents

getting-started
configuration
usage
api-reference
custom-collectors
```

## Overview

RCA Agent is an autonomous agent that diagnoses pipeline failures in seconds instead of hours. When a pipeline fails, the agent:

1. **Collects context** from Airflow, Git, and data sources
2. **Analyzes logs** using pattern matching and LLM intelligence
3. **Searches history** for similar past incidents
4. **Generates reports** with root cause and recommendations

## Quick Example

```python
from rca_agent import RCAAgent, FailureEvent

agent = RCAAgent()

event = FailureEvent(
    dag_id="etl_sales_daily",
    task_id="load_to_warehouse",
    run_id="scheduled__2024-01-15T00:00:00+00:00",
)

report = await agent.analyze(event)

print(f"Root Cause: {report.root_cause}")
print(f"Confidence: {report.confidence:.0%}")
print(f"Category: {report.error_category.value}")
```

## Features

- 🔄 **Multi-source Context Collection**: Airflow logs, Git history, source health
- 🧠 **LLM-powered Analysis**: Claude or GPT-4 for intelligent diagnosis
- 📚 **Historical Learning**: RAG-based retrieval of similar incidents
- 🏷️ **Error Classification**: Automatic categorization (OOM, schema, timeout, etc.)
- 📊 **Structured Reports**: JSON/Markdown/HTML with confidence scores
- 🔔 **Slack Integration**: Enriched notifications

## Indices and tables

* {ref}`genindex`
* {ref}`modindex`
* {ref}`search`
