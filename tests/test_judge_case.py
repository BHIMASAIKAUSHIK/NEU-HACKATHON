from __future__ import annotations

import unittest

from src.data_loader import load_sample_catalog
from src.judge_case import parse_judge_case


class JudgeCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_sample_catalog()

    def test_valid_judge_file_returns_catalogued_sample(self):
        self.assertEqual(
            parse_judge_case(b"TCGA-A7-A3RF-01\n", self.catalog),
            "TCGA-A7-A3RF-01",
        )

    def test_bom_and_lowercase_are_normalised(self):
        contents = "\ufefftcga-bh-a8fy-01\n".encode("utf-8")
        self.assertEqual(parse_judge_case(contents, self.catalog), "TCGA-BH-A8FY-01")

    def test_invalid_format_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid sample ID format"):
            parse_judge_case("not-a-sample", self.catalog)

    def test_unknown_sample_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not present"):
            parse_judge_case("TCGA-ZZ-ZZZZ-01", self.catalog)

    def test_multiple_nonempty_lines_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly one sample ID"):
            parse_judge_case("TCGA-A7-A3RF-01\nTCGA-BH-A8FY-01", self.catalog)


if __name__ == "__main__":
    unittest.main()
