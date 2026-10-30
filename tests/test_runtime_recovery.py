"""A stopped news worker group must not leave a permanent scheduler slot occupied."""

import unittest
from dagster import DagsterInstance, DagsterRunStatus, job
from dagster._core.remote_origin import GrpcServerCodeLocationOrigin, RemoteRepositoryOrigin, RemoteJobOrigin
from news.runtime_recovery import recover_interrupted_runs


@job(name='news_refresh_job')
def news_job():
    pass


@job(name='property_job')
def other_job():
    pass


class RuntimeRecoveryTests(unittest.TestCase):
    def test_only_interrupted_news_workers_are_failed(self):
        with DagsterInstance.ephemeral() as instance:
            interrupted = instance.create_run_for_job(news_job, tags={'dagster/code_location':'daily-news'}, status=DagsterRunStatus.STARTED)
            origin = RemoteJobOrigin(RemoteRepositoryOrigin(GrpcServerCodeLocationOrigin(host='127.0.0.1', port=2472, location_name='daily-news'), '__repository__'), 'news_refresh_job')
            queued = instance.create_run_for_job(news_job, tags={'dagster/code_location':'daily-news'}, status=DagsterRunStatus.QUEUED, remote_job_origin=origin)
            other = instance.create_run_for_job(other_job, tags={'dagster/code_location':'other'}, status=DagsterRunStatus.STARTED)
            elsewhere = instance.create_run_for_job(news_job, tags={'dagster/code_location':'other'}, status=DagsterRunStatus.STARTED)
            self.assertEqual(recover_interrupted_runs(instance), 1)
            self.assertEqual(instance.get_run_by_id(interrupted.run_id).status, DagsterRunStatus.FAILURE)
            self.assertEqual(instance.get_run_by_id(queued.run_id).status, DagsterRunStatus.QUEUED)
            self.assertEqual(instance.get_run_by_id(other.run_id).status, DagsterRunStatus.STARTED)
            self.assertEqual(instance.get_run_by_id(elsewhere.run_id).status, DagsterRunStatus.STARTED)
            self.assertEqual(recover_interrupted_runs(instance), 0)
