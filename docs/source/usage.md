# Usage Guide

This guide covers common usage patterns for RCA Agent.

## Basic Analysis

### Analyzing a Failure

```python
from rca_agent import RCAAgent, FailureEvent

agent = RCAAgent()

event = FailureEvent(
    dag_id="etl_sales_daily",
    task_id="load_to_warehouse",
    run_id="scheduled__2024-01-15T00:00:00+00:00",
    error_message="java.lang.OutOfMemoryError: Java heap space",
    try_number=1,
)

report = await agent.analyze(event)
```

### Understanding the Report

```python
# Basic info
print(f"Report ID: {report.report_id}")
print(f"Category: {report.error_category.value}")
print(f"Severity: {report.severity.value}")
print(f"Confidence: {report.confidence:.0%}")

# Root cause
print(f"Root Cause: {report.root_cause}")
print(f"Summary: {report.root_cause_summary}")

# Evidence
for evidence in report.evidence:
    print(f"  - {evidence}")

# Recommendations
for rec in report.recommendations:
    print(f"  [{rec.priority}] {rec.action}")
    if rec.estimated_effort:
        print(f"      Effort: {rec.estimated_effort}")
```

## Formatting Reports

### Markdown

```python
markdown = agent.format_report(report, format="markdown")
print(markdown)

# Or save to file
with open("report.md", "w") as f:
    f.write(markdown)
```

### HTML

```python
html = agent.format_report(report, format="html")
with open("report.html", "w") as f:
    f.write(html)
```

### JSON

```python
import json
json_str = agent.format_report(report, format="json")
data = json.loads(json_str)
```

## Webhook Integration

### Setting Up Airflow Callback

In your Airflow DAG:

```python
import requests

def failure_callback(context):
    payload = {
        "dag_id": context["dag"].dag_id,
        "task_id": context["task_instance"].task_id,
        "run_id": context["dag_run"].run_id,
        "execution_date": context["execution_date"].isoformat(),
        "state": "failed",
        "try_number": context["task_instance"].try_number,
        "exception": str(context.get("exception", "")),
    }

    requests.post(
        "http://rca-agent:8000/webhook/airflow",
        json=payload,
        timeout=5,
    )

default_args = {
    "on_failure_callback": failure_callback,
}
```

### Starting the Server

```bash
rca-agent serve --port 8000
```

### API Endpoints

- `POST /webhook/airflow` - Receive Airflow callbacks
- `POST /analyze` - Manually trigger analysis
- `GET /health` - Health check
- `PATCH /reports/{id}/resolution` - Update resolution

## Working with Historical Incidents

### Finding Similar Incidents

```python
similar = agent.get_similar_incidents(
    dag_id="etl_sales_daily",
    task_id="load_to_warehouse",
    error_text="OutOfMemoryError",
    max_results=5,
)

for incident in similar:
    print(f"[{incident.date}] {incident.root_cause}")
    print(f"  Similarity: {incident.similarity_score:.0%}")
    if incident.resolution:
        print(f"  Resolution: {incident.resolution}")
```

### Recording Resolutions

When you fix an issue, record the resolution:

```python
agent.update_resolution(
    report_id=report.report_id,
    resolution="Increased executor memory from 4GB to 8GB",
)
```

This helps future analyses suggest proven solutions.

## CLI Usage

### Analyze Command

```bash
# Basic analysis
rca-agent analyze \
    --dag-id etl_sales_daily \
    --task-id load_to_warehouse \
    --run-id "scheduled__2024-01-15"

# With output file
rca-agent analyze \
    --dag-id etl_sales_daily \
    --task-id load_to_warehouse \
    --run-id "run_001" \
    --format html \
    --output report.html

# Without Slack notification
rca-agent analyze \
    --dag-id etl_sales_daily \
    --task-id load_to_warehouse \
    --run-id "run_001" \
    --no-notify
```

### Server Command

```bash
# Start server
rca-agent serve --port 8000

# With auto-reload (development)
rca-agent serve --port 8000 --reload
```

### Statistics

```bash
rca-agent stats
```

### Demo Scenarios

```bash
# Run demo scenarios
rca-agent demo --scenario oom
rca-agent demo --scenario schema-break
rca-agent demo --scenario source-timeout
```
