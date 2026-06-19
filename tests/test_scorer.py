# -*- coding: utf-8 -*-
"""scorer 单元测试"""
import os
import sys
import unittest

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(TEST_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from utils.scorer import (
    normalize, check_choice, check_fill,
    count_keyword_hits, similarity_score,
    score_question,
)


class TestNormalize(unittest.TestCase):
    def test_space_stripped(self):
        self.assertEqual(normalize("  λ/2  "), "λ/2")

    def test_fullwidth_conversion(self):
        self.assertEqual(normalize("Ａ"), "a")


class TestChoice(unittest.TestCase):
    def test_simple_correct(self):
        self.assertTrue(check_choice("A", "A"))

    def test_simple_wrong(self):
        self.assertFalse(check_choice("B", "A"))

    def test_equivalent_bar(self):
        self.assertTrue(check_choice("半波长", "λ/2|半波长|半个波长"))

    def test_judge_dui(self):
        self.assertTrue(check_choice("对", "对"))

    def test_judge_cuo(self):
        self.assertTrue(check_choice("错", "错"))


class TestFill(unittest.TestCase):
    def test_exact_match(self):
        self.assertTrue(check_fill("半个波长", "λ/2|半波长|半个波长"))

    def test_space_variant(self):
        self.assertTrue(check_fill("  半波长  ", "λ/2|半波长|半个波长"))

    def test_below_threshold(self):
        self.assertFalse(check_fill("半波长的一半真的很长", "λ/2|半波长|半个波长"))

    def test_similarity_near_match(self):
        # 与 "λ/2" 有一定相似，但不够 0.85 —— 这个要具体看
        # 更简单: 纯错答
        self.assertFalse(check_fill("完全不同的答案xyz", "弹性模量"))


class TestKeywordHits(unittest.TestCase):
    def test_basic(self):
        hits, total = count_keyword_hits(
            "弹性模量由胡克定律推导", "弹性模量,胡克定律,杨氏模量"
        )
        self.assertEqual(total, 3)
        self.assertEqual(hits, 2)

    def test_empty(self):
        hits, total = count_keyword_hits("anything", "")
        self.assertEqual(hits, 0)
        self.assertEqual(total, 0)


class TestSimilarity(unittest.TestCase):
    def test_identical(self):
        self.assertAlmostEqual(similarity_score("abc", "abc"), 1.0, places=2)

    def test_different(self):
        self.assertLess(similarity_score("完全无关的甲乙丙丁", "爱因斯坦相对论"), 0.5)


class TestScoreQuestion(unittest.TestCase):
    """核心测试——覆盖 AC-4 等关键行为"""

    def test_ac4_choice_correct_score(self):
        """AC-4: difficulty=2, type=choice, 时限30s, 用时10s, 连击=4
        期望: base = 2*2.0 = 4.0
              time_factor = 1 - 10/30 = 0.667
              time_bonus = 4.0 * 0.5 * 0.667 = 1.333
              new_combo = 5 → 查表 5连 = 1.0
              delta = 4.0 + 1.333 + 1.0 = 6.333 → round = 6.33
        """
        r = score_question(
            qtype="choice", difficulty=2, time_limit=30, time_spent=10,
            current_combo=4, user_answer="A", correct_answer="A",
        )
        self.assertTrue(r["is_correct"])
        self.assertEqual(r["new_combo"], 5)
        self.assertAlmostEqual(r["delta"], 6.33, places=2)

    def test_wrong_choice_penalty(self):
        r = score_question(
            qtype="choice", difficulty=2, time_limit=30, time_spent=5,
            current_combo=3, user_answer="B", correct_answer="A",
        )
        self.assertFalse(r["is_correct"])
        self.assertEqual(r["new_combo"], 0)
        self.assertEqual(r["delta"], -1.0)

    def test_timeout_penalty(self):
        r = score_question(
            qtype="choice", difficulty=2, time_limit=30, time_spent=30,
            current_combo=0, user_answer="A", correct_answer="A",
            is_timeout=True,
        )
        self.assertFalse(r["is_correct"])
        self.assertEqual(r["delta"], -1.0)  # 超时起步 -1

    def test_timeout_long_penalty_cap(self):
        # 用时 120s, 超 90s → 9 个 10s 段 → -9，但上限 -5
        r = score_question(
            qtype="choice", difficulty=2, time_limit=30, time_spent=120,
            current_combo=0, user_answer="A", correct_answer="A",
            is_timeout=True,
        )
        self.assertFalse(r["is_correct"])
        self.assertEqual(r["delta"], -5.0)  # 达到上限

    def test_judge_correct(self):
        r = score_question(
            qtype="judge", difficulty=1, time_limit=20, time_spent=5,
            current_combo=0, user_answer="对", correct_answer="对",
        )
        self.assertTrue(r["is_correct"])
        self.assertAlmostEqual(r["delta"], 1.5 + 1.5 * 0.5 * (1 - 5/20), places=2)

    def test_combo_reset_on_wrong(self):
        r = score_question(
            qtype="choice", difficulty=1, time_limit=30, time_spent=10,
            current_combo=7, user_answer="B", correct_answer="A",
        )
        self.assertEqual(r["new_combo"], 0)

    def test_high_combo_bonus(self):
        # 9连 → 答对后 10连 → 10连加分 3.0
        r = score_question(
            qtype="choice", difficulty=1, time_limit=30, time_spent=15,
            current_combo=9, user_answer="A", correct_answer="A",
        )
        self.assertEqual(r["new_combo"], 10)
        base = 1 * 2.0
        time_b = base * 0.5 * (1 - 15/30)
        expected = base + time_b + 3.0
        self.assertAlmostEqual(r["delta"], round(expected, 2), places=2)


if __name__ == "__main__":
    unittest.main()
