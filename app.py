"""Streamlit landing page for the OncoSys Multimodal Case Room."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from src.case_evidence import publisher_url, question_evidence, read_source_record, resolve_sources
from src.case_loader import load_case_details
from src.case_brief import build_case_brief, generate_case_brief, render_case_brief_markdown
from src.case_questions import STARTER_QUESTIONS, answer_case_question
from src.case_review import LAYER_LABELS as REVIEW_LAYERS, build_case_review
from src.case_urls import API_KEYS_URL, source_record_url
from src.data_loader import DATA_LAYER_COLUMNS, filter_sample_catalog, load_sample_catalog
from src.judge_case import parse_judge_case


PAGE_SIZE = 24
LAYER_LABELS = {
    "in_clinical": "Clinical",
    "has_survival": "Survival",
    "has_mutation": "Mutation",
    "has_copy_number": "Copy number",
    "has_rna": "RNA",
    "has_protein": "Protein",
}


st.set_page_config(
    page_title="OncoSys Case Room",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_data(show_spinner="Loading sample catalog…")
def get_catalog():
    return load_sample_catalog()


def select_case(sample_id: str) -> None:
    st.session_state.selected_sample_id = sample_id
    st.session_state.pop("case_section", None)
    st.session_state.pop("case_answer", None)
    st.session_state.pop("generated_brief", None)


def clear_case() -> None:
    st.session_state.selected_sample_id = None


def reset_page() -> None:
    st.session_state.catalog_page = 1


@st.cache_data(show_spinner="Linking this case across the source files…")
def get_case_details(sample_id: str):
    return load_case_details(sample_id)


def _display_value(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Unavailable"
    return str(value)


def render_case_questions(case, api_key: str) -> None:
    sample_id = case["sample_id"]
    st.subheader("Ask this case")
    st.caption("Ask about the records, measurements, slides, or conflicts for this sample.")
    with st.form("ask-case"):
        question = st.text_input("Your question", max_chars=500,
                                 placeholder="What stage is recorded, and is there a diagnostic slide?")
        submitted = st.form_submit_button("Ask Claude")
    columns = st.columns(len(STARTER_QUESTIONS))
    for column, starter in zip(columns, STARTER_QUESTIONS):
        if column.button(starter):
            question, submitted = starter, True

    if submitted:
        st.session_state.pop("case_answer", None)
        if not question.strip():
            st.info("Enter a question about this sample.")
        elif not api_key:
            st.info("Enter your Claude API key in the sidebar first.")
        else:
            evidence = question_evidence(case)
            try:
                with st.spinner("Claude is reading the selected case…"):
                    answer = answer_case_question(api_key, question.strip(), evidence)
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state.case_answer = (sample_id, question.strip(), answer, evidence)

    result = st.session_state.get("case_answer")
    if result is None or result[0] != sample_id:
        return
    _, question, answer, evidence = result
    st.text(question)
    if not answer:
        st.info("The available records don’t answer this question.")
        return
    st.caption("Compare each claim with its original source before relying on it.")
    for index, claim in enumerate(answer):
        st.text(claim["text"])
        with st.expander("View evidence for this claim"):
            render_source_records(resolve_sources(evidence, claim["sources"]), f"answer-{index}")


def show_source_record(records, key):
    index = st.selectbox(
        "Exact source location",
        range(len(records)),
        key=f"source-location-{key}",
        format_func=lambda index: f"{records[index]['source']} · {records[index]['locator']}",
    )
    render_original_record(records[index])


def render_original_record(item):
    url = publisher_url(item)
    if url:
        st.link_button("Open original dataset on UCSC Xena ↗", url)
        st.caption("Use the source location above to find this entry in the download.")
    try:
        message, cells = read_source_record(item)
    except (OSError, UnicodeError):
        st.error("The source file could not be read.")
        return
    st.write(message)
    if cells:
        st.dataframe(cells, hide_index=True, width="stretch")
        if any(cell.get("Original value") == "" for cell in cells):
            st.caption("Empty cells are blank in the original file.")
    for label, url in item["links"]:
        st.link_button(f"Open slide {label} ↗", url)


def render_source_records(records, key):
    st.dataframe([
        {
            "Source file": item["source"],
            "Exact location": item["locator"],
            "Recorded value or result": ", ".join(
                f"{field} = {'blank or missing' if value is None else value}"
                for field, value in item["data"].items()
            ),
        }
        for item in records
    ], hide_index=True, width="stretch")
    originals = [item for item in records if item.get("location")]
    publisher_links = {
        item["source"].rsplit("/", 1)[-1]: url
        for item in originals if (url := publisher_url(item))
    }
    for filename, url in publisher_links.items():
        st.link_button(f"Open original dataset on UCSC Xena ({filename}) ↗", url)
    if originals and st.checkbox("Show source record", key=f"source-{key}"):
        show_source_record(originals, key)
    if originals:
        links = []
        for item in originals:
            label = f"{item['source'].rsplit('/', 1)[-1]} · {item['locator']}"
            label = label.replace("[", r"\[").replace("]", r"\]")
            links.append(f"- [{label}]({source_record_url(item['sample_id'], item['ref'])})")
        with st.expander("Direct links to exact locations"):
            st.markdown("\n".join(links))
    links = dict(link for item in records for link in item["links"])
    for label, url in links.items():
        st.link_button(f"Open slide {label} ↗", url)


def render_case_detail(catalog, api_key: str) -> None:
    sample_id = st.session_state.selected_sample_id
    row = catalog.loc[catalog["sample_id"] == sample_id].iloc[0]

    st.button("← Back to all samples", on_click=clear_case)
    st.caption("Multimodal Case Room")
    st.title(sample_id)
    st.info(
        "Research-use prototype. Measurements shown here are not a diagnosis, treatment "
        "recommendation, risk score, or claim of clinical validity."
    )

    try:
        case = get_case_details(sample_id)
        # Streamlit can retain a cached case object across a hot reload after the
        # case schema changes. Refresh once rather than exposing a stale-shape
        # KeyError to the reviewer.
        if "matrix_column_counts" not in case:
            get_case_details.clear()
            case = get_case_details(sample_id)
    except (FileNotFoundError, KeyError, ValueError) as error:
        st.error(str(error))
        return

    st.caption(f"{row['sample_type']} · Patient {_display_value(row['patient_id'])}")
    review = build_case_review(case)
    with st.container(border=True):
        st.subheader(review["status"])
        st.write(review["explanation"])
        status_columns = st.columns(3)
        status_columns[0].metric("Data types available", f"{sum(review['available'].values())} of 6")
        status_columns[1].metric("Diagnostic slides", review["diagnostic_count"])
        status_columns[2].metric("All slides", len(case["slides"]))
        missing = review["missing"] + ([] if review["diagnostic_count"] else ["Diagnostic slide"])
        if missing:
            st.write("**Missing evidence** · " + ", ".join(missing))
        destination = review["destination"]
        label = "Review gaps and conflicts" if destination == "Data checks" else "Review records and measurements"
        st.button(label, type="primary",
                  on_click=lambda: st.session_state.update(case_section=destination))
    section = st.radio(
        "Case sections",
        ["Overview", "Records and measurements", "Slides", "Data checks", "Ask Claude"],
        horizontal=True, key="case_section",
    )
    if section == "Records and measurements":
        render_records(case)
    elif section == "Slides":
        render_slides(case)
    elif section == "Data checks":
        render_data_checks(case, row, review)
    elif section == "Ask Claude":
        render_case_questions(case, api_key)
    else:
        render_overview(case, api_key)


def render_overview(case, api_key: str) -> None:
    st.subheader("Case Summary")
    st.caption("Expand a source to check where the summary statement came from.")
    evidence = question_evidence(case)
    default_brief = build_case_brief(case, evidence)
    if st.button("Generate cited brief", help="Sends this sample’s evidence to Claude."):
        st.session_state.pop("generated_brief", None)
        if not api_key:
            st.info("Expand the sidebar and enter your Claude API key to generate a brief.")
        else:
            try:
                with st.spinner("Claude is drafting the brief…"):
                    generated = generate_case_brief(api_key, evidence)
            except ValueError as error:
                st.warning(f"{error} Showing the standard brief.")
            else:
                st.session_state.generated_brief = (case["sample_id"], generated, evidence)
    result = st.session_state.get("generated_brief")
    showing_claude = bool(result and result[0] == case["sample_id"])
    if showing_claude:
        _, generated, evidence = result
        brief_statements = generated + [item for item in default_brief if item.get("review_note")]
        st.caption("Claude draft. Expand its citations to check the source records.")
    else:
        brief_statements = default_brief
        st.caption("Standard brief from the source records.")

    with st.container(border=True):
        for index, statement in enumerate(brief_statements):
            if showing_claude and index == len(generated):
                st.markdown("**Evidence coverage and data checks**")
            st.text(statement["text"])
            with st.expander("View evidence for this claim"):
                render_source_records(statement["source_records"], f"brief-{index}")

    brief_markdown = render_case_brief_markdown(case, brief_statements)
    st.download_button(
        "Download Case Brief (.md)",
        data=brief_markdown,
        file_name=f"{case['sample_id']}-case-brief.md",
        mime="text/markdown",
        width="stretch",
    )


def render_data_checks(case, row, review) -> None:
    evidence = question_evidence(case)
    st.subheader("Evidence coverage")
    for layer, label in REVIEW_LAYERS.items():
        status = "Available" if review["available"][layer] else "Missing"
        st.write(f"**{label}** · {status}")

    if not row["in_sample_manifest"]:
        st.warning(
            "Slides exist for this exact sample ID, but no matching clinical or molecular "
            "record exists in the sample manifest. The app will not attach a different sample."
        )
    elif not row["has_diagnostic_slide"]:
        st.info("No diagnostic slide is linked to this sample. Frozen slides may still be available.")

    blanks = [
        item for item in evidence.values()
        if ' · column "' in item["locator"] and None in item["data"].values()
    ]
    if blanks:
        with st.expander("Blank or missing values in the fields reviewed"):
            render_source_records(blanks, "blanks")

    st.subheader("Conflicting evidence")
    if case["conflicts"]:
        for conflict in case["conflicts"]:
            with st.expander(conflict["title"], expanded=True):
                st.write(conflict["detail"])
                if conflict["records"]:
                    st.dataframe(conflict["records"], hide_index=True, width="stretch")
                ref = f"conflict-{conflict['id']}"
                render_source_records(resolve_sources(evidence, [ref]), ref)
    else:
        st.write("The app found no disagreements in the records it checked.")

    st.subheader("Case data quality")
    quality_checks = case["quality_checks"]
    pass_count = sum(check["status"] == "pass" for check in quality_checks)
    warning_count = sum(check["status"] == "warning" for check in quality_checks)
    error_count = sum(check["status"] == "error" for check in quality_checks)
    quality_metrics = st.columns(3)
    quality_metrics[0].metric("Checks passed", pass_count)
    quality_metrics[1].metric("Warnings", warning_count)
    quality_metrics[2].metric("Errors", error_count)

    icons = {"pass": "✅", "warning": "⚠️", "error": "❌"}
    for check in sorted(quality_checks, key=lambda item: ("error", "warning", "pass").index(item["status"])):
        with st.expander(f"{icons[check['status']]} {check['title']}"):
            st.write(check["detail"])
            ref = f"check-{check['id']}"
            render_source_records(resolve_sources(evidence, [ref]), ref)
    st.caption(
        "These are data-integrity checks, not medical conclusions. Protein and RNA values "
        "are not labelled abnormal without a documented threshold."
    )


def render_records(case) -> None:
    st.subheader("Clinical record")
    if len(case["clinical_records"]) > 1:
        st.warning(
            f"{len(case['clinical_records'])} clinical rows match this sample. "
            "All rows are shown so differences remain visible."
        )
        st.dataframe(case["clinical_records"], hide_index=True, width="stretch")
        st.caption(f"Exact sample match · Source: `{case['sources']['clinical']}`")
    elif case["clinical"]:
        clinical_rows = [
            {"Field": field, "Value": _display_value(value)}
            for field, value in case["clinical"].items()
        ]
        st.dataframe(clinical_rows, hide_index=True, width="stretch")
        st.caption(f"Exact sample match · Source: `{case['sources']['clinical']}`")
    else:
        st.warning("No clinical row matches this exact sample ID.")

    st.subheader("Clinical and protein biomarkers")
    clinical = case["clinical"] or {}
    protein = case["protein"] or {}
    disputed_fields = {field for conflict in case["conflicts"] for field in conflict["fields"]}
    biomarker_rows = []
    for label, protein_label in (("ER", "ER-alpha"), ("PR", "PR"), ("HER2", "HER2")):
        field = f"{label} clinical status"
        biomarker_rows.append({
            "Biomarker": label,
            "Clinical result": (
                "Disputed — see Data checks" if field in disputed_fields
                else _display_value(clinical.get(field))
            ),
            "Protein measurement": _display_value(protein.get(protein_label)),
        })
    st.dataframe(biomarker_rows, hide_index=True, width="stretch")
    st.caption(
        f"Clinical source: `{case['sources']['clinical']}` · Protein source: "
        f"`{case['sources']['protein']}` · Values are shown side by side; the prototype "
        "does not invent a clinical cutoff for the protein scale."
    )

    mutation_tab, copy_tab, rna_tab, survival_tab = st.tabs(
        ["Mutations", "Copy number", "RNA", "Survival"]
    )
    with mutation_tab:
        if case["mutations"] is None:
            st.warning("Mutation data is unavailable for this sample.")
        elif case["mutations"]:
            st.write(f"**{len(case['mutations'])} genes are marked mutated in the source matrix.**")
            st.dataframe(case["mutations"], hide_index=True, width="stretch")
        else:
            st.write("No genes are marked mutated in the source matrix for this sample.")
        st.caption(f"Source: `{case['sources']['mutations']}`")

    with copy_tab:
        if case["copy_number"] is None:
            st.warning("Copy-number data is unavailable for this sample.")
        else:
            st.write("Focused research genes; GISTIC calls range from -2 to 2.")
            st.dataframe(case["copy_number"], hide_index=True, width="stretch")
        st.caption(f"Source: `{case['sources']['copy_number']}`")

    with rna_tab:
        if case["rna"] is None:
            st.warning("RNA data is unavailable for this sample.")
        else:
            st.write("Expression values for the same focused research genes.")
            st.dataframe(case["rna"], hide_index=True, width="stretch")
        st.caption(f"Source: `{case['sources']['rna']}`")

    with survival_tab:
        if case["survival"] is None:
            st.warning("No survival row matches this case.")
        else:
            survival_rows = [
                {"Field": field, "Value": _display_value(value)}
                for field, value in case["survival"].items() if field != "Source row"
            ]
            st.dataframe(survival_rows, hide_index=True, width="stretch")
        st.caption(f"Source: `{case['sources']['survival']}`")


def render_slides(case) -> None:
    st.subheader("Pathology slides")
    st.caption("Open a slide to view a scanned tissue section. Each record shows its slide type.")
    if case["slides"]:
        for index, slide in enumerate(case["slides"], start=1):
            with st.container(border=True):
                st.write(f"**Slide {index}: {slide['slide_kind']}**")
                st.write(
                    f"Barcode: `{slide['slide_barcode']}`  \n"
                    f"Objective: {_display_value(slide['objective'])}×  \n"
                    f"Size: {_display_value(slide['size_mb'])} MB  \n"
                    f"License: {_display_value(slide['license'])}"
                )
                if slide["viewer_url"]:
                    st.link_button("Open slide in NCI viewer ↗", slide["viewer_url"])
        st.caption(f"Exact sample match · Source: `{case['sources']['slides']}`")
    else:
        st.warning("No pathology slide matches this exact sample ID.")


def render_sample_card(row) -> None:
    available_count = sum(bool(row[column]) for column in DATA_LAYER_COLUMNS)
    missing = [LAYER_LABELS[column] for column in DATA_LAYER_COLUMNS if not row[column]]
    slide_text = f"{int(row['total_slides'])} slide(s)"
    if row["diagnostic_slides"]:
        slide_text += f", {int(row['diagnostic_slides'])} diagnostic"
    elif row["frozen_slides"]:
        slide_text += ", frozen only"

    with st.container(border=True):
        st.markdown(f"**{row['sample_id']}**")
        st.caption(f"{row['sample_type']} · {row['record_status']}")
        st.write(f"{available_count} / {len(DATA_LAYER_COLUMNS)} data layers · {slide_text}")
        if missing:
            st.caption(f"Missing: {', '.join(missing)}")
        else:
            st.caption("No missing data layers")
        st.button(
            "View case",
            key=f"view-{row['sample_id']}",
            on_click=select_case,
            args=(row["sample_id"],),
            width="stretch",
        )


def render_start_tab(catalog) -> None:
    st.markdown("#### How to use")
    st.markdown(
        "1. **Pick a case** below, or open the judge's case.  \n"
        "2. **Read the evidence status** at the top of the case to see gaps and warnings.  \n"
        "3. Open **View evidence for this claim** in the case summary to check its source."
    )

    st.markdown("#### Demo cases")
    demos = [
        ("TCGA-A7-A3RF-01", "Sample with all six data types", "Includes a diagnostic slide."),
        ("TCGA-BH-A8FY-01", "Sample with missing evidence", "No protein data and no diagnostic slide."),
        ("TCGA-A7-A56D-11", "Sample with slides only", "Slides exist, but no clinical or molecular record."),
    ]
    known_ids = set(catalog["sample_id"])
    demo_columns = st.columns(3)
    for column, (demo_id, demo_label, demo_note) in zip(demo_columns, demos):
        if demo_id not in known_ids:
            continue
        with column.container(border=True):
            st.caption(f"{demo_id} · {demo_note}")
            st.button(demo_label, key=f"demo-{demo_id}", on_click=select_case,
                      args=(demo_id,), width="stretch")

    st.markdown("#### Judge case")
    st.caption(
        "Upload the `case_room_case.txt` file from the judge envelope. The file must "
        "contain one sample ID; it does not upload a replacement database."
    )
    judge_file = st.file_uploader("Judge case file", type=["txt"], key="judge-case-file")
    if judge_file is not None:
        try:
            judge_sample_id = parse_judge_case(judge_file.getvalue(), catalog)
        except ValueError as error:
            st.error(str(error))
        else:
            st.success(f"Validated judge sample: {judge_sample_id}")
            st.button(
                "Open judge case",
                key="open-judge-case",
                on_click=select_case,
                args=(judge_sample_id,),
                width="stretch",
            )


def render_browse_tab(catalog) -> None:
    search_column, protein_column, slide_column = st.columns([2, 1, 1])
    search = search_column.text_input(
        "Search sample or patient ID",
        placeholder="For example: TCGA-A7-A3RF-01",
        on_change=reset_page,
    )
    protein_filter = protein_column.selectbox(
        "Protein data",
        ["Any", "Available", "Missing"],
        on_change=reset_page,
    )
    slide_filter = slide_column.selectbox(
        "Slides",
        ["Any", "Diagnostic available", "Any slide available", "No slides"],
        on_change=reset_page,
    )

    sample_type_options = sorted(catalog["sample_type"].dropna().unique().tolist())
    default_types = ["Primary Tumor"] if "Primary Tumor" in sample_type_options else sample_type_options
    sample_types = st.multiselect(
        "Sample type",
        sample_type_options,
        default=default_types,
        on_change=reset_page,
    )

    filtered = filter_sample_catalog(
        catalog,
        search=search,
        sample_types=sample_types,
        protein_filter=protein_filter,
        slide_filter=slide_filter,
    )

    total_results = len(filtered)
    total_pages = max(1, math.ceil(total_results / PAGE_SIZE))
    if "catalog_page" not in st.session_state:
        st.session_state.catalog_page = 1
    st.session_state.catalog_page = min(st.session_state.catalog_page, total_pages)

    summary_columns = st.columns(4)
    summary_columns[0].metric("Matching samples", f"{total_results:,}")
    summary_columns[1].metric("With protein", f"{int(filtered['has_protein'].sum()):,}")
    summary_columns[2].metric(
        "With diagnostic slide", f"{int(filtered['has_diagnostic_slide'].sum()):,}"
    )
    summary_columns[3].metric(
        "Slide-only records", f"{int((~filtered['in_sample_manifest']).sum()):,}"
    )

    if total_results == 0:
        st.warning("No samples match these filters. Try removing a filter or searching another ID.")
        return

    page = st.session_state.catalog_page
    start = (page - 1) * PAGE_SIZE
    stop = min(start + PAGE_SIZE, total_results)
    st.caption(f"Showing {start + 1}–{stop} of {total_results:,} samples")

    page_rows = filtered.iloc[start:stop]
    card_columns = st.columns(3)
    for position, (_, row) in enumerate(page_rows.iterrows()):
        with card_columns[position % 3]:
            render_sample_card(row)

    previous_column, page_column, next_column = st.columns([1, 2, 1])
    if previous_column.button("← Previous", disabled=page <= 1, width="stretch"):
        st.session_state.catalog_page -= 1
        st.rerun()
    page_column.markdown(
        f"<p style='text-align:center'>Page <strong>{page}</strong> of "
        f"<strong>{total_pages}</strong></p>",
        unsafe_allow_html=True,
    )
    if next_column.button("Next →", disabled=page >= total_pages, width="stretch"):
        st.session_state.catalog_page += 1
        st.rerun()


def render_catalog(catalog) -> None:
    st.caption("ONCOSYS · EVIDENCE NAVIGATOR")
    st.title("Multimodal Case Room")
    st.write(
        "Find a tissue sample and see its records, lab measurements, and slides with sources."
    )
    st.info(
        "Research-use prototype. This tool does not diagnose disease, recommend treatment, "
        "or establish clinical validity."
    )
    start_tab, browse_tab = st.tabs(["Start here", "Browse all samples"])
    with start_tab:
        render_start_tab(catalog)
    with browse_tab:
        render_browse_tab(catalog)


def render_linked_source(catalog):
    st.title("Original source record")
    if st.button("Back to case"):
        sample = st.query_params.get("sample")
        st.query_params.clear()
        select_case(sample if sample in catalog["sample_id"].values else None)
        st.rerun()

    sample = st.query_params.get("sample")
    if sample not in catalog["sample_id"].values:
        st.error("This sample is unavailable in the loaded dataset.")
        return
    try:
        evidence = question_evidence(get_case_details(sample))
    except (OSError, KeyError, ValueError) as error:
        st.error(str(error))
        return
    item = evidence.get(st.query_params["source"])
    if not item or not item.get("location"):
        st.error("This source location is unavailable for the selected sample.")
        return
    st.text(item["source"])
    st.text(item["locator"])
    render_original_record(item)


def main() -> None:
    with st.sidebar:
        st.subheader("Claude setup")
        st.link_button("Get a Claude API key ↗", API_KEYS_URL)
        api_key = st.text_input("Claude API key", type="password", key="case_claude_key").strip()
        st.caption("The key stays in this app session. Asking a question sends it and this "
                   "sample’s evidence to Anthropic. API usage may incur charges.")

    try:
        catalog = get_catalog()
    except (FileNotFoundError, ValueError) as error:
        st.error(str(error))
        st.stop()

    if "source" in st.query_params:
        render_linked_source(catalog)
        return

    if "selected_sample_id" not in st.session_state:
        st.session_state.selected_sample_id = None

    if st.session_state.selected_sample_id:
        render_case_detail(catalog, api_key)
    else:
        render_catalog(catalog)


if __name__ == "__main__":
    main()
