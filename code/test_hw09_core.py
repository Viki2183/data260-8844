from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hw09.redis_client import PREFIX, make_key, validate_key
from hw09.data_versions import current_or_recorded_version
from hw09.semantic_cache import SemanticCache
from hw09.tests_support import FakeDB, FakeRedis
from hw09.view_counter import VulnerabilityReportViewCounter


class Report:
    id = 1

    def __init__(self):
        self.view_count = 0
        self.updated_at = datetime(2026, 11, 7, 0, 0, 0)


class Hw09CoreTests(unittest.TestCase):
    def test_all_key_builders_use_prefix(self):
        keys = [
            make_key("views:vulnerability_report", 1),
            make_key("semantic_cache:entry", "abc"),
            make_key("semantic_cache:index"),
            make_key("semantic_cache:version", 1),
        ]
        self.assertTrue(all(key.startswith(PREFIX) for key in keys))
        with self.assertRaises(ValueError):
            validate_key("views:bad")

    def test_view_counter_syncs_at_ten_and_twenty(self):
        redis = FakeRedis()
        report = Report()
        db = FakeDB(report)
        counter = VulnerabilityReportViewCounter(redis)
        values = [counter.increment_vulnerability_report_views(db, 1) for _ in range(25)]
        self.assertEqual(values, list(range(1, 26)))
        self.assertEqual(report.view_count, 20)
        self.assertEqual(db.commits, 2)
        self.assertEqual(db.refreshes, 2)

    def test_missing_report_uses_not_found_error(self):
        with self.assertRaisesRegex(LookupError, "Vulnerability report not found"):
            VulnerabilityReportViewCounter(FakeRedis()).increment_vulnerability_report_views(
                FakeDB(None), 404
            )

    def test_missing_report_version_uses_not_found_error(self):
        with self.assertRaisesRegex(LookupError, "Vulnerability report not found"):
            current_or_recorded_version(FakeDB(None), 404, FakeRedis())

    def test_semantic_cache_store_and_hit(self):
        redis = FakeRedis()
        cache = SemanticCache(redis_client=redis, threshold=0.85)
        cache.store("Which versions are affected?", [1.0, 0.0], "2.0 and older", 1, "v1")
        hit, similarity = cache.lookup("Which versions are affected?", [1.0, 0.0], "v1", 1)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["answer"], "2.0 and older")
        self.assertAlmostEqual(similarity, 1.0)
        miss, _ = cache.lookup("unrelated", [0.0, 1.0], "v1", 1)
        self.assertIsNone(miss)

    def test_float32_vector_shape(self):
        vector = SemanticCache._vector_bytes([0.0] * 384)
        self.assertEqual(len(vector), 384 * 4)


if __name__ == "__main__":
    unittest.main()
