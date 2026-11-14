# Multimodal Case Room

OncoSys Cancer AI Lab Hackathon · Track: Evidence Navigator

Demo video: https://drive.google.com/file/d/1I4zKhyIW_n-fTxTkUDNT7HQDNxQHazBY/view?usp=sharing

## What it is

Multimodal Case Room is a Streamlit app for reviewing one TCGA breast cancer case at a time.

You pick a sample. The app pulls together everything that matches that exact sample ID: clinical data, survival, protein, mutations, copy number, RNA and pathology slides. Each slide opens in the NCI viewer.

If a piece of evidence doesn't match the ID, the app leaves it out and tells you it's missing. It never borrows data from a similar-looking sample.

## Who uses it

A research analyst who is picking breast cancer cases for a study.

## The decision

For each case, the analyst needs to answer one question:

> Can I use this case as it is, use it with caveats, or does someone need to check it first?

## Why this is hard without the tool

One case is spread over seven files. The IDs look almost the same:

- `TCGA-BH-A8FY` is the patient
- `TCGA-BH-A8FY-01` is the tumour sample
- `TCGA-BH-A8FY-01A-01-TSA` is a slide

Joining these by hand is slow, and it's easy to get wrong. You can pick the wrong slide or miss a gap. You can also miss two sources that disagree.

## How it works

1. Search for a sample ID, or upload the judge's `case_room_case.txt`.
2. Open the case. The summary at the top lists each fact with its source file and row.
3. Check the 10 data quality checks and the conflicts section.
4. Look at the clinical ER, PR and HER2 results next to the protein values.
5. Read *Limitations and missing evidence* to see what's not there.
6. Download the case brief (Markdown). It keeps all the sources and slide links.

You can also ask Claude questions about the case. Each answer points back to the evidence it used. This step is optional and needs your own API key.

## Demo walkthrough

These are the practice cases from `products/multimodal-case-room/practice_cases.csv`.

| Case | What you see | Decision |
|---|---|---|
| C1 `TCGA-A7-A3RF-01` | All 6 data layers, a diagnostic slide and a frozen slide. 10 of 10 checks pass. | Use it. |
| C4 `TCGA-BH-A1FJ-01` | ER is clinically negative, but its ER protein value (2.27) is higher than three ER-positive cases (1.35 to 1.57). HER2 status is missing. | Needs review. Check the ER result first. |
| C7 `TCGA-BH-A8FY-01` | No protein data. Only a frozen slide, no diagnostic slide. | Use with caveats. |
| C8 `TCGA-A7-A56D-11` | Normal tissue with a slide but no clinical or molecular data. The app won't attach the same patient's tumour sample (`-01`). | Don't use. |

The app shows both ER values side by side for C4. It doesn't flag the mismatch on its own yet, so point it out during the demo.

## Setup

You need Python 3.10 or newer and about 75 MB of disk space.

```bash
git clone https://github.com/BHIMASAIKAUSHIK/NEU-HACKATHON.git
cd NEU-HACKATHON
pip install -r requirements.txt
python data/tcga-brca/fetch.py
streamlit run app.py
```

Then open http://localhost:8501.

Don't skip `fetch.py`. It downloads the data and checks every file against `data/tcga-brca/sources.csv`. Without it, the sample list still loads, but every case shows its data as unavailable.

To run the tests:

```bash
python -m unittest discover -s tests -v
```

On Mac or Linux, use `python3` if `python` doesn't work.

## A result you can check

Open `TCGA-A7-A3RF-01`.

- Clinical: ER positive, PR positive, HER2 negative, Stage IIA. This comes from `data/tcga-brca/raw/clinical.tsv`, row 159.
- Protein: ER-alpha 3.67, PR 0.29, HER2 −1.21. This comes from `data/tcga-brca/raw/protein_rppa.tsv.gz`, column `TCGA-A7-A3RF-01`.
- Slides: `TCGA-A7-A3RF-01Z-00-DX1` (diagnostic) and `TCGA-A7-A3RF-01A-01-TS1` (frozen). These come from `data/tcga-brca/slide_manifest.csv`.

To reproduce the protein values:

```python
import pandas as pd
df = pd.read_csv("data/tcga-brca/raw/protein_rppa.tsv.gz", sep="\t", index_col="Sample_description")
print(df.loc[["ERALPHA", "PR", "HER2"], "TCGA-A7-A3RF-01"])
```

## A limitation you can see

Open `TCGA-BH-A8FY-01`. The app warns that it has no protein data and no diagnostic slide.

Open `TCGA-A7-A56D-11`. The app marks it as slide-only.

The app also has some limits by design:

- It shows recorded values. It doesn't read the slide images.
- It shows protein values without a cutoff, because the data doesn't come with one.
- The quality checks cover coverage and consistency. They can't tell you whether a measurement is correct.

## Safety

- Every case page says it's a research prototype. It gives no diagnosis, treatment advice or risk score.
- Conflicting records stay side by side. The app labels them as needing human review and doesn't pick a winner.
- Claude is told not to diagnose, recommend treatment, predict outcomes or interpret slides. If the evidence can't answer a question, it has to say so.

## Data

We use only the frozen TCGA-BRCA release provided for the event. That covers UCSC Xena files plus slide links from NCI Imaging Data Commons. Sources and checksums are in `data/tcga-brca/sources.csv`, and licences are in `DATA_LICENSES.md`. We didn't add any other data.

## Third-party code

| Package or service | Used for | Licence |
|---|---|---|
| Streamlit | The web app | Apache-2.0 |
| pandas | Loading and joining data | BSD-3-Clause |
| NumPy | Used by pandas | BSD-3-Clause |
| Claude API (Anthropic) | Optional Q&A, with the user's own key | Anthropic terms |

`requirements.txt` also installs packages for the hackathon starter notebooks: matplotlib, Jupyter, jsonschema, Pillow, scikit-learn, idc-index and cryptography. The Case Room app doesn't use them.

## Team

| Name |
|---|
| Ibi | 
| Hardi |
| Purva |
| Kaushik |
