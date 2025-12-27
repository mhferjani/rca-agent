"""Demo DAG that simulates an OOM error for RCA Agent testing."""

from datetime import datetime, timedelta

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


def simulate_oom():
    """Simulate an OOM error."""
    # This will raise a MemoryError-like exception
    raise MemoryError("java.lang.OutOfMemoryError: Java heap space")


def process_data():
    """Simulate data processing."""
    print("Processing data...")
    import time

    time.sleep(2)
    print("Data processed successfully")


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
    "on_failure_callback": failure_callback,
}

with DAG(
    "demo_oom_failure",
    default_args=default_args,
    description="Demo DAG that simulates an OOM error",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["demo", "rca-agent"],
) as dag:
    task_extract = PythonOperator(
        task_id="extract_data",
        python_callable=process_data,
    )

    task_transform = PythonOperator(
        task_id="transform_large_dataset",
        python_callable=simulate_oom,
    )

    task_load = PythonOperator(
        task_id="load_to_warehouse",
        python_callable=process_data,
    )

    task_extract >> task_transform >> task_load
