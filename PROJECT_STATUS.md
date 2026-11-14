# OncoSys Multimodal Case Room — Project Implementation Status

**Track:** Track 2 — Evidence Navigator  
**Product:** Multimodal Case Room  
**Target Dataset:** TCGA Breast Invasive Carcinoma (TCGA-BRCA)  
**Status:** MVP Fully Functional · 16/16 Unit Tests Passing · Demo-Ready

---

## 1. Executive Summary

In computational oncology and clinical data integration, AI models and data pipelines often make unsubstantiated claims or silently bridge gaps by borrowing clinical or molecular data from unrelated samples. The **OncoSys Multimodal Case Room** is an interactive evidence investigation workspace designed for research and review teams.

It allows reviewers to inspect individual cancer cases across clinical records, overall survival, genomic mutations, copy number variations, RNA expression, RPPA protein measurements, and whole-slide pathology images. Crucially, the workspace enforces **strict sample barcode provenance**, **refuses to impute or borrow unverified evidence**, audits case quality, and produces an **atomic, source-cited case brief** where every statement is traceable to an exact file and coordinate locator.

---

## 2. Completed Architecture & Modules

### A. Sample Catalog & Multimodal Ingestion (`src/data_loader.py`)
- **Dual Manifest Union**: Ingests and joins `sample_manifest.csv` and `slide_manifest.csv` to catalog all known TCGA-BRCA samples without dropping slide-only records.
- **Evidence Coverage Matrix**: Computes presence/absence flags across 6 key data layers (`in_clinical`, `has_survival`, `has_mutation`, `has_copy_number`, `has_rna`, `has_protein`).
- **Slide Accounting**: Differentiates between diagnostic pathology slides (`DX`) and tissue/frozen slides (`TS`), tracking slide counts per sample.
- **Search & Filter Pipeline**: Provides fast filtering by sample type (Primary Tumor `01`, Metastatic `06`, Normal Tissue `11`), required evidence coverage, and sample/patient ID query matching.

### B. Strict Evidence Linking Engine (`src/case_loader.py`)
- **Exact Barcode Matching**: Strictly links records using standard TCGA barcodes (`TCGA-XX-XXXX-XX`). If a sample barcode is missing in a molecular or clinical layer, the system explicitly reports it as absent rather than guessing or inheriting data from another sample of the same patient.
- **Cross-Layer Evidence Harmonization**:
  - **Clinical & Pathology Stage**: Pathologic stage, receptor statuses (ER, PR, HER2), PAM50 molecular subtype.
  - **Overall Survival**: Event status (vital status), time to event / days to last follow-up.
  - **Genomic Mutations**: Gene-level mutation profiles with focus on driver genes (`TP53`, `PIK3CA`, `BRCA1`, `BRCA2`, `ESR1`, `ERBB2`).
  - **Copy Number Alterations**: GISTIC2 discretized calls (`Deep deletion`, `Loss`, `Neutral`, `Gain`, `Amplification`).
  - **Transcriptomics (RNA-Seq)**: Normalized $\log_2(\text{norm\_count} + 1)$ expression for receptor and driver genes.
  - **Proteomics (RPPA)**: Normalized protein expression levels for ER-alpha, PR, and HER2.
  - **Pathology Slides**: Metadata and NCI Imaging Data Commons (IDC) interactive whole-slide viewer links.

### C. Case Data Quality & Discrepancy Auditor (`src/case_loader.py`)
- **Automated Data Auditing**: Evaluates case integrity on load and surfaces transparent warnings without mutating source files.
- **Identified Quality Checks**:
  - Validates barcode structure and sample type.
  - Detects missing clinical, molecular, or pathology layers.
  - Flags diagnostic slide absence for primary tumors.
  - Detects biological or clinical discrepancies (e.g. sample marked ER-positive clinically but ER-alpha protein level is non-positive or conflicting).
  - Explicitly flags slide-only cases that lack clinical annotation.

### D. Atomic Source-Cited Case Brief Engine (`src/case_brief.py`)
- **Atomic Evidence Statements**: Generates structured, sentence-level briefs where every single statement includes:
  - `topic`: Domain (Identity, Clinical, Survival, Proteomics, Genomics, RNA, Pathology, Quality).
  - `statement`: Plain-language factual assertion.
  - `source_file`: Specific data file (e.g., `clinical.tsv`, `survival.tsv`, `protein_rppa.tsv.gz`).
  - `locator`: Exact coordinate in the file (e.g., column name, row identifier, or case key).
  - `status`: Verification status (`verified`, `warning`, `missing`).
