from django.db import models

# Create your models here.
from django.db import models


class GradeResult(models.Model):
    """The score of one scanned sheet, computed from its own version's key."""
    scan = models.OneToOneField(
        "omr.SheetScan", on_delete=models.CASCADE, related_name="grade")
    student_label = models.CharField(max_length=120, blank=True)
    score = models.PositiveIntegerField()
    max_score = models.PositiveIntegerField()
    correct_count = models.PositiveSmallIntegerField()
    wrong_count = models.PositiveSmallIntegerField()
    blank_count = models.PositiveSmallIntegerField()
    details = models.JSONField(default=list, blank=True)   # per item: item, answer, key, correct, points
    graded_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.scan_id}: {self.score}/{self.max_score}"

    @property
    def percent(self):
        return round(100 * self.score / self.max_score, 1) if self.max_score else 0.0