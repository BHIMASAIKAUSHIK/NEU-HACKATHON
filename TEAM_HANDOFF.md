# OncoSys Multimodal Case Room — Team Handoff

This package contains the current Track 2 application, its tests, and the
TCGA-BRCA files needed for the current demo.

## Run the app

From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open `http://localhost:8501` if it does not open automatically.

## Run the tests

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

The current suite contains 16 tests covering the catalog, exact case linking,
quality checks, source-cited brief, export, missing-data case, and slide-only
case.

## What is implemented

- Searchable sample-card catalog with evidence coverage and slide counts.
- Exact sample-ID linking across clinical, survival, mutation, copy-number,
  RNA, protein, and slide files.
- Case Data Quality checks that report missing, duplicate, inconsistent, or
  implausible records without modifying the source data.
- A rule-based Case Summary where every statement has a source and locator.
- Pathology viewer links and a downloadable one-case Markdown brief.

## Useful demo cases

- `TCGA-A7-A3RF-01`: complete case with all six layers and a diagnostic slide.
- `TCGA-BH-A8FY-01`: missing protein and diagnostic slide; warnings are visible.
- `TCGA-A7-A56D-11`: slide-only record; the app refuses to borrow another
  sample's clinical or molecular evidence.

## Research-use boundary

This prototype organizes evidence. It does not diagnose disease, recommend
treatment, create clinical cutoffs, or claim that raw RNA/protein values are
medically high or low.

## Remaining major work

The app still needs a user-facing way to switch its data source to an opened
judge envelope/release folder for the unseen-case demonstration.
