# -*- coding: utf-8 -*-
"""加权评分推荐引擎 —— 替代三段拼接选题"""
import random


class WeightedQuestionSampler:
    """五维加权评分，加权随机采样"""

    def __init__(self, candidates, user_state, preference=50):
        """
        candidates: list[dict] — 候选题目
        user_state: st.session_state 或 dict — 用户数据
        preference: int 0~100 — 0=纯新题, 100=纯错题
        """
        self.candidates = candidates
        self.state = user_state
        self.pref = max(0, min(100, preference))
        self.wrong_ids = {str(e["qid"]) for e in user_state.get("wrong_questions", [])}
        self.topic_stats = user_state.get("topic_stats", {})
        self.recent_ids = set()
        for round_ids in user_state.get("recent_pool_ids", [])[-3:]:
            self.recent_ids.update(str(x) for x in round_ids)
        self._topic_total = {}
        for q in candidates:
            t = q.get("topic", q.get("experiment", ""))
            self._topic_total[t] = self._topic_total.get(t, 0) + 1

    def _wrong_bonus(self, q):
        if str(q.get("id")) in self.wrong_ids:
            return 1.0
        return 0.0

    def _importance(self, q):
        diff = int(q.get("difficulty", 1))
        t = q.get("topic", q.get("experiment", ""))
        if "绪论" in str(t):
            return 1.0
        if diff >= 3:
            return 0.8
        return 0.5

    def _coverage_gap(self, q):
        t = q.get("topic", q.get("experiment", ""))
        total = self._topic_total.get(t, 1)
        stat = self.topic_stats.get(t, {})
        done = stat.get("total", 0)
        return 1.0 - min(done / max(total, 1), 1.0)

    def _recent_penalty(self, q):
        if str(q.get("id")) in self.recent_ids:
            return -1.0
        return 0.0

    def _weakness(self, q):
        t = q.get("topic", q.get("experiment", ""))
        stat = self.topic_stats.get(t, {})
        total = stat.get("total", 0)
        if total < 3:
            return 0.5
        acc = stat.get("correct", 0) / total
        if acc >= 0.8:
            return 0.0
        if acc <= 0.5:
            return 1.0
        return (0.8 - acc) / 0.3

    def _score(self, q):
        w_wrong = 0.30 * (self.pref / 100.0)
        w_coverage = 0.20 * (1.0 - self.pref / 100.0) + 0.20
        return (
            w_wrong * self._wrong_bonus(q) +
            0.25 * self._importance(q) +
            w_coverage * self._coverage_gap(q) +
            0.50 * self._recent_penalty(q) +
            0.25 * self._weakness(q)
        )

    def sample(self, n):
        if not self.candidates:
            return []
        scored = [(q, self._score(q)) for q in self.candidates]
        weights = [max(s, 0.01) for _, s in scored]
        total_w = sum(weights)
        if total_w == 0:
            probs = [1.0 / len(scored)] * len(scored)
        else:
            probs = [w / total_w for w in weights]
        n = min(n, len(self.candidates))
        selected = []
        indices = list(range(len(self.candidates)))
        for _ in range(n):
            idx = random.choices(indices, weights=probs, k=1)[0]
            selected.append(self.candidates[idx])
            probs[idx] = 0
            total_w = sum(probs)
            if total_w > 0:
                probs = [p / total_w for p in probs]
        return selected
