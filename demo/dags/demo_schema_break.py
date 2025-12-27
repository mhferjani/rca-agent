"""Demo DAG that simulates a schema mismatch error."""

from datetime import datetime

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator


def failure_callback(context):
    """Send failure notification to RCA Agent."""
    payload = {
        "dag_id": context["dag"].dag_id,
        "task_id": context["task_instance"].task_id,
        "run_id": context["dag_run"].run_id,
        "execution_date": context["execution_date"].isoformat(),
        "state": "failed",
        "try_number": context["task_instance"].try_number,
        "exception": str(context.get("exception", "")),
    }

    try:
        requests.post(
            "http://rca-agent:8000/webhook/airflow",
            json=payload,
            timeout=5,
        )
    except Exception as e:
        print(f"Failed to notify RCA Agent: {e}")


def fetch_api_data():
    """Simulate fetching data from API."""
    print("Fetching data from external API...")
    import time

    time.sleep(1)
    # Return mock data without expected column
    return {"user_id": 123, "name": "Test User"}


def parse_response(**context):
    """Simulate parsing API response with schema error."""
    data = context["task_instance"].xcom_pull(task_ids="fetch_data")

    # Simulate schema mismatch - expected column doesn't exist
    print(f"Received data: {data}")
    print("Attempting to access 'customer_id' column...")

    # This will raise KeyError
    raise KeyError("column 'customer_id' not found in API response - schema changed")


def load_data():
    """Simulate loading data."""
    print("Loading data to warehouse...")
    import time

    time.sleep(1)
    print("Data loaded successfully")


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
    "on_failure_callback": failure_callback,
}

with DAG(
    "demo_schema_break",
    default_args=default_args,
    description="Demo DAG that simulates a schema mismatch error",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["demo", "rca-agent"],
) as dag:
    task_fetch = PythonOperator(
        task_id="fetch_data",
        python_callable=fetch_api_data,
    )

    task_parse = PythonOperator(
        task_id="parse_response",
        python_callable=parse_response,
        provide_context=True,
    )

    task_load = PythonOperator(
        task_id="load_to_warehouse",
        python_callable=load_data,
    )

    task_fetch >> task_parse >> task_load
