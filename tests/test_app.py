from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


class CaseRoomAppTests(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
        self.assertEqual(len(self.app.exception), 0)

    def test_landing_page_defaults_to_primary_tumors(self):
        self.assertEqual(self.app.title[0].value, "Multimodal Case Room")
        self.assertEqual(len(self.app.file_uploader), 1)
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
        self.assertTrue(any(item.value == "Some evidence is missing" for item in self.app.subheader))
        next(button for button in self.app.button if button.label == "Review gaps and conflicts").click().run()
        self.assertTrue(any(item.value == "Conflicting evidence" for item in self.app.subheader))
        self.assertTrue(any("No diagnostic slide" in item.value for item in self.app.info))
        self.assertEqual(len(self.app.exception), 0)

    def test_slide_only_case_is_searchable_when_normal_tissue_is_selected(self):
        self.app.multiselect[0].set_value(["Normal Tissue"]).run()
        self.app.text_input[0].set_value("TCGA-A7-A56D-11").run()
        metrics = {metric.label: metric.value for metric in self.app.metric}
        self.assertEqual(metrics["Matching samples"], "1")
        self.assertEqual(metrics["Slide-only records"], "1")

        self.app.button(key="view-TCGA-A7-A56D-11").click().run()
        self.app.radio(key="case_section").set_value("Data checks").run()
        self.assertTrue(any("Slides exist" in item.value for item in self.app.warning))
        self.assertEqual(len(self.app.exception), 0)

    def test_generated_overview_exports_same_draft_and_preserves_review_notes(self):
        self.app.text_input(key="case_claude_key").set_value("test-key").run()
        next(button for button in self.app.button
             if button.label == "Sample with missing evidence").click().run()
        from src.case_brief import render_case_brief_markdown

        with patch("src.case_questions.urlopen") as send, patch(
            "src.case_brief.render_case_brief_markdown", wraps=render_case_brief_markdown
        ) as export:
            import io
            import json

            draft = "The clinical record lists Stage IA."
            from src.case_evidence import question_evidence
            from src.case_loader import load_case_details

            evidence = question_evidence(load_case_details("TCGA-BH-A8FY-01"))
            source = next(ref for ref in evidence if ref.endswith("-pathologic_stage"))
            response = {"content": [{"type": "text", "text": json.dumps([
                {"text": draft, "sources": [source]},
            ])}]}
            send.return_value = io.BytesIO(json.dumps(response).encode())
            next(button for button in self.app.button
                 if button.label == "Generate cited brief").click().run()
            self.assertIn(draft, [item.value for item in self.app.text])
            markdown = render_case_brief_markdown(*export.call_args.args)
            self.assertIn(draft, markdown)
            self.assertIn('column "pathologic_stage"', markdown)
            self.assertIn("Missing data layers: protein", markdown)
            self.assertIn("Diagnostic slide missing", markdown)
            self.assertIn("viewer.imaging.datacommons.cancer.gov", markdown)
            self.assertEqual(len(self.app.exception), 0)


if __name__ == "__main__":
    unittest.main()
