"""Prioritize the next research review action using the selected case records."""

LAYER_LABELS = {
    "clinical": "Clinical record",
    "survival": "Follow-up data",
    "mutations": "Reported gene mutations",
    "copy_number": "DNA copy number",
    "rna": "RNA measurements",
    "protein": "Protein measurements",
}


def build_case_review(case):
    available = {
        layer: bool(case["clinical_records"]) if layer == "clinical" else case[layer] is not None
        for layer in LAYER_LABELS
    }
    missing = [LAYER_LABELS[layer] for layer, found in available.items() if not found]
    diagnostics = [
        slide for slide in case["slides"]
        if "diagnostic" in (slide["slide_kind"] or "").lower()
    ]
    errors = [check for check in case["quality_checks"] if check["status"] == "error"]
    if errors or case["conflicts"]:
        status = "Some records need review"
        explanation = "Inspect the flagged source records before relying on the affected evidence."
        destination = "Data checks"
    elif missing or not diagnostics:
        status = "Some evidence is missing"
        explanation = "Check the gaps below against what your research question needs."
        destination = "Data checks"
    else:
        status = "Key evidence is available"
        explanation = "Review the clinical record and the linked diagnostic slides for your question."
        destination = "Records and measurements"
    return {
        "available": available,
        "missing": missing,
        "diagnostic_count": len(diagnostics),
        "status": status,
        "explanation": explanation,
        "destination": destination,
    }
