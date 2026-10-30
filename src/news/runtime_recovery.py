"""Release orphaned news slots before the isolated systemd worker group starts.
Only ExecStartPre may call this: KillMode=control-group must have stopped all prior news workers.
"""

from dagster import DagsterInstance, DagsterRunStatus, RunsFilter


def recover_interrupted_runs(instance):
    runs = instance.get_runs(filters=RunsFilter(
        job_name='news_refresh_job',
        tags={'dagster/code_location': 'daily-news'},
        statuses=[DagsterRunStatus.STARTING, DagsterRunStatus.STARTED, DagsterRunStatus.CANCELING],
    ))
    for run in runs:
        instance.report_run_failed(
            run,
            message='The isolated news worker group stopped before completion. '
                    'Pipeline checkpoints are retained; the next scheduled run may proceed.',
        )
    return len(runs)


if __name__ == '__main__':
    with DagsterInstance.get() as instance:
        print('Interrupted news workers recorded: ' + str(recover_interrupted_runs(instance)))
