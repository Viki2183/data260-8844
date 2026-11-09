"""Small deterministic fakes shared by offline HW9 tests."""

from __future__ import annotations

import json


class FakeRedis:
    def __init__(self):
        self.hw9_test_double = True
        self.hw9_entries = {}
        self.values = {}
        self.sets = {}

    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value
        return True

    def sadd(self, key, value):
        self.sets.setdefault(key, set()).add(value)
        return 1

    def smembers(self, key):
        return self.sets.get(key, set())


class FakeQuery:
    def __init__(self, value):
        self.value = value

    def filter(self, *_args):
        return self

    def first(self):
        return self.value


class FakeDB:
    def __init__(self, report):
        self.report = report
        self.commits = 0
        self.refreshes = 0

    def query(self, _model):
        return FakeQuery(self.report)

    def commit(self):
        self.commits += 1

    def refresh(self, _report):
        self.refreshes += 1
