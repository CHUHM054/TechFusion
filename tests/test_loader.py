# -*- coding: utf-8 -*-
import os
import sys
import unittest

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(TEST_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from utils.question_loader import load_questions, sample_questions
from utils.validate_csv import validate


class TestLoader(unittest.TestCase):
    def test_load_returns_dataframe(self):
        df = load_questions()
        self.assertGreater(len(df), 0)
        self.assertIn("type", df.columns)
        self.assertIn("question", df.columns)

    def test_sample_returns_list_of_dicts(self):
        pool = sample_questions(n=5, seed=42)
        self.assertEqual(len(pool), 5)
        for q in pool:
            self.assertIsInstance(q, dict)
            self.assertIn("type", q)
            self.assertIn("question", q)

    def test_sample_filter_by_type(self):
        pool = sample_questions(n=10, types=["choice"], seed=42)
        if pool:
            for q in pool:
                self.assertEqual(q["type"], "choice")


class TestValidate(unittest.TestCase):
    def test_valid_csv(self):
        csv_path = os.path.join(APP_DIR, "data", "subjects", "物理实验", "questions.csv")
        errors, total, experiments = validate(csv_path)
        self.assertEqual(len(errors), 0, f"errors: {errors}")
        self.assertGreater(total, 0)


if __name__ == "__main__":
    unittest.main()
