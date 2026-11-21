# OMR accuracy (digital/synthetic only)

**Every figure here comes from rendered sheets with simulated camera effects (tilt, rotation,
uneven light, noise, blur). Nothing was measured on printed, hand-marked paper.** Real-paper
accuracy is unknown until real sheets are tested.

Reproduce: `python -m core.benchmark --sheets 10 --seed 1 --markdown`

Mark mix per item: 60% solid, 15% faint, 10% double, 15% blank. Item counts per sheet: 10 to 50.

| condition | sheets | unreadable | crashed | items | correct | flagged | confident wrong | QR not read | ID wrong |
|---|---|---|---|---|---|---|---|---|---|
| mild | 10 | 0 | 0 | 325 | 273 (84.0%) | 52 | 0 | 0 | 0 |
| moderate | 10 | 0 | 0 | 355 | 314 (88.5%) | 41 | 0 | 0 | 0 |
| harsh | 10 | 3 | 0 | 244 | 201 (82.4%) | 43 | 0 | 7 | 0 |
| TOTAL | 30 | 3 | 0 | 924 | 788 (85.3%) | 136 | 0 | 7 | 0 |

## How to read it

- **Confident wrong (0 of 924)** is the headline: a wrong answer the reader did not flag.
  This is the error that would silently change a grade.
- **Correct is not an accuracy rate.** The mix deliberately includes faint and double marks,
  which the reader is designed to send to review. Flagged items (136 of 924, 14.7%) are
  the system working as intended: a person decides them.
- **Unreadable (3 of 30 harsh sheets)** were refused with a "retake the photo" message.
- **QR not read (7, all in the harsh condition)**: the app asks the teacher to choose the
  version by hand. **ID wrong is 0**: no sheet was assigned a wrong version or serial.

## Other synthetic results

- End-to-end test (`apps/grading/tests_accuracy.py`): 12 simulated students on 3 versions with
  clean single marks. 12 of 12 identified, 120 of 120 items read correctly, 0 wrong scores.

## Limits

One seed, 10 sheets per condition, clean pencil-like marks drawn by software. Real paper adds
smudges, pen types, creases, shadows and phone-camera behavior that are not modeled.
Treat these numbers as a regression check for the software, not a promise for classroom use.
Test with real printed sheets before relying on it.