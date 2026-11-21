# ExamGen

Generates multiple versions of an exam from a question bank, prints answer sheets with a QR code
and corner markers, reads phone photos of filled sheets, and grades each sheet against the key of
its own version. Built with Django 5.2 and OpenCV.

## What it does

1. **Banks**: keep questions by topic and difficulty (multiple choice and true/false).
2. **Exams**: set size, difficulty mix and number of versions; the engine builds the versions
   with shuffled questions and choices.
3. **Documents**: generate printable exam papers and answer sheets.
4. **Scans**: upload photos of filled sheets. The reader finds the corner markers, reads the QR
   code (version and sheet serial), and measures every bubble.
5. **Review**: any uncertain item (faint, double, erased) goes to a person. Nothing is guessed.
6. **Grading**: a sheet is graded only when every item is resolved. The results page shows
   graded count, mean, highest, lowest, ready and needs-review counts, and a CSV download.

## Run locally (Windows / PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Tests: `python manage.py test` (184 tests at the time of writing, about 2.5 minutes).

## Managing data

- **Delete** a question bank or a question from its list page (a confirmation page comes first).
  Deleting a bank keeps its exams. Exams hold their own copy of each question, so they are not
  affected by deleting or editing bank questions.
- **Profile** (`/accounts/profile/`): edit your name and email.
- **Results search**: filter the results table by student name, version code, or sheet number.
- **Remove a user's data** (administrator, command line):

```powershell
python manage.py purge_user_data USERNAME            # dry run: lists what would be deleted
python manage.py purge_user_data USERNAME --yes      # actually deletes
python manage.py purge_user_data USERNAME --yes --keep-banks
```

The account itself is never deleted. Uploaded files are removed only after the database
changes are committed.

## Deploy

Production settings are in `config/settings/prod.py` and read environment variables
(see `.env.example`).

```powershell
pip install -r requirements-prod.txt
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Put that output in `DJANGO_SECRET_KEY`, then on the server:

```
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
gunicorn config.wsgi:application
```

`DJANGO_SETTINGS_MODULE` must be `config.settings.prod`. Without it, `wsgi.py` falls back to the
development settings. Keep the database and `media/` folder (uploaded scan photos) on a persistent
disk, and back them up.

With prod settings, HTTPS redirect and HSTS are on by default. To test prod settings locally over
plain HTTP, set `DJANGO_SSL_REDIRECT=false` for that session only, and remove it afterwards.
Leaving it set will make `check --deploy` report warnings even though `prod.py` is correct.

## Accuracy

See `docs/ACCURACY.md`. All measured figures are digital/synthetic. Real printed-paper accuracy
has not been measured.

## Project layout

`apps/` Django apps (accounts, banks, exams, documents, omr, grading, reports) |
`core/` engine (generation, similarity, sheet layout, OMR reader, benchmark) |
`spike/` synthetic sheet and photo generator used by tests and the benchmark.