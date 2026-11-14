from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class CaseRoomAppTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        self.assertEqual(len(self.app.exception), 0)

    def test_landing_page_defaults_to_primary_tumors(self):
        self.assertEqual(self.app.title[0].value, "Multimodal Case Room")
        metrics = {metric.label: metric.value for metric in self.app.metric}
        self.assertEqual(metrics["Matching samples"], "1,101")
        self.assertEqual(metrics["Slide-only records"], "0")
        self.assertEqual(len([button for button in self.app.button if button.label == "View case"]), 24)

    def test_search_and_open_missing_data_case(self):
        self.app.text_input[0].set_value("TCGA-BH-A8FY-01").run()
        metrics = {metric.label: metric.value for metric in self.app.metric}
        self.assertEqual(metrics["Matching samples"], "1")

        self.app.button(key="view-TCGA-BH-A8FY-01").click().run()
        self.assertEqual(self.app.title[0].value, "TCGA-BH-A8FY-01")
        self.assertTrue(any(item.value == "Case Summary" for item in self.app.subheader))
        self.assertEqual(len(self.app.get("download_button")), 1)
        self.assertTrue(any("No diagnostic slide" in item.value for item in self.app.info))
        self.assertEqual(len(self.app.exception), 0)

    def test_slide_only_case_is_searchable_when_normal_tissue_is_selected(self):
        self.app.multiselect[0].set_value(["Normal Tissue"]).run()
        self.app.text_input[0].set_value("TCGA-A7-A56D-11").run()
        metrics = {metric.label: metric.value for metric in self.app.metric}
        self.assertEqual(metrics["Matching samples"], "1")
        self.assertEqual(metrics["Slide-only records"], "1")

        self.app.button(key="view-TCGA-A7-A56D-11").click().run()
        self.assertTrue(any("Slides exist" in item.value for item in self.app.warning))
        self.assertEqual(len(self.app.exception), 0)


if __name__ == "__main__":
    unittest.main()
