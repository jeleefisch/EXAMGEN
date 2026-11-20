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

## D-006: Engine works on IDs and indexes, not text (2026-11-20)
**Status:** Accepted
**Decision:** `core/generation` receives questions as (id, topic, difficulty, type, choice count, correct index) and returns question IDs plus choice orders. The database layer builds the saved snapshot.
**Consequence:** Needs a translation step between ORM objects and engine objects.

## D-007: Greedy least-reuse-first selection with balanced allocation (2026-11-20)
**Status:** Accepted
**Decision:** Each version uses the lowest reuse level at which the configuration is feasible, with per-cell fair-share caps; optional retries when a similarity limit is set.
**Reason:** Simple, explainable, measurably low overlap (see tests). Not guaranteed optimal.
**Consequence:** If a proven minimum overlap is needed later, revisit with OR-Tools.