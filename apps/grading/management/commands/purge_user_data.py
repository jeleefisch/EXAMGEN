"""Delete one user's exams, scans, grades, uploaded photos and (optionally) banks.

Dry run by default. Nothing is deleted without --yes. The account itself is kept.
"""
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.banks.models import QuestionBank
from apps.exams.models import Exam
from apps.grading.models import GradeResult
from apps.omr.models import SheetScan


class Command(BaseCommand):
    help = "Delete a user's test data (exams, scans, grades, photos, banks). Dry run unless --yes."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--yes", action="store_true", help="really delete")
        parser.add_argument("--keep-banks", action="store_true",
                            help="keep question banks and questions")

    def handle(self, *args, **opts):
        user = get_user_model().objects.filter(username=opts["username"]).first()
        if user is None:
            raise CommandError(f"No user named {opts['username']!r}.")
        exams = Exam.objects.filter(owner=user)
        scans = SheetScan.objects.filter(exam__in=exams)
        banks = QuestionBank.objects.filter(owner=user)
        files = [s.image.name for s in scans if s.image]
        summary = (f"exams: {exams.count()}, scans: {scans.count()}, "
                   f"grades: {GradeResult.objects.filter(scan__in=scans).count()}, "
                   f"photos: {len(files)}, "
                   f"banks: {0 if opts['keep_banks'] else banks.count()}")
        if not opts["yes"]:
            self.stdout.write(f"DRY RUN for {user.username}: would delete {summary}. "
                              "Run again with --yes to delete.")
            return
        with transaction.atomic():
            exams.delete()                      # cascades to versions, scans, grades
            if not opts["keep_banks"]:
                banks.delete()
        for name in files:                      # only after the database commit succeeded
            try:
                default_storage.delete(name)
            except OSError:
                self.stderr.write(f"Could not delete file {name}")
        self.stdout.write(self.style.SUCCESS(f"Deleted for {user.username}: {summary}."))