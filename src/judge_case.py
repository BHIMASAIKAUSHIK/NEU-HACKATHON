"""Parse the judge-selected sample ID from ``case_room_case.txt``."""

from __future__ import annotations

import re

import pandas as pd


SAMPLE_ID_PATTERN = re.compile(r"^TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}-[0-9]{2}$")


def parse_judge_case(contents: bytes | str, catalog: pd.DataFrame) -> str:
    """Validate and return the exact sample ID contained in a judge file."""

    if isinstance(contents, bytes):
        if len(contents) > 10_000:
            raise ValueError("Judge case file is unexpectedly large; upload case_room_case.txt only.")
        try:
            text = contents.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("Judge case file must be UTF-8 text.") from error
    else:
        text = contents

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError("Judge case file must contain exactly one sample ID on one line.")

    sample_id = lines[0].upper()
    if not SAMPLE_ID_PATTERN.fullmatch(sample_id):
        raise ValueError(
            "Invalid sample ID format. Expected a value like TCGA-A7-A3RF-01."
        )

    available_ids = set(catalog["sample_id"].dropna().astype(str))
    if sample_id not in available_ids:
        raise ValueError(f"Sample ID {sample_id} is not present in the loaded manifests.")
    return sample_id
