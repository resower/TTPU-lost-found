"""A small loop that runs the jobs when they are due. (Celery would be overkill for 3 jobs.)

Every 30 seconds it checks each job. The time each job last finished is stored in the
database (JobState), so after a restart the worker continues where it stopped.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import time as clock
from zoneinfo import ZoneInfo

from django.utils import timezone

from . import jobs
from .models import JobState

log = logging.getLogger(__name__)

TASHKENT = ZoneInfo("Asia/Tashkent")
POLL_SECONDS = 30


@dataclass
class Job:
    name: str
    function: Callable
    every: timedelta | None = None  # run every N minutes/hours ...
    daily_at: clock | None = None  # ... or once a day at this Tashkent time
    needs_since: bool = False  # pass the time of the last successful run to the function


JOBS = [
    Job("match", jobs.match_run, every=timedelta(minutes=10), needs_since=True),
    Job("expiry", jobs.expire_lost_reports, every=timedelta(hours=1)),
    Job("digest", jobs.daily_digest, daily_at=clock(9, 0)),
]


def is_due(job, last_run_at, now):
    """Should this job run now?"""
    if job.daily_at:
        today = now.astimezone(TASHKENT).date()
        scheduled = datetime.combine(today, job.daily_at, tzinfo=TASHKENT)
        return now >= scheduled and (last_run_at is None or last_run_at < scheduled)
    return last_run_at is None or now - last_run_at >= job.every


def run_due_jobs(now=None):
    """Run every job that is due. A failing job is logged and never stops the others."""
    now = now or timezone.now()
    for job in JOBS:
        state, _created = JobState.objects.get_or_create(name=job.name)
        if not is_due(job, state.last_run_at, now):
            continue
        try:
            if job.needs_since:
                job.function(state.last_run_at)
            else:
                job.function()
        except Exception:
            log.exception("Job %s failed, it will be tried again", job.name)
            continue
        # Saved only after success. `now` is taken before the job started, so anything that
        # arrived while it was running is picked up by the next run.
        state.last_run_at = now
        state.save(update_fields=["last_run_at"])


def main():
    log.info("Worker started")
    while True:
        run_due_jobs()
        time.sleep(POLL_SECONDS)