- **Markdown Export**: Formats the brief with markdown tables and direct hyperlinks to NCI IDC whole-slide viewers for instant download.

### E. Interactive Reviewer Workspace (`app.py`)
- **Streamlit Web Interface**:
  - Responsive catalog browser with paginated sample cards (24 per page).
  - Visual badge pills indicating availability of each evidence layer.
  - Deep-dive Case Room view with organized tabs for Clinical, Genomics & Transcriptomics, Proteomics, and Pathology.
  - Prominent "Data Quality & Provenance Warnings" alert container.
  - Interactive WSI Slide links that launch the NCI IDC viewer in a new tab.
  - "Download Case Brief (.md)" button for provenance-preserving review handoffs.

---

## 3. Unit Test & Validation Suite (`tests/`)

The repository includes a comprehensive, automated test suite with **16 unit tests** covering all critical invariants:

1. **Catalog Tests (`tests/test_data_loader.py`)**:
   - `test_catalog_keeps_union_of_sample_and_slide_manifests`: Verifies no sample is lost during manifest joining.
   - `test_filters_primary_tumors_with_protein_and_diagnostic_slide`: Tests composite filtering logic.
   - `test_complete_practice_case_has_expected_coverage`: Validates full coverage for clean practice cases.
   - `test_missing_data_practice_case_stays_visible`: Ensures cases with gaps remain discoverable.
   - `test_slide_only_practice_case_is_not_dropped`: Confirms slide-only records are kept in catalog.
   - `test_search_matches_patient_or_sample_id`: Verifies search index.

2. **Case Loader & Provenance Tests (`tests/test_case_loader.py`)**:
   - `test_complete_case_loads_exact_source_backed_details`: Tests exact multi-layer lookup.
   - `test_missing_protein_and_diagnostic_slide_are_explicit`: Verifies absent layers are explicitly flagged.
   - `test_slide_only_case_refuses_to_attach_other_records`: Invariant test proving no accidental cross-sample data pollution.
   - `test_unknown_sample_is_rejected`: Error handling for nonexistent barcodes.

3. **Case Brief & Citation Tests (`tests/test_case_brief.py`)**:
   - `test_complete_case_has_atomic_cited_statements_and_slide_links`: Validates presence of source and locator on all statements.
   - `test_missing_evidence_is_stated_and_quality_warning_is_preserved`: Tests warning preservation in export.
   - `test_slide_only_case_does_not_claim_a_clinical_record`: Tests truthful reporting for isolated records.

4. **App Integration Tests (`tests/test_app.py`)**:
   - `test_landing_page_defaults_to_primary_tumors`: Tests UI default initialization.
   - `test_search_and_open_missing_data_case`: Tests UI search, selection, and view transition.
   - `test_slide_only_case_is_searchable_when_normal_tissue_is_selected`: Tests edge-case navigation in UI.

**Test Run Result:**
```text
Ran 16 tests in ~6.8s — OK (ALL TESTS PASSING)
```

---

## 4. Benchmark Practice Cases

| Sample Barcode | Tissue Type | Status / Characteristics | Purpose in Demo |
|---|---|---|---|
| `TCGA-A7-A3RF-01` | Primary Tumor | Complete: All 6 data layers present + Diagnostic slide | Demonstrates full multimodal synthesis and viewer linking |
| `TCGA-BH-A8FY-01` | Primary Tumor | Partial: Missing RPPA protein and diagnostic slide | Demonstrates quality warnings and explicit absence reporting |
| `TCGA-A7-A56D-11` | Normal Tissue | Slide-Only: Only slides exist, no clinical/molecular record | Proves strict adherence to anti-hallucination / zero data borrowing |

---

## 5. Next Steps / Saturday In-Person Roadmap

- [ ] **Envelope Unsealing Workflow**: Add a UI component or CLI hook to load the unseen Saturday test envelopes (`envelopes/unseal.py`) directly into the Case Room.
- [ ] **Cohort Control Tower / Handoff Format**: Integrate JSON findings export adhering to `format/shared_findings_schema.json` v0.2 for cross-team interoperability.
- [ ] **Side-by-side Case Comparison**: Optional stretch view to compare primary tumor vs. normal tissue or paired cohorts.
