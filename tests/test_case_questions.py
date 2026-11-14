import io
import json
import unittest
from unittest.mock import patch

from src.case_questions import answer_case_question, question_evidence
from src.case_evidence import resolve_sources
from src.case_loader import load_case_details


class CaseQuestionsTests(unittest.TestCase):
    def test_missing_case_preserves_source_and_slide_link(self):
        evidence = question_evidence(load_case_details("TCGA-BH-A8FY-01"))
        self.assertTrue(any(entry["links"] for entry in evidence.values()))
        self.assertTrue(any(entry["source"].endswith("protein_rppa.tsv.gz") and entry["data"].get("matching columns") == 0 for entry in evidence.values()))

    def test_source_coordinates_distinguish_values_missing_columns_and_slide_rows(self):
        complete = question_evidence(load_case_details("TCGA-A7-A3RF-01"))
        stage = complete["clinical-159-pathologic_stage"]
        self.assertIn('row 159 · column "pathologic_stage"', stage["locator"])
        self.assertEqual(stage["data"], {"Pathologic stage": "Stage IIA"})
        self.assertIn('Sample_description="HER2" · column "TCGA-A7-A3RF-01"',
                      complete["protein-HER2"]["locator"])
        self.assertEqual(complete["slide-443"]["data"]["slide_kind"], "diagnostic (FFPE)")

        missing = question_evidence(load_case_details("TCGA-BH-A8FY-01"))
        sources = resolve_sources(missing, ["check-missing-layers", "check-diagnostic-slide"])
        self.assertIn(missing["protein-header"], sources)
        self.assertEqual(missing["protein-header"]["data"]["matching columns"], 0)
        self.assertIn(missing["slide-2040"], sources)
        self.assertEqual(missing["slide-2040"]["data"]["slide_kind"], "frozen, top section")

        slide_only = question_evidence(load_case_details("TCGA-A7-A56D-11"))
        self.assertEqual(slide_only["clinical"]["data"], {"matching records": 0})

    def test_claude_response_must_reference_current_case_evidence(self):
        evidence = {"E1": {"data": {"diagnostic slides": 0}}}
        for source in ("E1", "E99"):
            with self.subTest(source=source):
                answer = [{"text": "No diagnostic slides are listed.", "sources": [source]}]
                response = {"content": [{"type": "text", "text": json.dumps(answer)}]}
                with patch("src.case_questions.urlopen",
                           return_value=io.BytesIO(json.dumps(response).encode())) as send:
                    if source == "E1":
                        self.assertEqual(answer_case_question("test-key", "Any diagnostic slides?", evidence), answer)
                        request = send.call_args.args[0]
                        sent = json.loads(json.loads(request.data)["messages"][0]["content"])
                        self.assertEqual(sent["evidence"], {"E1": {"diagnostic slides": 0}})
                    else:
                        with self.assertRaisesRegex(ValueError, "usable citations"):
                            answer_case_question("test-key", "Any diagnostic slides?", evidence)
