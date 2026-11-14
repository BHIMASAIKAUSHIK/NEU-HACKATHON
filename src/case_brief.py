"""Build a conservative, source-cited brief for one Case Room sample.

The brief deliberately uses fixed evidence-selection rules.  It summarizes
source values but does not turn research measurements into diagnoses or
clinical recommendations.
"""

from __future__ import annotations

from typing import Any


KEY_MUTATION_GENES = ("TP53", "BRCA1", "BRCA2", "ESR1", "PGR", "ERBB2")


def _entry(text: str, source: str, locator: str, links: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "text": text,
        "source": source,
        "locator": locator,
        "links": links or [],
    }


def build_case_brief(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Return atomic, cited statements for a single linked case."""

    sample_id = case["sample_id"]
    patient_id = case.get("patient_id") or "unavailable patient"
    sample_type = case.get("sample_type") or "unknown sample type"
    sources = case["sources"]

    statements = [
        _entry(
            f"{sample_id} is a {sample_type.lower()} sample linked to patient {patient_id}.",
            sources["availability"],
            f"sample_id={sample_id}; fields: patient_id, sample_type",
        )
    ]

    clinical = case.get("clinical") or {}
    clinical_fields = (
        ("Pathologic stage", "pathologic stage"),
        ("ER clinical status", "ER"),
        ("PR clinical status", "PR"),
        ("HER2 clinical status", "HER2"),
        ("PAM50 RNA subtype", "PAM50 subtype"),
    )
    available_clinical = [
        f"{label}: {clinical[field]}"
        for field, label in clinical_fields
        if clinical.get(field) is not None
    ]
    if available_clinical:
        statements.append(
            _entry(
                "Recorded clinical characteristics are " + "; ".join(available_clinical) + ".",
                sources["clinical"],
                f"sample column/row={sample_id}; fields: "
                + ", ".join(field for field, _ in clinical_fields if clinical.get(field) is not None),
            )
        )
    else:
        statements.append(
            _entry(
                "No clinical record is linked to this exact sample ID.",
                sources["clinical"],
                f"exact sample lookup={sample_id}",
            )
        )

    mutations = case.get("mutations")
    if mutations is None:
        mutation_text = "Mutation data is unavailable for this sample."
    else:
        mutation_names = {item["gene"] for item in mutations}
        highlighted = [gene for gene in KEY_MUTATION_GENES if gene in mutation_names]
        mutation_text = f"The source matrix marks {len(mutations)} genes as mutated"
        if highlighted:
            mutation_text += ", including predefined focus genes " + ", ".join(highlighted)
        mutation_text += "."
    statements.append(
        _entry(
            mutation_text,
            sources["mutations"],
            f"sample column={sample_id}; mutation value=1; focus list is fixed in the application",
        )
    )

    availability = case.get("availability") or {}
    layer_names = {
        "clinical": "clinical",
        "survival": "survival",
        "mutation": "mutation",
        "copy_number": "copy number",
        "rna": "RNA",
        "protein": "protein",
    }
    present = [label for key, label in layer_names.items() if availability.get(key)]
    missing = [label for key, label in layer_names.items() if not availability.get(key)]
    coverage_text = "Available data layers: " + (", ".join(present) if present else "none") + "."
    coverage_text += " Missing data layers: " + (", ".join(missing) if missing else "none") + "."
    statements.append(
        _entry(
            coverage_text,
            sources["availability"],
            f"sample_id={sample_id}; availability fields cross-checked by Case Data Quality",
        )
    )

    slides = case.get("slides") or []
    diagnostic_count = sum("diagnostic" in slide["slide_kind"].lower() for slide in slides)
    if slides:
        slide_text = (
            f"{len(slides)} pathology slide{'s are' if len(slides) != 1 else ' is'} linked by exact "
            f"sample barcode, including {diagnostic_count} diagnostic slide"
            f"{'s' if diagnostic_count != 1 else ''}."
        )
        slide_links = [
            {"label": slide["slide_barcode"], "url": slide["viewer_url"]}
            for slide in slides
            if slide.get("viewer_url")
        ]
        slide_locator = "slide barcodes: " + ", ".join(slide["slide_barcode"] for slide in slides)
    else:
        slide_text = "No pathology slide is linked to this exact sample ID."
        slide_links = []
        slide_locator = f"exact sample lookup={sample_id}"
    statements.append(_entry(slide_text, sources["slides"], slide_locator, slide_links))

    checks = case.get("quality_checks") or []
    warnings = [check for check in checks if check["status"] == "warning"]
    errors = [check for check in checks if check["status"] == "error"]
    passed = sum(check["status"] == "pass" for check in checks)
    statements.append(
        _entry(
            f"Case data quality: {passed} checks passed, {len(warnings)} warnings, and {len(errors)} errors.",
            "Case Data Quality checks",
            "derived from the cited integrity checks displayed below this brief",
        )
    )
    for check in warnings + errors:
        statements.append(
            _entry(
                f"{check['title']}: {check['detail']}",
                check["source"],
                f"quality check={check['id']}; status={check['status']}",
            )
        )

    return statements


def render_case_brief_markdown(case: dict[str, Any], statements: list[dict[str, Any]]) -> str:
    """Render a portable Markdown brief with citations and slide links."""

    lines = [
        f"# OncoSys Case Brief: {case['sample_id']}",
        "",
        "> Research-use evidence summary. This is not a diagnosis, treatment recommendation, "
        "risk score, or claim of clinical validity.",
        "",
        "## Source-cited summary",
        "",
    ]
    for statement in statements:
        lines.extend(
            [
                f"- {statement['text']}",
                f"  - Source: `{statement['source']}`",
                f"  - Locator: {statement['locator']}",
            ]
        )
        for link in statement["links"]:
            lines.append(f"  - [{link['label']}]({link['url']})")

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "Raw RNA, copy-number and protein measurements are not labelled high, low, abnormal, "
            "or clinically significant without a documented threshold. Review the original evidence "
            "with a qualified human reviewer.",
            "",
        ]
    )
    return "\n".join(lines)
