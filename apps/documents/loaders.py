"""Convert database rows into the plain dataclasses the PDF writers use."""
from django.db.models import Prefetch

from apps.exams.models import VersionChoice

from . import pdf


def exam_doc(exam):
    return pdf.ExamDoc(
        title=exam.title,
        subject=exam.subject or "",
        institution=exam.institution_name or "",
        points_per_question=float(exam.points_per_question),
    )


def version_doc(version):
    items = version.items.order_by("position").prefetch_related(
        Prefetch("choices", queryset=VersionChoice.objects.order_by("display_label"))
    )
    return pdf.VersionDoc(
        code=version.code,
        items=[
            pdf.ItemDoc(
                text=i.text,
                qtype=i.qtype,
                correct_label=i.correct_label,
                choices=[pdf.ChoiceDoc(c.display_label, c.text) for c in i.choices.all()],
            )
            for i in items
        ],
    )