"""Validate the real Dagster schedule, retry policy and publication envelope."""

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from news.dagster_defs import defs, news_refresh_job, news_schedule


class ScheduleTests(unittest.TestCase):
    def test_two_runs_in_auckland_wall_clock_time(self):
        self.assertEqual(news_schedule.cron_schedule, '0 3,15 * * *')
        self.assertEqual(news_schedule.execution_timezone, 'Pacific/Auckland')
        from dagster._utils.schedules import schedule_execution_time_iterator
        for month in (1, 7):
            start = datetime(2026, month, 10, 0, tzinfo=ZoneInfo('Pacific/Auckland'))
            iterator = schedule_execution_time_iterator(start.timestamp(), news_schedule.cron_schedule, news_schedule.execution_timezone)
            ticks = [next(iterator), next(iterator)]
            self.assertEqual([t.hour for t in ticks], [3, 15])

    def test_isolated_job_has_bounded_retries(self):
        self.assertEqual(news_refresh_job.name, 'news_refresh_job')
        op = news_refresh_job.graph.node_defs[0]
        self.assertEqual(op.retry_policy.max_retries, 2)
        self.assertEqual(op.retry_policy.delay, 300)
        self.assertEqual(defs.resolve_schedule_def('news_twice_daily').job.name, news_refresh_job.name)
