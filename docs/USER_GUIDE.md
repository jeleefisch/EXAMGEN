# ExamGen teacher guide

## 1. Before exam day
1. Sign in. Add questions to a bank (multiple choice or true/false, with topic and difficulty).
2. Create an exam: title, number of questions, difficulty mix, number of versions.
3. Generate the versions and **finalize** the exam. Scanning and grading only work on a
   finalized exam.
4. Print the exam papers and answer sheets (Documents). Each answer sheet carries a QR code
   that identifies its version and sheet number.

## 2. Telling students how to mark
- Shade one bubble per item, fully and darkly. Use a dark pencil or pen.
- To change an answer, erase cleanly. A visible smudge or white-out beside a mark sends the
  item to review.
- Do not mark two bubbles in one item.
- Do not write over the corner squares or the QR code.

## 3. Taking photos
- Lay the sheet flat in even light. Avoid shadows across the page.
- All four black corner squares must be visible. The photo may be tilted or rotated.
- Use JPEG or PNG. HEIC is not supported. Maximum 15 MB per photo, 40 photos per upload.

## 4. Uploading and reviewing
1. Open the exam, then **Scanned sheets**, then upload.
2. The app reads each sheet. Statuses:
   - **Read**: version found.
   - **Needs version**: the QR could not be read. Choose the version (and sheet number) by hand.
   - **Unreadable**: retake the photo.
3. Open a sheet to see what was read. Items that are faint, double-marked, or near an erasure
   are listed for review. Choose the answer (a letter, or "-" for blank) and save.
4. Changing a decision on a sheet removes its existing grade. Grade it again.

## 5. Grading and results
1. Open **Results** for the exam and press **Grade all ready sheets**. Sheets still needing
   review are skipped and counted under "Needs review".
2. Each sheet is graded against the answer key of its own version.
3. Open **Details** to see per-item answers and add the student's name.
4. Use the **search box** above the results table to find a sheet by student name, version
   code, or sheet number. The tiles always cover all sheets, not just the filtered rows.
5. The tiles show graded count, mean, highest, lowest (all as percentages, because versions can
   have different maximum scores), ready-to-grade and needs-review counts.
6. **Download CSV** for a spreadsheet. Names beginning with `=`, `+`, `-` or `@` are saved with
   a leading apostrophe so spreadsheets do not run them as formulas.

## 6. Good to know
- The reader never guesses. Uncertain items always wait for you.
- Re-uploading or re-reading a sheet clears its grade.
- Accuracy figures are digital/synthetic only; see `docs/ACCURACY.md`. Spot-check some real
  sheets before relying on results.

## 7. Your account and your data
- **Profile**: open Profile in the sidebar to change your name and email.
- **Deleting a question or bank**: use Delete on the list page and confirm. Exams you already
  created keep their own copy of every question, so they and their graded sheets are unchanged.
- **Removing all of someone's data** is done by the administrator with `purge_user_data`
  (see the README). It shows what it would delete first, and deletes nothing without `--yes`.