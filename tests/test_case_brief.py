from __future__ import annotations

import unittest

from src.case_brief import build_case_brief, render_case_brief_markdown
from src.case_loader import load_case_details


class CaseBriefTests(unittest.TestCase):
    def test_complete_case_has_atomic_cited_statements_and_slide_links(self):
        case = load_case_details("TCGA-A7-A3RF-01")
        statements = build_case_brief(case)

        self.assertTrue(statements)
        self.assertTrue(all(item["text"] and item["source"] and item["locator"] for item in statements))
        self.assertTrue(any("Stage IIA" in item["text"] for item in statements))
        self.assertTrue(any("21 genes" in item["text"] for item in statements))
        self.assertTrue(any(item["links"] for item in statements))

        export = render_case_brief_markdown(case, statements)
        self.assertIn("# OncoSys Case Brief: TCGA-A7-A3RF-01", export)
        self.assertIn("clinical.tsv", export)
        self.assertIn("viewer.imaging.datacommons.cancer.gov", export)
        self.assertIn("not a diagnosis", export)

    def test_missing_evidence_is_stated_and_quality_warning_is_preserved(self):
        case = load_case_details("TCGA-BH-A8FY-01")
        statements = build_case_brief(case)
        texts = " ".join(item["text"] for item in statements)

        self.assertIn("Missing data layers: protein", texts)
        self.assertIn("Diagnostic slide missing", texts)
        self.assertIn("2 warnings", texts)

    def test_slide_only_case_does_not_claim_a_clinical_record(self):
        case = load_case_details("TCGA-A7-A56D-11")
        statements = build_case_brief(case)
        texts = " ".join(item["text"] for item in statements)

        self.assertIn("No clinical record", texts)
        self.assertNotIn("Recorded clinical characteristics", texts)

    def test_conflict_statement_is_exported_with_source_rows(self):
        case = load_case_details("TCGA-A7-A3RF-01")
        case["conflicts"] = [
            {
                "id": "clinical-er-status",
                "title": "Conflicting ER clinical status",
                "detail": "Clinical rows contain Positive and Negative ER values.",
                "source": "data/tcga-brca/raw/clinical.tsv",
                "fields": ["ER clinical status"],
                "records": [
                    {"Source row": 10, "Field": "ER clinical status", "Value": "Positive"},
                    {"Source row": 20, "Field": "ER clinical status", "Value": "Negative"},
                ],
            }
        ]
        statements = build_case_brief(case)
        texts = " ".join(item["text"] for item in statements)
        self.assertNotIn("ER: Positive", texts)
        self.assertIn("Conflict preserved", texts)
        export = render_case_brief_markdown(case, statements)
        self.assertIn("source rows=10, 20", export)


if __name__ == "__main__":
    unittest.main()
