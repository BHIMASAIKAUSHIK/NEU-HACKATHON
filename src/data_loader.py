"""Load the lightweight sample catalog used by the Case Room landing page.

The catalog deliberately uses only the two committed manifests. Large molecular
tables are loaded later, after a reviewer selects a case.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_MANIFEST = PROJECT_ROOT / "data" / "tcga-brca" / "sample_manifest.csv"
SLIDE_MANIFEST = PROJECT_ROOT / "data" / "tcga-brca" / "slide_manifest.csv"

DATA_LAYER_COLUMNS = (
    "in_clinical",
    "has_survival",
    "has_mutation",
    "has_copy_number",
    "has_rna",
    "has_protein",
)

SAMPLE_TYPE_CODES = {
    "01": "Primary Tumor",
    "06": "Metastasis",
    "11": "Normal Tissue",
}


def _sample_type_from_barcode(sample_id: str) -> str:
    """Infer the documented TCGA sample type from the final two digits."""

    text = str(sample_id)
    if len(text) < 15:
        return "Unknown"
    return SAMPLE_TYPE_CODES.get(text[13:15], "Other")


def _normalise_bool(series: pd.Series) -> pd.Series:
    """Return a strict boolean series for CSV values and missing records."""

    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    return (
        series.astype("string")
        .fillna("")
        .str.strip()
        .str.lower()
        .isin({"true", "1", "yes"})
    )


def load_sample_catalog(
    sample_manifest_path: str | Path = SAMPLE_MANIFEST,
    slide_manifest_path: str | Path = SLIDE_MANIFEST,
) -> pd.DataFrame:
    """Build one lightweight row per sample across both committed manifests.

    An outer union is intentional: some samples have slide records but no
    molecular/clinical manifest record. Those gaps are important findings and
    must remain visible rather than being dropped by an inner join.
    """

    sample_path = Path(sample_manifest_path)
    slide_path = Path(slide_manifest_path)
    if not sample_path.exists():
        raise FileNotFoundError(f"Sample manifest not found: {sample_path}")
    if not slide_path.exists():
        raise FileNotFoundError(f"Slide manifest not found: {slide_path}")

    samples = pd.read_csv(sample_path, dtype={"sample_id": "string", "patient_id": "string"})
    slides = pd.read_csv(
        slide_path,
        dtype={"sample_id": "string", "patient_id": "string", "slide_kind": "string"},
    )

    required_sample_columns = {"sample_id", "patient_id", "sample_type", *DATA_LAYER_COLUMNS}
    required_slide_columns = {"sample_id", "patient_id", "slide_kind"}
    missing_sample = required_sample_columns - set(samples.columns)
    missing_slide = required_slide_columns - set(slides.columns)
    if missing_sample:
        raise ValueError(f"Sample manifest is missing columns: {sorted(missing_sample)}")
    if missing_slide:
        raise ValueError(f"Slide manifest is missing columns: {sorted(missing_slide)}")

    slide_rows = slides.assign(
        is_diagnostic=slides["slide_kind"].str.contains("diagnostic", case=False, na=False),
        is_frozen=slides["slide_kind"].str.contains("frozen", case=False, na=False),
    )
    slide_summary = (
        slide_rows.groupby("sample_id", as_index=False)
        .agg(
            slide_patient_id=("patient_id", "first"),
            total_slides=("sample_id", "size"),
            diagnostic_slides=("is_diagnostic", "sum"),
            frozen_slides=("is_frozen", "sum"),
        )
    )

    samples = samples.copy()
    samples["in_sample_manifest"] = True
    catalog = samples.merge(slide_summary, on="sample_id", how="outer", validate="one_to_one")

    catalog["patient_id"] = catalog["patient_id"].fillna(catalog["slide_patient_id"])
    catalog["sample_type"] = catalog["sample_type"].fillna(
        catalog["sample_id"].map(_sample_type_from_barcode)
    )
    catalog["in_sample_manifest"] = _normalise_bool(catalog["in_sample_manifest"])

    for column in DATA_LAYER_COLUMNS:
        catalog[column] = _normalise_bool(catalog[column])

    for column in ("total_slides", "diagnostic_slides", "frozen_slides"):
        catalog[column] = catalog[column].fillna(0).astype(int)

    catalog["available_layers"] = catalog[list(DATA_LAYER_COLUMNS)].sum(axis=1).astype(int)
    catalog["has_diagnostic_slide"] = catalog["diagnostic_slides"] > 0
    catalog["has_any_slide"] = catalog["total_slides"] > 0
    catalog["record_status"] = catalog["in_sample_manifest"].map(
        {True: "Linked record", False: "Slide-only record"}
    )

    return catalog.sort_values("sample_id", kind="stable").reset_index(drop=True)


def filter_sample_catalog(
    catalog: pd.DataFrame,
    *,
    search: str = "",
    sample_types: list[str] | None = None,
    protein_filter: str = "Any",
    slide_filter: str = "Any",
) -> pd.DataFrame:
    """Apply landing-page filters without mutating the cached catalog."""

    result = catalog
    search_text = search.strip().lower()
    if search_text:
        matches_sample = result["sample_id"].fillna("").str.lower().str.contains(
            search_text, regex=False
        )
        matches_patient = result["patient_id"].fillna("").str.lower().str.contains(
            search_text, regex=False
        )
        result = result[matches_sample | matches_patient]

    if sample_types:
        result = result[result["sample_type"].isin(sample_types)]

    if protein_filter == "Available":
        result = result[result["has_protein"]]
    elif protein_filter == "Missing":
        result = result[~result["has_protein"]]

    if slide_filter == "Diagnostic available":
        result = result[result["has_diagnostic_slide"]]
    elif slide_filter == "Any slide available":
        result = result[result["has_any_slide"]]
    elif slide_filter == "No slides":
        result = result[~result["has_any_slide"]]

    return result.reset_index(drop=True)
