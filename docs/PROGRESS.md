# ExamGen progress (2026-11-21)

## Completed (tested on my machine)
- core/ engine: combinatorics, similarity, feasibility (max-flow), shuffle, selection, generator, verifier
- Auth, dashboard, question banks, topics, questions (MC/TF), ownership checks
- Exam models, generation service (atomic, snapshots, fresh seed per generation)
- Exam UI: configure, feasibility rejection, generate, finalize, version preview
- PDFs: exam paper, answer key, answer sheets, student copies (paper + sheet) - download views and tests
- Sheet layout geometry + to_pixel mapping + QR payload with checksum
- Test suite: 136 passing (before the booklet.py font sync; re-run pending)

# ExamGen progress (2026-11-21)

## Completed (tested on my machine; 184 tests passing)
- core/ engine: combinatorics, similarity, feasibility (max-flow), shuffle, selection, generator, verifier
- Auth, dashboard, question banks, topics, questions (MC/TF), ownership checks
- Bank and question delete (confirm page, POST only, owner-checked); profile page
- Exam models, generation service (atomic, snapshots, fresh seed per generation)
- Exam UI: configure, feasibility rejection, generate, finalize, version preview
- PDFs: exam paper, answer key, answer sheets, student copies
- Sheet layout geometry, QR payload with checksum
- OMR reader (corner markers, QR, bubble measurement); uncertain items go to manual review
- Grading against each sheet's own version key; results page with statistics, search, CSV
- Production settings (env-driven), `check --deploy` clean except HSTS subdomains/preload
- `purge_user_data` management command (dry run by default)
- README, USER_GUIDE, ACCURACY docs

## Verified in the browser (2026-11-21)
- Create bank/topic/questions, edit question, delete bank, exam create/generate/finalize,
  answer key matches bank (checked by hand), documents page, profile

## Implemented, unverified
- Inactive filter on the Questions page (renders, not checked with real data)
- Cancel button on delete confirm pages

## Not done
- A real printed-and-photographed sheet. All accuracy figures are digital/synthetic.
- Student roster mapped to the QR serial
- Text search on the Questions page; topic dropdown on the Questions page
- Not confirmed: live feasibility while typing, DejaVu fonts
- CSV import, UI polish