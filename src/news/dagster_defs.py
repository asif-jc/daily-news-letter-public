"""Expose the private publication workflow as one isolated Dagster code location.
The retained news workflow owns processing checkpoints; Dagster owns launch, retries and schedule history.
"""

from dagster import Definitions, RetryPolicy, ScheduleDefinition, job, op

import json
import subprocess
import sys
from pathlib import Path


@op(retry_policy=RetryPolicy(max_retries=2, delay=300))
def publish_daily_news(context):
    # Re-execution must use the original attempt's checkpoint rather than collect again.
    attempt_id = context.dagster_run.root_run_id or context.run_id
    # A child process gives even a wedged publisher a three-hour hard execution bound.
    subprocess.run(
        [sys.executable, '-m', 'news', 'refresh', '--attempt', attempt_id],
        check=True, timeout=10800,
    )
    result = json.loads((Path('.local/automation') / (attempt_id + '.json')).read_text())
    context.add_output_metadata({
        'news_run_id': result['run_id'],
        'public_commit': result['commit'],
        'files_verified': result['confirmed']['files_verified'],
    })
    return result['run_id']


@job
def news_refresh_job():
    publish_daily_news()


news_schedule = ScheduleDefinition(
    name='news_twice_daily',
    job=news_refresh_job,
    cron_schedule='0 3,15 * * *',
    execution_timezone='Pacific/Auckland',
)

defs = Definitions(jobs=[news_refresh_job], schedules=[news_schedule])
