# -*- coding: utf-8 -*-
import json
import os
import shutil
import sys
import tempfile
import unittest

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(TEST_DIR)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import config as _config
_ORIG_DIR = _config.SESSION_DIR
_ORIG_FILE = _config.SESSION_FILE

import utils.storage as _storage


class TestStorageBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="quiz_test_")
        _storage.SESSION_DIR = self.tmp
        _storage.SESSION_FILE = os.path.join(self.tmp, "session.json")
        _storage.ARCHIVES_DIR = os.path.join(self.tmp, "archives")
        _storage.ARCHIVES_META_FILE = os.path.join(self.tmp, "archives_meta.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestBasic(TestStorageBase):
    def test_load_empty_returns_none(self):
        self.assertIsNone(_storage.load_session())

    def test_save_creates_file(self):
        _storage.save_session({"total_score": 42.0})
        self.assertTrue(os.path.exists(_storage.SESSION_FILE))

    def test_save_and_load_roundtrip(self):
        original = {
            "total_score": 42.5,
            "total_correct": 10,
            "total_wrong": 3,
            "total_questions": 13,
            "max_combo_ever": 7,
            "topic_stats": {"绪论": {"correct": 3, "wrong": 1, "timeout": 0, "total": 4}},
            "wrong_questions": [],
            "round_history": [],
        }
        _storage.save_session(original)
        loaded = _storage.load_session()
        self.assertIsNotNone(loaded)
        self.assertAlmostEqual(loaded["total_score"], 42.5, places=2)
        self.assertEqual(loaded["max_combo_ever"], 7)
        self.assertEqual(loaded["topic_stats"]["绪论"]["correct"], 3)

    def test_corrupted_file_returns_none(self):
        with open(_storage.SESSION_FILE, "w", encoding="utf-8") as f:
            f.write("not valid json {")
        self.assertIsNone(_storage.load_session())

    def test_default_fields_injected(self):
        minimal = {"total_score": 1.0}
        _storage.save_session(minimal)
        loaded = _storage.load_session()
        for k in ("wrong_questions", "round_history", "topic_stats"):
            self.assertIn(k, loaded)


class TestWrongBook(TestStorageBase):
    def test_add_first_wrong(self):
        state = dict(_storage.DEFAULT_SESSION)
        state["wrong_questions"] = []
        _storage.add_wrong_question(state, "q1", "题目1", "A", "B", "绪论")
        self.assertEqual(len(state["wrong_questions"]), 1)
        self.assertEqual(state["wrong_questions"][0]["wrong_count"], 1)

    def test_add_duplicate_increments_count(self):
        state = dict(_storage.DEFAULT_SESSION)
        state["wrong_questions"] = []
        _storage.add_wrong_question(state, "q1", "题目", "A", "B", "绪论")
        _storage.add_wrong_question(state, "q1", "题目", "C", "B", "绪论")
        self.assertEqual(len(state["wrong_questions"]), 1)
        self.assertEqual(state["wrong_questions"][0]["wrong_count"], 2)

    def test_remove_wrong(self):
        state = dict(_storage.DEFAULT_SESSION)
        state["wrong_questions"] = []
        _storage.add_wrong_question(state, "q1", "t", "A", "B", "绪论")
        _storage.remove_wrong_question(state, "q1")
        self.assertEqual(len(state["wrong_questions"]), 0)

    def test_is_wrong_check(self):
        state = dict(_storage.DEFAULT_SESSION)
        state["wrong_questions"] = []
        _storage.add_wrong_question(state, "q1", "t", "A", "B", "绪论")
        self.assertTrue(_storage.is_wrong_question(state, "q1"))
        self.assertFalse(_storage.is_wrong_question(state, "q999"))


class TestExperimentStats(TestStorageBase):
    def test_new_experiment(self):
        state = dict(_storage.DEFAULT_SESSION)
        state["topic_stats"] = {}
        _storage.update_topic_stats(state, "绪论", True)
        self.assertEqual(state["topic_stats"]["绪论"]["correct"], 1)
        self.assertEqual(state["topic_stats"]["绪论"]["total"], 1)

    def test_wrong_increments_wrong(self):
        state = dict(_storage.DEFAULT_SESSION)
        state["topic_stats"] = {}
        _storage.update_topic_stats(state, "绪论", False)
        self.assertEqual(state["topic_stats"]["绪论"]["wrong"], 1)

    def test_timeout_flag(self):
        state = dict(_storage.DEFAULT_SESSION)
        state["topic_stats"] = {}
        _storage.update_topic_stats(state, "绪论", False, is_timeout=True)
        self.assertEqual(state["topic_stats"]["绪论"]["timeout"], 1)


class TestRoundHistory(TestStorageBase):
    def test_add_history(self):
        state = dict(_storage.DEFAULT_SESSION)
        state["round_history"] = []
        _storage.add_round_history(state, "diligence", 10.5, 80.0, 3, 10)
        self.assertEqual(len(state["round_history"]), 1)
        self.assertEqual(state["round_history"][0]["score"], 10.5)
        self.assertEqual(state["round_history"][0]["mode"], "diligence")


if __name__ == "__main__":
    unittest.main()
