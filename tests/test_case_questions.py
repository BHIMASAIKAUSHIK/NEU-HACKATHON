import io
import json
import unittest
from unittest.mock import patch

from src.case_questions import answer_case_question, question_evidence
from src.case_loader import load_case_details


class CaseQuestionsTests(unittest.TestCase):
    def test_missing_case_preserves_source_and_slide_link(self):
        evidence = question_evidence(load_case_details("TCGA-BH-A8FY-01"))
        self.assertTrue(any(entry["links"] for entry in evidence.values()))
        self.assertTrue(any(entry["data"] == {
            "layer": "protein", "selected sample data": None,
        } for entry in evidence.values()))

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
