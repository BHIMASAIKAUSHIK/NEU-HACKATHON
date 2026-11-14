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

- Generates and downloads a one-case Markdown brief (`<SAMPLE_ID>_case_brief.md`).
- Preserves all atomic source citations, table/field locators, and external NCI IDC slide viewer links.
- Includes data quality warnings directly in the export for auditability.

---

## Verification & automated testing

The test suite contains 16 automated unit tests passing across all critical components:
- `tests/test_data_loader.py`: Catalog union, filtering, search, and edge-case retention.
- `tests/test_case_loader.py`: Exact barcode matching, zero-borrowing guarantee, rejection of unknown IDs.
- `tests/test_case_brief.py`: Rule-based statement generation, citation locator integrity, slide URL preservation.
- `tests/test_app.py`: UI state, landing page filtering, case selection, and navigation.

```text
Ran 16 tests in ~6.8s — OK (ALL TESTS PASSING)
```

---

## Demo practice cases

- **`TCGA-A7-A3RF-01`**: Complete case with all 6 molecular/clinical layers and diagnostic slides.
- **`TCGA-BH-A8FY-01`**: Missing protein and diagnostic slide; demonstrates explicit missing-evidence warnings.
- **`TCGA-A7-A56D-11`**: Slide-only record; demonstrates that the app strictly refuses to borrow clinical/molecular data from other samples.
