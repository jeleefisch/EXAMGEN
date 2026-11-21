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

# ExamGen progress (2026-11-20)

## Completed (tested on my machine)
- `core/` engine: combinatorics, similarity, feasibility (max-flow), shuffle, selection, generator, verifier
- Auth, dashboard, question banks, topics, questions (MC/TF) with ownership checks
- Exam and snapshot models (RESTRICT on Question.topic)
- Generation service `apps/exams/services.py` (atomic, verified, snapshot-based)
- Test suite: 83 passing

## D-010 PDFs can only be downloaded for finalized exams
Printed papers must always match the saved key. Drafts can still be regenerated, so they are not printable.

## D-011 Answer-sheet geometry lives in one file
`core/sheet_layout.py` is the only place bubble positions are defined. The PDF writer draws from it and the OMR reader will locate bubbles from it, so they cannot drift apart. QR payload is `EG1|<version code>|<sheet serial>|<crc16>`; the checksum detects damaged codes (manual entry is the fallback).

## D-012 PDF writers take plain dataclasses, not Django models
This keeps them testable without Django. `loaders.py` converts database rows into those dataclasses.

## D-013 Student copies: the answer sheet is the last page of each student's own paper
Suggested by the project owner. One PDF per version; each copy is the paper followed by a full-page answer sheet with that copy's QR code. The version code and sheet number are printed on every page, so faculty cannot mix up papers and sheets. Trade-offs: papers become consumable, and the sheet should be printed single-sided and photographed flat (or detached). The standalone paper and sheets downloads remain available.

## D-014 A fresh random seed for every generation
Each successful generation draws a new seed and stores it in `Exam.base_seed`, so "Regenerate" gives a different result. A failed generation keeps the old seed and saves nothing. The stored seed still lets any saved set of versions be reproduced. The seed is written with `.update()` so the exam is not marked stale.

## D-015 Reprints continue serial numbers
The answer-sheets PDF accepts `?start=N` so a reprint never reuses a sheet serial within a version. The "of N" total is shown only when numbering starts at 1.

D-016: a selected row with an erasure-like patch (a bubble more than 0.03 lighter than empty) is sent to manual review. The threshold is calibrated on one digital sample only.
D-017: the stale warning is not shown for finalized exams.

D-018: core/omr_reader.py and core/omr_erasure.py are copies of the spike files, so Django never imports spike/. Debt: the spike will later become a thin wrapper.
D-019: the upload is per exam. Reads are two-pass (QR first, then the version’s own layout). An unusable QR gives the manual version choice (D-002).
D-020: the machine reading (status, detected) is never overwritten. Human decisions go in resolved, and final prefers them.

D-021: grading uses the scan’s own version key and the snapshot points, and blank scores 0. It refuses unresolved sheets.
D-022: a grade is deleted when its scan is re-read or a resolution changes, so scores are never stale.
D-023: CSV text cells starting with = + - @ get a leading '.