from datetime import datetime, timedelta
from datetime import time as clock
from unittest import mock
from zoneinfo import ZoneInfo

from catalog.testing import AppTestCase
from worker import scheduler
from worker.models import JobState
from worker.scheduler import Job

TASHKENT = ZoneInfo("Asia/Tashkent")


def at(hour, minute=0, day=10):
    return datetime(2026, 10, day, hour, minute, tzinfo=TASHKENT)


class IsDueTest(AppTestCase):
    def test_interval_job(self):
        job = Job("match", mock.Mock(), every=timedelta(minutes=10))
        now = at(12)
        self.assertTrue(scheduler.is_due(job, None, now))  # never ran
        self.assertFalse(scheduler.is_due(job, now - timedelta(minutes=9), now))
        self.assertTrue(scheduler.is_due(job, now - timedelta(minutes=10), now))

    def test_daily_job_waits_for_its_time(self):
        job = Job("digest", mock.Mock(), daily_at=clock(9, 0))
        self.assertFalse(scheduler.is_due(job, None, at(8, 59)))
        self.assertTrue(scheduler.is_due(job, None, at(9, 1)))

    def test_daily_job_runs_once_a_day(self):
        job = Job("digest", mock.Mock(), daily_at=clock(9, 0))
        self.assertFalse(scheduler.is_due(job, at(9, 1), at(15)))  # already ran today
        self.assertTrue(scheduler.is_due(job, at(9, 1, day=9), at(9, 2)))  # ran yesterday

    def test_daily_job_that_missed_its_time_runs_after_a_restart(self):
        job = Job("digest", mock.Mock(), daily_at=clock(9, 0))
        self.assertTrue(scheduler.is_due(job, at(9, 1, day=9), at(18)))


class RunDueJobsTest(AppTestCase):
    def run_with(self, jobs, now):
        with mock.patch.object(scheduler, "JOBS", jobs):
            scheduler.run_due_jobs(now)

    def test_a_job_that_ran_is_remembered(self):
        function = mock.Mock()
        now = at(12)
        self.run_with([Job("a", function, every=timedelta(minutes=10))], now)
        function.assert_called_once_with()
        self.assertEqual(JobState.objects.get(name="a").last_run_at, now)
        self.run_with([Job("a", function, every=timedelta(minutes=10))], now + timedelta(minutes=1))
        function.assert_called_once()  # not due again yet

    def test_the_time_of_the_last_run_is_passed_on(self):
        function = mock.Mock()
        job = Job("a", function, every=timedelta(minutes=10), needs_since=True)
        self.run_with([job], at(12))
        function.assert_called_with(None)
        self.run_with([job], at(12, 30))
        function.assert_called_with(at(12))

    def test_a_failing_job_is_retried_and_does_not_stop_the_others(self):
        broken = mock.Mock(side_effect=RuntimeError("boom"))
        fine = mock.Mock()
        jobs = [
            Job("broken", broken, every=timedelta(minutes=10)),
            Job("fine", fine, every=timedelta(minutes=10)),
        ]
        with self.assertLogs("worker.scheduler", "ERROR"):
            self.run_with(jobs, at(12))
        fine.assert_called_once()
        self.assertIsNone(JobState.objects.get(name="broken").last_run_at)
        self.assertIsNotNone(JobState.objects.get(name="fine").last_run_at)

    def test_the_real_job_list(self):
        self.assertEqual([job.name for job in scheduler.JOBS], ["match", "expiry", "digest"])
