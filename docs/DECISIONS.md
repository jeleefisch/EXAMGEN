# ExamGen Architectural Decision Log

Format: each entry records what we decided, why, and what it costs us.

## D-001: Modular monolith (2026-11-20)
**Status:** Accepted
**Decision:** One Django project split into focused apps (accounts, banks, exams, documents, omr, grading, reports). No microservices.
**Reason:** Simpler to build, run, test, and explain. The project does not need distributed architecture.
**Consequence:** All modules share one database and one deployment. Boundaries are kept by convention, not by the network.

## D-002: QR code on each answer sheet for identification (2026-11-20)
**Status:** Accepted
**Decision:** Each printed answer sheet carries a QR code encoding the exam, version, and student assignment. We do not OCR handwritten names.
**Reason:** Guarantees each sheet is graded with its own version's answer key. QR decoding is reliable and built into OpenCV.
**Consequence:** Sheets must be generated per student or per version before the exam. A damaged QR code needs a manual-entry fallback.

## D-003: Django 5.2 LTS on Python 3.14 (2026-11-20)
**Status:** Accepted (OpenCV/NumPy compatibility with 3.14 to be verified in Phase 5)
**Decision:** Use Django 5.2 LTS, which supports Python 3.14 as of 5.2.8.
**Reason:** Long-term security support suits a thesis project.
**Consequence:** If OpenCV fails to install on 3.14, we recreate the environment on Python 3.13.

## D-004: Algorithms in a Django-free `core/` package (2026-11-20)
**Status:** Accepted
**Decision:** Generation, similarity, combinatorics, and OMR logic live in `core/` with no Django imports. Apps call into `core/`.
**Reason:** Pure functions are easy to unit-test and to describe mathematically.
**Consequence:** A small amount of translation code is needed between ORM objects and plain data.

## D-005: Split settings (base/dev/prod) (2026-11-20)
**Status:** Accepted
**Decision:** `config/settings/base.py` holds shared settings, `dev.py` the development overrides. `prod.py` comes in Phase 8.
**Consequence:** `SECRET_KEY` currently sits in `base.py`. It must move to an environment variable before any deployment.

## D-006 The engine works on IDs and indexes, not text
The core engine never sees question text. The database layer builds snapshots from `question_id` and `choice_order`. This keeps the engine small, testable, and Django-free.

## D-007 Greedy least-reuse-first selection with balanced allocation
Measured, not proven optimal. Reduced overlap from about 12% to about 0 for 3 versions on a 72-question bank. OR-Tools is a possible later upgrade.

## D-008 Exams hold snapshots, not live links
`Exam.bank` is SET_NULL, topic requirements store names, and version codes are globally unique. Editing or deleting a bank never changes an existing exam or its answer key.

## D-009 Generation is all-or-nothing
`generate_exam_versions` computes everything first, then writes inside one `transaction.atomic()`. Any failure rolls back, so an exam never ends up with half its versions.