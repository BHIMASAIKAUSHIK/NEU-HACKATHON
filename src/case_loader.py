"""Load source-backed details for one exact TCGA sample barcode."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.data_loader import PROJECT_ROOT, load_sample_catalog


RAW_DIR = PROJECT_ROOT / "data" / "tcga-brca" / "raw"
CLINICAL_FILE = RAW_DIR / "clinical.tsv"
SURVIVAL_FILE = RAW_DIR / "survival.tsv"
PROTEIN_FILE = RAW_DIR / "protein_rppa.tsv.gz"
MUTATION_FILE = RAW_DIR / "mutation_gene_level.tsv.gz"
COPY_NUMBER_FILE = RAW_DIR / "copy_number_gistic.tsv.gz"
RNA_FILE = RAW_DIR / "rna_hiseq.tsv.gz"
SLIDE_FILE = PROJECT_ROOT / "data" / "tcga-brca" / "slide_manifest.csv"

CLINICAL_FIELDS = {
    "pathologic_stage": "Pathologic stage",
    "breast_carcinoma_estrogen_receptor_status": "ER clinical status",
    "breast_carcinoma_progesterone_receptor_status": "PR clinical status",
    "lab_proc_her2_neu_immunohistochemistry_receptor_status": "HER2 clinical status",
    "PAM50Call_RNAseq": "PAM50 RNA subtype",
}

PROTEIN_ROWS = {
    "ERALPHA": "ER-alpha",
    "PR": "PR",
    "HER2": "HER2",
}

FOCUS_GENES = ("ESR1", "PGR", "ERBB2", "TP53", "BRCA1", "BRCA2")

COPY_NUMBER_LABELS = {
    -2: "Deep deletion",
    -1: "Loss",
    0: "Neutral",
    1: "Gain",
    2: "Amplification",
}

RECEPTOR_VALUES = {
    "ER clinical status": {"Positive", "Negative", "Indeterminate"},
    "PR clinical status": {"Positive", "Negative", "Indeterminate"},
    "HER2 clinical status": {"Positive", "Negative", "Equivocal", "Indeterminate"},
}


def _clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return round(value, 4)
    return value


def _read_sample_matrix(
    path: Path,
    sample_id: str,
    *,
    index_column: str,
) -> pd.Series | None:
    """Read one exact sample column from a wide matrix, if it exists."""

    if not path.exists():
        return None
    columns = pd.read_csv(path, sep="\t", nrows=0).columns
    if sample_id not in columns:
        return None
    frame = pd.read_csv(path, sep="\t", usecols=[index_column, sample_id])
    return frame.set_index(index_column)[sample_id]


def _load_clinical(sample_id: str) -> dict[str, Any] | None:
    if not CLINICAL_FILE.exists():
        return None
    clinical = pd.read_csv(CLINICAL_FILE, sep="\t", low_memory=False)
    if "sampleID" not in clinical.columns:
        raise ValueError("clinical.tsv is missing the sampleID column")
    rows = clinical[clinical["sampleID"].eq(sample_id)]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return {label: _clean_value(row.get(column)) for column, label in CLINICAL_FIELDS.items()}


def _load_survival(sample_id: str, patient_id: str | None) -> dict[str, Any] | None:
    if not SURVIVAL_FILE.exists():
        return None
    survival = pd.read_csv(SURVIVAL_FILE, sep="\t", low_memory=False)
    rows = survival[survival.get("sample", pd.Series(dtype=str)).eq(sample_id)]
    if rows.empty and patient_id and "_PATIENT" in survival.columns:
        rows = survival[survival["_PATIENT"].eq(patient_id)]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return {
        "Overall survival event": _clean_value(row.get("OS")),
        "Overall survival time (days)": _clean_value(row.get("OS.time")),
        "Disease-specific survival event": _clean_value(row.get("DSS")),
        "Disease-specific survival time (days)": _clean_value(row.get("DSS.time")),
    }


def _load_protein(sample_id: str) -> dict[str, Any] | None:
    series = _read_sample_matrix(PROTEIN_FILE, sample_id, index_column="Sample_description")
    if series is None:
        return None
    return {
        label: _clean_value(series.get(source_row))
        for source_row, label in PROTEIN_ROWS.items()
    }


def _load_mutations(sample_id: str) -> list[dict[str, Any]] | None:
    series = _read_sample_matrix(MUTATION_FILE, sample_id, index_column="sample")
    if series is None:
        return None
    mutated = series[series.fillna(0).ne(0)]
    return [
        {"gene": str(gene), "source_value": _clean_value(value)}
        for gene, value in mutated.items()
    ]


def _load_copy_number(sample_id: str) -> list[dict[str, Any]] | None:
    series = _read_sample_matrix(COPY_NUMBER_FILE, sample_id, index_column="Gene Symbol")
    if series is None:
        return None
    records = []
    for gene in FOCUS_GENES:
        value = _clean_value(series.get(gene))
        label = COPY_NUMBER_LABELS.get(value, "Unavailable" if value is None else "Other")
        records.append({"gene": gene, "value": value, "interpretation": label})
    return records


def _load_rna(sample_id: str) -> list[dict[str, Any]] | None:
    series = _read_sample_matrix(RNA_FILE, sample_id, index_column="sample")
    if series is None:
        return None
    return [
        {"gene": gene, "expression": _clean_value(series.get(gene))}
        for gene in FOCUS_GENES
    ]


def _load_slides(sample_id: str) -> list[dict[str, Any]]:
    slides = pd.read_csv(SLIDE_FILE, dtype={"sample_id": "string"})
    rows = slides[slides["sample_id"].eq(sample_id)]
    result = []
    for _, row in rows.iterrows():
        result.append(
            {
                "slide_barcode": _clean_value(row.get("slide_barcode")),
                "slide_kind": _clean_value(row.get("slide_kind")),
                "objective": _clean_value(row.get("objective")),
                "size_mb": _clean_value(row.get("size_mb")),
                "viewer_url": _clean_value(row.get("viewer_url")),
                "license": _clean_value(row.get("license")),
            }
        )
    return result


def _quality_check(
    check_id: str,
    status: str,
    title: str,
    detail: str,
    source: str,
) -> dict[str, str]:
    return {
        "id": check_id,
        "status": status,
        "title": title,
        "detail": detail,
        "source": source,
    }


def _matrix_column_count(path: Path, sample_id: str) -> int:
    if not path.exists():
        return 0
    return list(pd.read_csv(path, sep="\t", nrows=0).columns).count(sample_id)


def run_case_quality_checks(case: dict[str, Any]) -> list[dict[str, str]]:
    """Run transparent, non-clinical integrity checks for one linked case."""

    sample_id = case["sample_id"]
    patient_id = case["patient_id"]
    checks: list[dict[str, str]] = []

    if case["record_status"] == "Linked record":
        checks.append(
            _quality_check(
                "manifest-link",
                "pass",
                "Sample manifest link",
                "The exact sample ID has one catalogued clinical/molecular record.",
                "data/tcga-brca/sample_manifest.csv",
            )
        )
    else:
        checks.append(
            _quality_check(
                "manifest-link",
                "warning",
                "Slide-only record",
                "Slides match this sample ID, but the sample manifest has no clinical/molecular record.",
                "data/tcga-brca/sample_manifest.csv",
            )
        )

    clinical = pd.read_csv(CLINICAL_FILE, sep="\t", low_memory=False)
    clinical_rows = clinical[clinical["sampleID"].eq(sample_id)]
    if len(clinical_rows) == 1:
        checks.append(
            _quality_check(
                "clinical-row-count",
                "pass",
                "Unique clinical row",
                "Exactly one clinical row matches the sample ID.",
                "data/tcga-brca/raw/clinical.tsv",
            )
        )
        clinical_patient = _clean_value(clinical_rows.iloc[0].get("_PATIENT"))
        if clinical_patient == patient_id:
            checks.append(
                _quality_check(
                    "patient-consistency",
                    "pass",
                    "Patient ID consistency",
                    "The clinical patient ID matches the patient ID in the sample catalog.",
                    "clinical.tsv + sample_manifest.csv",
                )
            )
        elif clinical_patient is None:
            checks.append(
                _quality_check(
                    "patient-consistency",
                    "warning",
                    "Patient ID unavailable",
                    "The clinical row does not provide a patient ID to compare.",
                    "data/tcga-brca/raw/clinical.tsv",
                )
            )
        else:
            checks.append(
                _quality_check(
                    "patient-consistency",
                    "error",
                    "Patient ID mismatch",
                    f"Catalog patient {patient_id} does not match clinical patient {clinical_patient}.",
                    "clinical.tsv + sample_manifest.csv",
                )
            )
    elif len(clinical_rows) == 0:
        checks.append(
            _quality_check(
                "clinical-row-count",
                "warning",
                "Clinical row missing",
                "No clinical row matches this exact sample ID.",
                "data/tcga-brca/raw/clinical.tsv",
            )
        )
    else:
        checks.append(
            _quality_check(
                "clinical-row-count",
                "error",
                "Duplicate clinical rows",
                f"{len(clinical_rows)} clinical rows use the same sample ID; one was expected.",
                "data/tcga-brca/raw/clinical.tsv",
            )
        )

    matrix_specs = {
        "mutation": (MUTATION_FILE, "mutation_gene_level.tsv.gz"),
        "copy_number": (COPY_NUMBER_FILE, "copy_number_gistic.tsv.gz"),
        "rna": (RNA_FILE, "rna_hiseq.tsv.gz"),
        "protein": (PROTEIN_FILE, "protein_rppa.tsv.gz"),
    }
    matrix_problems = []
    linked_columns = 0
    for layer, (path, filename) in matrix_specs.items():
        count = _matrix_column_count(path, sample_id)
        expected = case["availability"][layer]
        if count == 1:
            linked_columns += 1
        if count > 1:
            matrix_problems.append(f"{filename} contains {count} columns with this sample ID")
        elif expected and count == 0:
            matrix_problems.append(f"manifest says {layer} is available, but {filename} has no column")
        elif not expected and count == 1:
            matrix_problems.append(f"manifest says {layer} is missing, but {filename} contains a column")
    if matrix_problems:
        checks.append(
            _quality_check(
                "molecular-column-links",
                "error",
                "Molecular column inconsistency",
                "; ".join(matrix_problems) + ".",
                "sample_manifest.csv + molecular matrix headers",
            )
        )
    else:
        checks.append(
            _quality_check(
                "molecular-column-links",
                "pass",
                "Molecular column links",
                f"Manifest availability agrees with all matrix headers; {linked_columns} exact columns found.",
                "sample_manifest.csv + molecular matrix headers",
            )
        )

    missing_layers = [
        layer.replace("_", " ").title()
        for layer in ("clinical", "survival", "mutation", "copy_number", "rna", "protein")
        if not case["availability"][layer]
    ]
    if missing_layers:
        checks.append(
            _quality_check(
                "missing-layers",
                "warning",
                "Missing data layers",
                "Unavailable for this case: " + ", ".join(missing_layers) + ".",
                "data/tcga-brca/sample_manifest.csv",
            )
        )
    else:
        checks.append(
            _quality_check(
                "missing-layers",
                "pass",
                "Complete catalogued coverage",
                "All six catalogued clinical/molecular data layers are available.",
                "data/tcga-brca/sample_manifest.csv",
            )
        )

    slides = case["slides"]
    slide_barcodes = [slide["slide_barcode"] for slide in slides if slide["slide_barcode"]]
    viewer_urls = [slide["viewer_url"] for slide in slides if slide["viewer_url"]]
    duplicate_barcodes = sorted({value for value in slide_barcodes if slide_barcodes.count(value) > 1})
    duplicate_urls = sorted({value for value in viewer_urls if viewer_urls.count(value) > 1})
    if duplicate_barcodes or duplicate_urls:
        detail_parts = []
        if duplicate_barcodes:
            detail_parts.append(f"duplicate barcodes: {', '.join(duplicate_barcodes)}")
        if duplicate_urls:
            detail_parts.append(f"{len(duplicate_urls)} repeated viewer URL(s)")
        checks.append(
            _quality_check(
                "slide-duplicates",
                "error",
                "Duplicate slide records",
                "; ".join(detail_parts) + ".",
                "data/tcga-brca/slide_manifest.csv",
            )
        )
    else:
        checks.append(
            _quality_check(
                "slide-duplicates",
                "pass",
                "Unique slide records",
                f"No duplicate barcode or viewer URL was found across {len(slides)} linked slide(s).",
                "data/tcga-brca/slide_manifest.csv",
            )
        )

    slide_manifest = pd.read_csv(SLIDE_FILE, dtype={"sample_id": "string", "patient_id": "string"})
    linked_slide_rows = slide_manifest[slide_manifest["sample_id"].eq(sample_id)]
    slide_patient_ids = set(linked_slide_rows["patient_id"].dropna().astype(str))
    if slide_patient_ids and slide_patient_ids == {patient_id}:
        checks.append(
            _quality_check(
                "slide-patient-link",
                "pass",
                "Slide-to-patient link",
                "Every linked slide carries the same patient ID as the selected sample.",
                "slide_manifest.csv + sample_manifest.csv",
            )
        )
    elif slide_patient_ids:
        checks.append(
            _quality_check(
                "slide-patient-link",
                "error",
                "Slide patient mismatch",
                f"Slide patient ID(s) {sorted(slide_patient_ids)} do not match {patient_id}.",
                "slide_manifest.csv + sample_manifest.csv",
            )
        )
    else:
        checks.append(
            _quality_check(
                "slide-patient-link",
                "warning",
                "No slide-to-patient link",
                "No slide record is available to verify the patient link.",
                "data/tcga-brca/slide_manifest.csv",
            )
        )

    if case["availability"]["diagnostic_slide"]:
        checks.append(
            _quality_check(
                "diagnostic-slide",
                "pass",
                "Diagnostic slide available",
                "At least one linked slide is labelled diagnostic (FFPE).",
                "data/tcga-brca/slide_manifest.csv",
            )
        )
    else:
        checks.append(
            _quality_check(
                "diagnostic-slide",
                "warning",
                "Diagnostic slide missing",
                "No linked slide is labelled diagnostic; frozen slides are not substituted.",
                "data/tcga-brca/slide_manifest.csv",
            )
        )

    category_problems = []
    clinical_values = case["clinical"] or {}
    for label, allowed in RECEPTOR_VALUES.items():
        value = clinical_values.get(label)
        if value is not None and value not in allowed:
            category_problems.append(f"{label} has unexpected value {value!r}")
    if category_problems:
        checks.append(
            _quality_check(
                "clinical-categories",
                "warning",
                "Unexpected clinical category",
                "; ".join(category_problems) + ".",
                "data/tcga-brca/raw/clinical.tsv",
            )
        )
    elif case["clinical"]:
        checks.append(
            _quality_check(
                "clinical-categories",
                "pass",
                "Recognized receptor categories",
                "Available ER, PR and HER2 statuses use categories observed in the frozen release.",
                "data/tcga-brca/raw/clinical.tsv",
            )
        )

    invalid_slide_values = [
        slide["slide_barcode"]
        for slide in slides
        if (slide["size_mb"] is not None and slide["size_mb"] <= 0)
        or (slide["objective"] is not None and slide["objective"] <= 0)
    ]
    if invalid_slide_values:
        checks.append(
            _quality_check(
                "slide-values",
                "error",
                "Impossible slide value",
                "Non-positive size or objective found for: " + ", ".join(invalid_slide_values) + ".",
                "data/tcga-brca/slide_manifest.csv",
            )
        )
    elif slides:
        checks.append(
            _quality_check(
                "slide-values",
                "pass",
                "Plausible slide metadata",
                "All available slide sizes and objective values are positive.",
                "data/tcga-brca/slide_manifest.csv",
            )
        )

    return checks


def load_case_details(sample_id: str, *, include_large_layers: bool = True) -> dict[str, Any]:
    """Load a case using only exact sample barcode matches.

    `include_large_layers=False` is useful for quick checks that do not need the
    mutation, copy-number and RNA matrices.
    """

    catalog = load_sample_catalog()
    rows = catalog[catalog["sample_id"].eq(sample_id)]
    if rows.empty:
        raise KeyError(f"Sample is not present in either manifest: {sample_id}")
    row = rows.iloc[0]

    details: dict[str, Any] = {
        "sample_id": sample_id,
        "patient_id": _clean_value(row["patient_id"]),
        "sample_type": _clean_value(row["sample_type"]),
        "record_status": _clean_value(row["record_status"]),
        "availability": {
            "clinical": bool(row["in_clinical"]),
            "survival": bool(row["has_survival"]),
            "mutation": bool(row["has_mutation"]),
            "copy_number": bool(row["has_copy_number"]),
            "rna": bool(row["has_rna"]),
            "protein": bool(row["has_protein"]),
            "slides": bool(row["has_any_slide"]),
            "diagnostic_slide": bool(row["has_diagnostic_slide"]),
        },
        "clinical": _load_clinical(sample_id),
        "survival": _load_survival(sample_id, _clean_value(row["patient_id"])),
        "protein": _load_protein(sample_id),
        "slides": _load_slides(sample_id),
        "mutations": None,
        "copy_number": None,
        "rna": None,
        "sources": {
            "availability": "data/tcga-brca/sample_manifest.csv",
            "clinical": "data/tcga-brca/raw/clinical.tsv",
            "survival": "data/tcga-brca/raw/survival.tsv",
            "protein": "data/tcga-brca/raw/protein_rppa.tsv.gz",
            "mutations": "data/tcga-brca/raw/mutation_gene_level.tsv.gz",
            "copy_number": "data/tcga-brca/raw/copy_number_gistic.tsv.gz",
            "rna": "data/tcga-brca/raw/rna_hiseq.tsv.gz",
            "slides": "data/tcga-brca/slide_manifest.csv",
        },
    }

    if include_large_layers:
        details["mutations"] = _load_mutations(sample_id)
        details["copy_number"] = _load_copy_number(sample_id)
        details["rna"] = _load_rna(sample_id)

    details["missing"] = [
        name.replace("_", " ").title()
        for name, available in details["availability"].items()
        if not available and name != "diagnostic_slide"
    ]
    if details["availability"]["slides"] and not details["availability"]["diagnostic_slide"]:
        details["missing"].append("Diagnostic Slide")
    details["quality_checks"] = run_case_quality_checks(details)
    return details
