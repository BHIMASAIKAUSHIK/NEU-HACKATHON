from __future__ import annotations

import unittest

from src.data_loader import filter_sample_catalog, load_sample_catalog


class SampleCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_sample_catalog()

    def test_catalog_keeps_union_of_sample_and_slide_manifests(self):
        self.assertEqual(len(self.catalog), 1271)
        self.assertEqual(self.catalog["sample_id"].nunique(), 1271)

    def test_complete_practice_case_has_expected_coverage(self):
        row = self.catalog[self.catalog["sample_id"] == "TCGA-A7-A3RF-01"].iloc[0]
        self.assertTrue(row["in_clinical"])
        self.assertTrue(row["has_protein"])
        self.assertEqual(row["diagnostic_slides"], 1)
        self.assertEqual(row["available_layers"], 6)

    def test_missing_data_practice_case_stays_visible(self):
        row = self.catalog[self.catalog["sample_id"] == "TCGA-BH-A8FY-01"].iloc[0]
        self.assertFalse(row["has_protein"])
        self.assertEqual(row["diagnostic_slides"], 0)
        self.assertGreater(row["frozen_slides"], 0)

    def test_slide_only_practice_case_is_not_dropped(self):
        row = self.catalog[self.catalog["sample_id"] == "TCGA-A7-A56D-11"].iloc[0]
        self.assertFalse(row["in_sample_manifest"])
        self.assertEqual(row["sample_type"], "Normal Tissue")
        self.assertEqual(row["total_slides"], 5)
        self.assertEqual(row["record_status"], "Slide-only record")

    def test_search_matches_patient_or_sample_id(self):
        by_sample = filter_sample_catalog(self.catalog, search="A3RF")
        by_patient = filter_sample_catalog(self.catalog, search="TCGA-A7-A3RF")
        self.assertIn("TCGA-A7-A3RF-01", set(by_sample["sample_id"]))
        self.assertIn("TCGA-A7-A3RF-01", set(by_patient["sample_id"]))

    def test_filters_primary_tumors_with_protein_and_diagnostic_slide(self):
        filtered = filter_sample_catalog(
            self.catalog,
            sample_types=["Primary Tumor"],
            protein_filter="Available",
            slide_filter="Diagnostic available",
        )
        self.assertFalse(filtered.empty)
        self.assertTrue(filtered["has_protein"].all())
        self.assertTrue(filtered["has_diagnostic_slide"].all())
        self.assertEqual(set(filtered["sample_type"]), {"Primary Tumor"})


if __name__ == "__main__":
    unittest.main()
