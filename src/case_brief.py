"""Build a conservative, source-cited brief for one Case Room sample.

The brief deliberately uses fixed evidence-selection rules.  It summarizes
source values but does not turn research measurements into diagnoses or
clinical recommendations.
"""

from __future__ import annotations

import re
from typing import Any

from src.case_evidence import publisher_url, question_evidence, resolve_sources
from src.case_loader import CLINICAL_FIELDS
from src.case_questions import answer_case_question


KEY_MUTATION_GENES = ("TP53", "BRCA1", "BRCA2", "ESR1", "PGR", "ERBB2")


def _entry(text: str, source: str, locator: str, links: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "text": text,
        "source": source,
        "locator": locator,
        "links": links or [],
    }


def build_case_brief(case: dict[str, Any], evidence=None) -> list[dict[str, Any]]:
    """Return atomic, cited statements for a single linked case."""

    sample_id = case["sample_id"]
    patient_id = case.get("patient_id") or "unavailable patient"
    sample_type = case.get("sample_type") or "unknown sample type"
    sources = case["sources"]
    evidence = question_evidence(case) if evidence is None else evidence

    def cite(statement, refs):
        statement["source_records"] = resolve_sources(evidence, refs)
        return statement

    statements = [
        _entry(
            f"{sample_id} is a {sample_type.lower()} sample linked to patient {patient_id}.",
            sources["availability"],
            f"sample_id={sample_id}; fields: patient_id, sample_type",
        )
    ]

    identity = ["manifest-patient_id", "manifest-sample_type"]
    if case["manifest_source_row"] is None:
        identity = ["availability", "slide-count"]
        statements[0]["text"] = (
            f"{sample_id} has slide records and no matching sample manifest row."
        )
    cite(statements[0], identity)

    clinical = case.get("clinical") or {}
    clinical_fields = (
        ("Pathologic stage", "pathologic stage"),
        ("ER clinical status", "ER"),
        ("PR clinical status", "PR"),
        ("HER2 clinical status", "HER2"),
        ("PAM50 RNA subtype", "PAM50 subtype"),
    )
    conflict_fields = {
        field
        for conflict in case.get("conflicts") or []
        for field in conflict.get("fields", [])
    }
    available_clinical = [
        f"{label}: {clinical[field]}"
        for field, label in clinical_fields
        if clinical.get(field) is not None and field not in conflict_fields
    ]
    if available_clinical:
        statements.append(
            _entry(
                "Recorded clinical characteristics are " + "; ".join(available_clinical) + ".",
                sources["clinical"],
                f"sample column/row={sample_id}; fields: "
                + ", ".join(
                    field
                    for field, _ in clinical_fields
                    if clinical.get(field) is not None and field not in conflict_fields
                ),
            )
        )
        row = case["clinical_records"][0]["Source row"]
        cite(statements[-1], [
            f"clinical-{row}-{column}" for column, label in CLINICAL_FIELDS.items()
            if label not in conflict_fields and clinical.get(label) is not None
        ])
    elif not case.get("clinical_records") and not clinical:
        statements.append(
            _entry(
                "No clinical record is linked to this exact sample ID.",
                sources["clinical"],
                f"exact sample lookup={sample_id}",
            )
        )

        cite(statements[-1], ["clinical"])

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
            f"sample column={sample_id}; mutation value is nonzero; focus list is fixed in the application",
        )
    )

    cite(statements[-1], ["mutations-header" if mutations is None else "mutation-count"])

    review_notes_start = len(statements)
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

    cite(statements[-1], [
        ref for ref in evidence
        if ref.startswith(("manifest-in_", "manifest-has_")) or ref == "availability"
    ])

    slides = case.get("slides") or []
    diagnostic_count = sum("diagnostic" in (slide["slide_kind"] or "").lower() for slide in slides)
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

    cite(statements[-1], ["slide-count"])

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
    cite(statements[-1], [f"check-{check['id']}" for check in checks])
    for check in warnings + errors:
        statements.append(
            _entry(
                f"{check['title']}: {check['detail']}",
                check["source"],
                f"quality check={check['id']}; status={check['status']}",
            )
        )

        cite(statements[-1], [f"check-{check['id']}"])

    for conflict in case.get("conflicts") or []:
        row_locator = ""
        if conflict.get("records"):
            rows = sorted({str(record["Source row"]) for record in conflict["records"]})
            row_locator = "; source rows=" + ", ".join(rows)
        values_by_row = [
            f"Row {record['Source row']} records {record['Field']} as {record['Value']}."
            for record in conflict.get("records", [])
        ]
        detail = " ".join([conflict["detail"], *values_by_row])
        statements.append(
            _entry(
                f"Conflict preserved: {detail}",
                conflict["source"],
                f"conflict={conflict['id']}{row_locator}",
            )
        )

        cite(statements[-1], [f"conflict-{conflict['id']}"])

    for statement in statements[review_notes_start:]:
        statement["review_note"] = True
    return statements


def generate_case_brief(api_key, evidence):
    """Draft cited sentences and resolve their sources against this case."""
    claims = answer_case_question(
        api_key,
        "Write a concise research brief for the open sample.",
        evidence,
        additional_instructions=(
            "\nWrite three to five sentences when the evidence supports them. Cover available "
            "clinical and molecular findings and the slide inventory. Include any relevant "
            "limitations or disagreements, and report both values for disputed findings. "
            "Cite individual slide records when you describe those slides."
        ),
    )
    if not claims:
        raise ValueError("Claude did not return a cited brief.")
    statements = []
    for claim in claims:
        refs = list(dict.fromkeys(claim["sources"]))
        items = resolve_sources(evidence, refs)
        links = dict(link for item in items for link in item["links"])
        statement = _entry(
            claim["text"].strip(),
            " / ".join(dict.fromkeys(item["source"] for item in items)),
            "Source coordinates and values below",
            [{"label": label, "url": url} for label, url in links.items()],
        )
        statement["evidence_refs"] = refs
        statement["source_records"] = items
        statements.append(statement)
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
    showing_claude = any(statement.get("evidence_refs") for statement in statements)
    if showing_claude:
        lines.extend(["Claude draft. Check the cited records below each statement.", ""])
    notes_started = False
    for statement in statements:
        if showing_claude and statement.get("review_note") and not notes_started:
            lines.extend(["", "## Evidence coverage and data checks", ""])
            notes_started = True
        lines.extend(
            [
                "- " + re.sub(r"([\\`*_{}\[\]<>!|])", r"\\\1", " ".join(statement["text"].splitlines())),
                f"  - Source: `{statement['source']}`",
                f"  - Locator: {statement['locator']}",
            ]
        )
        links = {link["label"]: link["url"] for link in statement["links"]}
        for item in statement.get("source_records", []):
            values = ", ".join(f"{field} = {value if value is not None else 'blank or missing'}"
                               for field, value in item["data"].items())
            lines.append(f"  - `{item['source']}` · {item['locator']} · {values}")
            if url := publisher_url(item):
                filename = item["source"].rsplit("/", 1)[-1]
                links[f"Original UCSC Xena dataset ({filename})"] = url
            links.update(item["links"])
        for label, url in links.items():
            lines.append(f"  - [{label}]({url})")

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
