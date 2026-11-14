# OncoSys Hackathon Project Status

## Selected track and project

- **Track:** Track 2 — Evidence Navigator
- **Selected project:** Multimodal Case Room
- **Target user:** A research team reviewing individual cancer cases

We are building only the Multimodal Case Room. Evidence Copilot, Research Claim
Auditor and Repair Review Desk are different Track 2 project choices and are not
part of our application.

## Project goal

The user opens one tumor sample and sees its linked clinical, molecular and
pathology evidence in one place. The application must use exact sample IDs,
show missing or conflicting evidence and identify the source of every summary
statement.

The application organizes research evidence. It does not diagnose disease,
recommend treatment or create medical thresholds.

## Current workflow

1. Browse or search the sample catalog.
2. Open one sample using its exact sample ID.
3. Retrieve matching records from the clinical, survival, mutation,
   copy-number, RNA, protein and slide files.
4. Display which evidence is available and missing.
5. Run the Case Data Quality checks.
6. Create a source-cited Case Summary.
7. Open linked pathology slides in the NCI viewer.
8. Download the summary as a one-case Markdown brief.

## Completed work

### Sample catalog

- Displays sample cards from the sample and slide manifests.
- Shows patient ID, sample ID, sample type, available layers, missing layers and
  slide counts.
- Supports sample/patient search and filters for sample type, protein and
  slides.
- Keeps slide-only samples visible instead of dropping them during a join.

### Exact case linking

- Uses the exact tumor sample ID as the molecular-data linking key.
- Retrieves the matching clinical record.
- Retrieves the matching survival record.
- Retrieves the exact sample column from mutation, RNA, copy-number and protein
  matrices.
- Retrieves every slide row whose barcode belongs to that exact sample.
- Refuses to attach records from a nearby or similar sample.

### Case detail view

- Clinical stage, ER, PR, HER2 and PAM50 fields when available.
- Clinical and protein biomarker measurements displayed side by side.
- Mutation list and mutation count.
- Focused RNA and copy-number values.
- Survival fields.
- Pathology slide metadata and NCI viewer links.
- Missing-evidence and research-use limitations.

### Case Data Quality

The application currently runs ten groups of checks:

1. Sample-manifest link.
2. Unique clinical row.
3. Patient-ID consistency.
4. Exact molecular-column links.
5. Missing data layers.
6. Duplicate slide barcodes or viewer links.
7. Slide-to-patient consistency.
8. Diagnostic-slide availability.
9. Recognized ER, PR and HER2 categories.
10. Positive slide size and microscope objective values.

These checks report problems. They do not delete, merge or repair the source
files.

### Source-cited Case Summary

- Every opened sample has its own Case Summary at the top of the detail page.
- Fixed rules select identity, clinical biomarkers, mutation count, data-layer
  coverage, slide availability and quality results.
- Every statement names its source file and record locator.
- Slide statements preserve the external viewer links.
- Missing evidence and quality warnings appear in the summary.
- The application does not label raw RNA or protein values medically high or
  low without a validated threshold.

### Export

- The user can download a Markdown brief for the currently opened sample.
- The brief contains the summary, citations, record locators, slide links and
  the research-use boundary.
- It does not export the complete database.

### Judge Case Loader

- The catalog includes an **Open the judge-selected case** section.
- It accepts a `case_room_case.txt` upload containing one sample ID.
- It validates the TCGA sample-ID format and checks the loaded manifests.
- Invalid, multi-line and unknown sample IDs produce clear errors.
- A validated judge sample opens through the normal linking, quality, summary
  and export workflow.

### Conflict preservation and display

- All clinical rows matching the exact sample ID are retained with their
  original source-row numbers.
- Contradictory patient, stage, receptor or subtype values appear in a dedicated
  **Conflicting evidence** section.
- Cross-file inconsistencies from molecular headers, patient links and slide
  records also appear as conflicts.
- Conflicting fields are omitted from the ordinary summary statement instead
  of silently choosing the first value.
- Every conflicting value and its source row are included in the case brief.

### Testing and team materials

- **23 automated tests currently pass.**
- Tests cover the catalog, exact linking, complete case, missing-data case,
  slide-only case, quality checks, summary citations and export.
- A clean team-share ZIP has been created.
- A five-slide, three-minute judge presentation has been created.

## Required work remaining

### 1. AI-written brief with citation protection

The current summary is deterministic and source-cited. The official product
brief asks for an AI-written brief. A safe implementation should:

- Give the language model only verified statements produced by our rules.
- Require citation IDs for every generated sentence.
- Reject sentences with missing or unknown citations.
- Fall back to the deterministic summary when AI is unavailable or invalid.
- Prevent diagnosis, treatment advice and invented medical thresholds.

No API key should be committed to the repository.

### 2. Unseen-case rehearsal

- Open the public practice envelope.
- Load its `case_room_case.txt` through the same judge workflow.
- Test a complete case, a missing-layer case and a slide-only case.
- Confirm that the brief downloads with working viewer links.
- Time the complete workflow and keep it comfortably within the live demo.

### 3. Final documentation and demo polish

- Add screenshots and architecture notes to the main project README.
- Record the final installation and startup commands.
- Confirm the application starts on a clean teammate computer.
- Prepare a short recovery plan if the network or slide viewer is unavailable.

## Optional stretch features

These are useful only after the required work is reliable:

- Compare two cases side by side.
- Flag possible disagreement between recorded clinical receptor status and the
  corresponding protein evidence, using a documented interpretation rule.
- Export a formatted PDF in addition to Markdown.
- Add a visible evidence-provenance graph.

## Known limitations

- The current summary wording comes from fixed rules rather than a language
  model.
- The app does not diagnose or recommend treatment.
- Raw molecular values are displayed without invented clinical cutoffs.
- External pathology viewing depends on the NCI viewer link and network access.

## Useful demonstration cases

- `TCGA-A7-A3RF-01` — complete case with all six data layers and a diagnostic
  slide.
- `TCGA-BH-A8FY-01` — protein missing and no diagnostic slide.
- `TCGA-A7-A56D-11` — slide-only record; the app refuses to borrow clinical or
  molecular evidence from another sample.

## Run the application

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Run the tests

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

## Recommended implementation order

1. Citation-protected AI wording with deterministic fallback.
2. Practice-envelope and unseen-case rehearsal.
3. Final README, demo rehearsal and deployment check.
4. Stretch work only if the required workflow remains stable.
