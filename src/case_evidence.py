"""Resolve citations to source coordinates for the selected sample."""

import csv
import gzip
from functools import lru_cache
from pathlib import Path

from src.case_loader import CLINICAL_FIELDS, PROTEIN_ROWS, SURVIVAL_FIELDS
from src.data_loader import DATA_LAYER_COLUMNS, PROJECT_ROOT


@lru_cache(maxsize=1)
def _publisher_urls():
    directory = Path("data/tcga-brca")
    with (PROJECT_ROOT / directory / "sources.csv").open(encoding="utf-8", newline="") as handle:
        return {
            (directory / "raw" / row["file"]).as_posix(): row["source_url"]
            for row in csv.DictReader(handle)
        }


def publisher_url(item):
    """Use the same publisher URL as the dataset downloader."""
    return _publisher_urls().get(item["source"]) if item.get("location") else None


def question_evidence(case):
    sample = case["sample_id"]
    sources = case["sources"]
    evidence = {}

    def add(ref, source, locator, data, links=(), inputs=(), location=None):
        evidence[ref] = {
            "ref": ref, "sample_id": sample,
            "source": sources.get(source, source),
            "locator": locator, "data": data, "links": links, "inputs": inputs,
            "location": location,
        }
        return ref

    def row_location(key, row, column):
        return f'{key}={sample} · row {row} · column "{column}"'

    def lookup(key, column, count):
        return add(key, key, f'Exact lookup · {column} = "{sample}"', {
            "matching records": count,
        }, location={"match": (column, sample)})

    def fields(prefix, source, key, row, values):
        return [
            add(f"{prefix}-{column}", source, row_location(key, row, column), {label: value},
                location={"match": (key, sample), "row": row, "column": column})
            for column, (label, value) in values.items()
        ]

    slides = case["slides"]
    manifest_row = case["manifest_source_row"]
    if manifest_row is None:
        manifest_refs = [lookup("availability", "sample_id", 0)]
    else:
        manifest_refs = fields("manifest", "availability", "sample_id", manifest_row, {
            "patient_id": ("patient ID", case["patient_id"]),
            "sample_type": ("sample type", case["sample_type"]),
        })
        manifest_refs += fields("manifest", "availability", "sample_id", manifest_row, {
            column: (column, case["availability"][layer])
            for column, layer in zip(
                DATA_LAYER_COLUMNS, ("clinical", "survival", "mutation", "copy_number", "rna", "protein")
            )
        })

    clinical_refs = []
    for record in case["clinical_records"]:
        row = record["Source row"]
        clinical_refs.extend(fields(f"clinical-{row}", "clinical", "sampleID", row, {
            column: (label, record[label]) for column, label in {
                **CLINICAL_FIELDS, "_PATIENT": "Patient ID",
            }.items()
        }))
    if not clinical_refs:
        clinical_refs = [lookup("clinical", "sampleID", 0)]

    survival = case["survival"]
    if survival is not None:
        fields("survival", "survival", "sample", survival["Source row"], {
            column: (label, survival[label]) for column, label in SURVIVAL_FIELDS.items()
        })
    else:
        lookup("survival", "sample", 0)

    def matrix(layer, availability_key, index_column, values, available):
        count = case["matrix_column_counts"][availability_key]
        header = add(f"{layer}-header", layer, f'Header lookup · exact column "{sample}"', {
            "sample column": sample, "matching columns": count,
        }, location={"column": sample, "header_only": True})
        refs = []
        if count == 1 and available:
            for row, label, value in values:
                ref = f"{layer}-{row}"
                refs.append(add(
                    ref, layer, f'Row key {index_column}="{row}" · column "{sample}"',
                    {label: value},
                    location={"match": (index_column, str(row)), "column": sample},
                ))
        return header, refs

    protein = case["protein"]
    protein_header, _ = matrix("protein", "protein", "Sample_description", (
        (row, label, protein[label]) for row, label in PROTEIN_ROWS.items()
    ), protein is not None)
    rna_header, _ = matrix("rna", "rna", "sample", (
        (record["gene"], "RNA expression", record["expression"]) for record in case["rna"] or []
    ), case["rna"] is not None)
    cn_header, _ = matrix("copy_number", "copy_number", "Gene Symbol", (
        (record["gene"], "Copy number", record["value"]) for record in case["copy_number"] or []
    ), case["copy_number"] is not None)
    mutations = case["mutations"]
    mutation_header, mutation_refs = matrix("mutations", "mutation", "sample", (
        (record["gene"], "Mutation indicator", record["source_value"]) for record in mutations or []
    ), mutations is not None)
    if mutations is not None:
        add("mutation-count", "mutations", f'Column "{sample}" · count gene rows with a nonzero value',
            {"genes marked mutated": len(mutations)}, inputs=mutation_refs or [mutation_header])

    slide_refs = []
    for slide in slides:
        barcode = slide["slide_barcode"]
        row = slide["source_row"]
        slide_refs.append(add(
            f"slide-{row}", "slides", f"sample_id={sample} · row {row} · slide_barcode={barcode}",
            {column: slide[column] for column in (
                "slide_barcode", "slide_kind", "patient_id", "objective", "size_mb", "viewer_url",
            )},
            ((barcode, slide["viewer_url"]),) if slide["viewer_url"] else (),
            location={"match": ("sample_id", sample), "row": row},
        ))
    if not slide_refs:
        slide_refs = [lookup("slides", "sample_id", 0)]
    add("slide-count", "slides", f"Exact sample_id={sample} · count linked rows and diagnostic slide_kind",
        {"matching slides": len(slides), "diagnostic slides": sum(
            "diagnostic" in (slide["slide_kind"] or "").lower() for slide in slides
        )}, inputs=slide_refs)

    missing_inputs = [ref for ref in manifest_refs if next(iter(evidence[ref]["data"].values())) is False]
    if manifest_row is None:
        missing_inputs = manifest_refs
    missing_inputs += [ref for ref in (protein_header, mutation_header, rna_header, cn_header)
                       if evidence[ref]["data"]["matching columns"] == 0]
    missing_inputs += [ref for ref in ("clinical", "survival") if ref in evidence]
    check_inputs = {
        "manifest-link": manifest_refs,
        "clinical-row-count": clinical_refs,
        "patient-consistency": manifest_refs + clinical_refs,
        "molecular-column-links": manifest_refs + [mutation_header, cn_header, rna_header, protein_header],
        "missing-layers": missing_inputs or manifest_refs,
        "slide-duplicates": slide_refs,
        "slide-patient-link": slide_refs + manifest_refs,
        "diagnostic-slide": ("slide-count",),
        "clinical-categories": clinical_refs,
        "slide-values": slide_refs,
    }
    for check in case["quality_checks"]:
        add(f"check-{check['id']}", check["source"], f"Data check · {check['title']}", {
            "status": check["status"], "finding": check["detail"],
        }, inputs=check_inputs[check["id"]])
    for conflict in case["conflicts"]:
        columns = {label: column for column, label in {**CLINICAL_FIELDS, "_PATIENT": "Patient ID"}.items()}
        records = [
            add(f"conflict-value-{conflict['id']}-{record['Source row']}", "clinical",
                row_location("sampleID", record["Source row"], columns[record["Field"]]),
                {record["Field"]: record["Value"]},
                location={"match": ("sampleID", sample), "row": record["Source row"],
                          "column": columns[record["Field"]]})
            for record in conflict["records"]
        ]
        add(f"conflict-{conflict['id']}", conflict["source"], f"Data check · {conflict['title']}", {
            "finding": conflict["detail"], "conflicting records": conflict["records"],
        }, inputs=records or [f"check-{conflict['id']}"])

    return evidence


