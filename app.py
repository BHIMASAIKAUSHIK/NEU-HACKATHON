"""Streamlit landing page for the OncoSys Multimodal Case Room."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from src.case_loader import load_case_details
from src.case_brief import build_case_brief, render_case_brief_markdown
from src.data_loader import DATA_LAYER_COLUMNS, filter_sample_catalog, load_sample_catalog


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
)


@st.cache_data(show_spinner="Loading sample catalog…")
def get_catalog():
    return load_sample_catalog()


def select_case(sample_id: str) -> None:
    st.session_state.selected_sample_id = sample_id


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


def render_case_detail(catalog) -> None:
    sample_id = st.session_state.selected_sample_id
    row = catalog.loc[catalog["sample_id"] == sample_id].iloc[0]

    st.button("← Back to all samples", on_click=clear_case)
    st.caption("MULTIMODAL CASE ROOM · SOURCE-LINKED CASE")
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
        if "quality_checks" not in case:
            get_case_details.clear()
            case = get_case_details(sample_id)
    except (FileNotFoundError, KeyError, ValueError) as error:
        st.error(str(error))
        return

    metric_columns = st.columns(4)
    metric_columns[0].metric("Patient", _display_value(row["patient_id"]))
    metric_columns[1].metric("Sample type", row["sample_type"])
    metric_columns[2].metric("Data layers", f"{row['available_layers']} / 6")
    metric_columns[3].metric("Slides", int(row["total_slides"]))

    st.subheader("Case Summary")
    st.caption(
        "Rule-based evidence brief. Every statement identifies its source; measurements are not "
        "turned into medical conclusions."
    )
    brief_statements = build_case_brief(case)
    with st.container(border=True):
        for statement in brief_statements:
            st.write(statement["text"])
            st.caption(f"Source: `{statement['source']}` · {statement['locator']}")
            if statement["links"]:
                link_columns = st.columns(min(3, len(statement["links"])))
                for index, link in enumerate(statement["links"]):
                    link_columns[index % len(link_columns)].link_button(
                        f"Open {link['label']} ↗", link["url"]
                    )

    brief_markdown = render_case_brief_markdown(case, brief_statements)
    st.download_button(
        "Download Case Brief (.md)",
        data=brief_markdown,
        file_name=f"{sample_id}-case-brief.md",
        mime="text/markdown",
        width="stretch",
    )

    st.subheader("Evidence coverage")
    availability_columns = st.columns(3)
    for index, column in enumerate(DATA_LAYER_COLUMNS):
        status = "Available" if row[column] else "Missing"
        icon = "✅" if row[column] else "—"
        availability_columns[index % 3].write(f"{icon} **{LAYER_LABELS[column]}:** {status}")
    st.caption(f"Source: `{case['sources']['availability']}`")

    if not row["in_sample_manifest"]:
        st.warning(
            "Slides exist for this exact sample ID, but no matching clinical or molecular "
            "record exists in the sample manifest. The app will not attach a different sample."
        )
    elif not row["has_diagnostic_slide"]:
        st.info("No diagnostic slide is linked to this sample. Frozen slides may still be available.")

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
    for check in quality_checks:
        with st.expander(f"{icons[check['status']]} {check['title']}"):
            st.write(check["detail"])
            st.caption(f"Source: `{check['source']}`")
    st.caption(
        "These are data-integrity checks, not medical conclusions. Protein and RNA values "
        "are not labelled abnormal without a documented threshold."
    )

    st.subheader("Clinical record")
    if case["clinical"]:
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
    biomarker_rows = [
        {
            "Biomarker": "ER",
            "Clinical result": _display_value(clinical.get("ER clinical status")),
            "Protein measurement": _display_value(protein.get("ER-alpha")),
        },
        {
            "Biomarker": "PR",
            "Clinical result": _display_value(clinical.get("PR clinical status")),
            "Protein measurement": _display_value(protein.get("PR")),
        },
        {
            "Biomarker": "HER2",
            "Clinical result": _display_value(clinical.get("HER2 clinical status")),
            "Protein measurement": _display_value(protein.get("HER2")),
        },
    ]
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
                for field, value in case["survival"].items()
            ]
            st.dataframe(survival_rows, hide_index=True, width="stretch")
        st.caption(f"Source: `{case['sources']['survival']}`")

    st.subheader("Pathology slides")
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

    st.subheader("Limitations and missing evidence")
    if case["missing"]:
        for item in case["missing"]:
            st.write(f"- {item} is unavailable for this case.")
    else:
        st.write("All catalogued data layers and a diagnostic slide are available for this case.")
    st.caption(
        "Availability does not prove that a measurement is correct or clinically useful. "
        "A qualified human reviewer must interpret the original evidence."
    )


def render_sample_card(row) -> None:
    with st.container(border=True):
        st.markdown(f"#### {row['sample_id']}")
        st.caption(f"{row['sample_type']} · {row['record_status']}")
        st.write(f"**Patient:** {row['patient_id']}")

        available = [LAYER_LABELS[column] for column in DATA_LAYER_COLUMNS if row[column]]
        missing = [LAYER_LABELS[column] for column in DATA_LAYER_COLUMNS if not row[column]]
        st.write(f"**Available:** {', '.join(available) if available else 'None'}")
        if missing:
            st.write(f"**Missing:** {', '.join(missing)}")

        slide_text = f"{int(row['total_slides'])} total"
        if row["diagnostic_slides"]:
            slide_text += f" · {int(row['diagnostic_slides'])} diagnostic"
        elif row["frozen_slides"]:
            slide_text += f" · {int(row['frozen_slides'])} frozen only"
        st.write(f"**Slides:** {slide_text}")

        st.button(
            "View case",
            key=f"view-{row['sample_id']}",
            on_click=select_case,
            args=(row["sample_id"],),
            width="stretch",
        )


def render_catalog(catalog) -> None:
    st.caption("ONCOSYS · EVIDENCE NAVIGATOR")
    st.title("Multimodal Case Room")
    st.write(
        "Browse de-identified TCGA-BRCA samples, see which evidence exists, and open one "
        "case without silently filling its gaps."
    )
    st.info(
        "Research-use prototype. This tool does not diagnose disease, recommend treatment, "
        "or establish clinical validity."
    )

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


def main() -> None:
    try:
        catalog = get_catalog()
    except (FileNotFoundError, ValueError) as error:
        st.error(str(error))
        st.stop()

    if "selected_sample_id" not in st.session_state:
        st.session_state.selected_sample_id = None

    if st.session_state.selected_sample_id:
        render_case_detail(catalog)
    else:
        render_catalog(catalog)


if __name__ == "__main__":
    main()
