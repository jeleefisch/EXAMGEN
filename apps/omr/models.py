from django.conf import settings
from django.db import models

from apps.exams.models import Exam, ExamVersion
from core import sheet_layout as L


class SheetScan(models.Model):
    """One uploaded photo of one answer sheet."""

    class Status(models.TextChoices):
        READ = "read", "Read"
        NEEDS_VERSION = "needs_version", "Needs version"
        UNREADABLE = "unreadable", "Unreadable"

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="scans")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    version = models.ForeignKey(
        ExamVersion, on_delete=models.SET_NULL, null=True, blank=True, related_name="scans")
    serial = models.PositiveIntegerField(null=True, blank=True)
    image = models.FileField(upload_to="scans/%Y/%m/")
    original_name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=14, choices=Status.choices, default=Status.UNREADABLE)
    qr_ok = models.BooleanField(default=False)
    rotation_steps = models.PositiveSmallIntegerField(default=0)
    warnings = models.JSONField(default=list, blank=True)
    error = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.original_name} ({self.get_status_display()})"

    @property
    def pending_count(self):
        return sum(1 for i in self.items.all() if i.needs_review)

    @property
    def is_ready(self):
        """Ready for grading: version known and every uncertain row resolved."""
        return (self.status == self.Status.READ and self.version_id is not None
                and self.pending_count == 0)


class ScanItem(models.Model):
    """What the reader saw for one item, plus the human's decision if any."""
    AMBIGUOUS = "ambiguous"
    MULTIPLE = "multiple"
    BLANK = "blank"
    SELECTED = "selected"

    scan = models.ForeignKey(SheetScan, on_delete=models.CASCADE, related_name="items")
    item = models.PositiveSmallIntegerField()            # 1-based
    choices_count = models.PositiveSmallIntegerField()   # 2 = True/False, 4 = multiple choice
    status = models.CharField(max_length=12)             # selected | blank | multiple | ambiguous
    detected = models.CharField(max_length=10, blank=True)   # "B", "-", "CD", "?"
    ratios = models.JSONField(default=list, blank=True)
    resolved = models.CharField(max_length=1, blank=True)    # human answer: letter or "-"

    class Meta:
        ordering = ("item",)
        constraints = [
            models.UniqueConstraint(fields=("scan", "item"), name="unique_item_per_scan"),
        ]

    def __str__(self):
        return f"{self.scan_id} #{self.item}: {self.detected}"

    @property
    def needs_review(self):
        return self.status in (self.AMBIGUOUS, self.MULTIPLE) and not self.resolved

    @property
    def final(self):
        """The answer to grade: human decision first, else a confident machine reading."""
        if self.resolved:
            return self.resolved
        if self.status == self.BLANK:
            return "-"
        if self.status == self.SELECTED:
            return self.detected
        return ""

    def valid_codes(self):
        return ["-"] + list(L.LABELS[:self.choices_count])