def resolve_sources(evidence, refs):
    """Keep both derived results and the records used to compute them."""
    resolved = {}

    def visit(ref):
        if ref in resolved:
            return
        item = evidence[ref]
        resolved[ref] = item
        for input_ref in item["inputs"]:
            visit(input_ref)

    for ref in refs:
        visit(ref)
    return list(resolved.values())


def read_source_record(item):
    """Read the original text at a citation, or repeat its exact lookup."""
    path = PROJECT_ROOT / item["source"]
    location = item["location"]
    column = location.get("column")
    match = location.get("match")
    row_number = location.get("row")
    if not path.is_file():
        return "Source file is unavailable in this workspace.", []

    opener = gzip.open if path.suffix == ".gz" else open
    delimiter = "," if path.suffix == ".csv" else "\t"
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        header = next(reader, [])
        if location.get("header_only"):
            positions = [str(position) for position, name in enumerate(header, 1) if name == column]
            return (f'Header lookup for "{column}" found {len(positions)} matching columns.',
                    [{"Column": column, "Position": position} for position in positions])
        if column is not None and header.count(column) != 1:
            return f'Column "{column}" occurs {header.count(column)} times in the source header.', []
        key, value = match
        if key not in header:
            return f'The source header has no "{key}" field.', []
        index = header.index(key)
        selected = range(len(header)) if column is None else [header.index(column)]
        records = []
        for number, cells in enumerate(reader, 2):
            if row_number is not None and number > row_number:
                break
            if len(cells) > index and cells[index] == value and row_number in (None, number):
                records.extend({
                    "Row": number,
                    "Column": header[position],
                    "Original value": cells[position] if position < len(cells) else "",
                } for position in selected)
        if not records:
            return f'No source row matches {key} = "{value}" at this location.', []
        return f'Exact match for {key} = "{value}".', records
