from django.db import models


class JobState(models.Model):
    """When each background job last finished successfully.

    It is stored in the database (not in memory), so a restarted worker knows
    what already ran and neither skips a job nor repeats it.
    """

    name = models.CharField(max_length=40, unique=True)
    last_run_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name
