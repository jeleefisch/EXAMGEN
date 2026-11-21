# ExamGen progress (2026-11-21)

## Completed (tested on my machine)
- core/ engine: combinatorics, similarity, feasibility (max-flow), shuffle, selection, generator, verifier
- Auth, dashboard, question banks, topics, questions (MC/TF), ownership checks
- Exam models, generation service (atomic, snapshots, fresh seed per generation)
- Exam UI: configure, feasibility rejection, generate, finalize, version preview
- PDFs: exam paper, answer key, answer sheets, student copies (paper + sheet) - download views and tests
- Sheet layout geometry + to_pixel mapping + QR payload with checksum
- Test suite: 136 passing (before the booklet.py font sync; re-run pending)

## Implemented, unverified
- booklet.py synced with pdf.py styles/fonts (not yet re-run)
- Browser walkthrough and a real printed sheet (not yet checked)

## Planned
- Phase 4.5: OMR feasibility spike (OpenCV/NumPy on Python 3.14 unchecked)
- Phase 5: OMR module; Phase 6: grading + manual review; Phase 7: reports, metrics; Phase 8: deployment, docs
- Gaps: delete UI for banks/questions, question search, profile page, student roster, live feasibility, DejaVu fonts