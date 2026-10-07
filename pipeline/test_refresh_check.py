"""python3 -m unittest discover -s pipeline -p 'test_*.py'"""
import contextlib
import io
import json
import os
import tempfile
import unittest

from pipeline.refresh_check import problems
from pipeline.since import REPOS

FULL = {"since": {}, "DownloadRank": 1, "releases": []}


def write(d, version, counts, rec=FULL):
    for repo in REPOS:
        os.makedirs(f"{d}/{version}/{repo}")
        with open(f"{d}/{version}/{repo}/packages.json", "w") as fh:
            json.dump({f"p{i}": dict(rec) for i in range(counts.get(repo, 100))}, fh)


def check(old, new):
    with contextlib.redirect_stderr(io.StringIO()):
        return problems(old, new)


class RefreshCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old, self.new = f"{self.tmp.name}/old", f"{self.tmp.name}/new"
        write(self.old, "3.24", {})
        os.makedirs(f"{self.old}/site")  # not a release: ignored

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_drop_of_up_to_two_percent_passes(self):
        write(self.new, "3.24", {"bioc": 98})
        self.assertEqual(check(self.old, self.new), [])

    def test_a_larger_drop_in_one_repo_fails(self):
        write(self.new, "3.24", {"workflows": 97})
        self.assertEqual(check(self.old, self.new),
                         ["3.24/workflows: 100 -> 97 packages, more than 2% fewer"])

    def test_a_record_without_a_required_field_fails(self):
        write(self.new, "3.24", {}, rec={"since": {}, "releases": []})
        self.assertEqual(len(check(self.old, self.new)), len(REPOS))
        self.assertIn("3.24/bioc: 100 of 100 records without DownloadRank", check(self.old, self.new))

    def test_a_release_missing_from_the_new_data_fails(self):
        with self.assertRaises(FileNotFoundError):
            check(self.old, self.new)


if __name__ == "__main__":
    unittest.main()
