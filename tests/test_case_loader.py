from __future__ import annotations

import unittest

from src.case_loader import load_case_details


class CaseLoaderTests(unittest.TestCase):
    def test_complete_case_loads_exact_source_backed_details(self):
        case = load_case_details("TCGA-A7-A3RF-01")
        self.assertEqual(case["sample_id"], "TCGA-A7-A3RF-01")
        self.assertEqual(case["clinical"]["ER clinical status"], "Positive")
        self.assertIsNotNone(case["protein"]["ER-alpha"])
        self.assertGreater(len(case["mutations"]), 0)
        self.assertEqual(len(case["copy_number"]), 6)
        self.assertEqual(len(case["rna"]), 6)
        self.assertTrue(any("diagnostic" in slide["slide_kind"] for slide in case["slides"]))
        statuses = {check["id"]: check["status"] for check in case["quality_checks"]}
        self.assertEqual(statuses["clinical-row-count"], "pass")
        self.assertEqual(statuses["molecular-column-links"], "pass")
        self.assertEqual(statuses["slide-duplicates"], "pass")
        self.assertEqual(statuses["diagnostic-slide"], "pass")

    def test_missing_protein_and_diagnostic_slide_are_explicit(self):
        case = load_case_details("TCGA-BH-A8FY-01", include_large_layers=False)
        self.assertIsNone(case["protein"])
        self.assertIn("Protein", case["missing"])
        self.assertIn("Diagnostic Slide", case["missing"])
        self.assertTrue(case["slides"])
        self.assertTrue(all("frozen" in slide["slide_kind"] for slide in case["slides"]))
        statuses = {check["id"]: check["status"] for check in case["quality_checks"]}
        self.assertEqual(statuses["missing-layers"], "warning")
        self.assertEqual(statuses["diagnostic-slide"], "warning")

    def test_slide_only_case_refuses_to_attach_other_records(self):
        case = load_case_details("TCGA-A7-A56D-11", include_large_layers=False)
        self.assertEqual(case["record_status"], "Slide-only record")
        self.assertIsNone(case["clinical"])
        self.assertIsNone(case["protein"])
        self.assertEqual(len(case["slides"]), 5)
        statuses = {check["id"]: check["status"] for check in case["quality_checks"]}
        self.assertEqual(statuses["manifest-link"], "warning")
        self.assertEqual(statuses["clinical-row-count"], "warning")

    def test_unknown_sample_is_rejected(self):
        with self.assertRaises(KeyError):
            load_case_details("TCGA-NOT-A-REAL-01", include_large_layers=False)


if __name__ == "__main__":
    unittest.main()
