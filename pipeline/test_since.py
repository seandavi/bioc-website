"""python3 -m unittest discover -s pipeline -p 'test_*.py'"""
import json
import os
import tempfile
import unittest

from pipeline.net import packaged_date
from pipeline.packages import apply_downloads
from pipeline.since import history, record, releases
from pipeline.tarballs import to_record

CFG = {
    "devel_version": "3.24",
    "r_ver_for_bioc_ver": {"2.5": "2.10", "2.14": "3.1", "3.23": "4.6", "3.24": "4.6"},
    "release_dates": {"2.5": "10/28/2009", "2.14": "4/14/2014", "3.23": "04/29/2026"},
}


class History(unittest.TestCase):
    def test_first_release_is_the_oldest_older_than_before_in_numeric_order(self):
        with tempfile.TemporaryDirectory() as d:
            for version, names in {"2.5": ["a"], "3.9": ["a", "b"], "3.10": ["b", "c"],
                                   "3.11": ["d"]}.items():
                os.makedirs(f"{d}/{version}/bioc")
                with open(f"{d}/{version}/bioc/packages.json", "w") as fh:
                    json.dump({n: {} for n in names}, fh)
            first, seen, _ = history(d, before="3.11")
        self.assertEqual(first, {"a": "2.5", "b": "3.9", "c": "3.10"})
        self.assertEqual(seen, ["2.5", "3.9", "3.10"])

    def test_repo_per_release_incl_newer_ones_but_not_before_itself(self):
        with tempfile.TemporaryDirectory() as d:
            for version, repo, names in [("3.9", "bioc", ["a", "m"]), ("3.10", "data/annotation", ["m"]),
                                         ("3.11", "bioc", ["a"]), ("3.12", "workflows", ["a"])]:
                os.makedirs(f"{d}/{version}/{repo}")
                with open(f"{d}/{version}/{repo}/packages.json", "w") as fh:
                    json.dump({n: {} for n in names}, fh)
            first, _, where = history(d, before="3.11")
        self.assertEqual(where["m"], {"3.9": "bioc", "3.10": "data/annotation"})
        self.assertEqual(where["a"], {"3.9": "bioc", "3.12": "workflows"})
        self.assertEqual(first, {"a": "3.9", "m": "3.9"})  # 3.12 is newer: no effect on "first"


class Releases(unittest.TestCase):
    def test_newest_first_in_numeric_order_with_the_repo_of_each_release(self):
        where = {"3.9": "bioc", "3.10": "data/annotation", "3.2": "bioc"}
        self.assertEqual(releases(where, "3.11", "data/experiment"),
                         [["3.11", "data/experiment"], ["3.10", "data/annotation"], ["3.9", "bioc"],
                          ["3.2", "bioc"]])

    def test_a_package_new_in_the_release_being_built_lists_only_it(self):
        self.assertEqual(releases({}, "3.24", "bioc"), [["3.24", "bioc"]])

    def test_the_release_being_built_wins_over_stale_data_on_disk(self):
        self.assertEqual(releases({"3.24": "bioc"}, "3.24", "workflows"), [["3.24", "workflows"]])


class Record(unittest.TestCase):
    def test_release_with_r_version_and_iso_date(self):
        self.assertEqual(record("2.14", CFG), {"release": "2.14", "r": "3.1", "date": "2014-04-14"})
        self.assertEqual(record("3.23", CFG)["date"], "2026-04-29")

    def test_earliest_release_reads_or_earlier(self):
        self.assertTrue(record("2.5", CFG)["orEarlier"])
        self.assertNotIn("orEarlier", record("2.14", CFG))

    def test_devel_has_no_date_yet(self):
        self.assertEqual(record("3.24", CFG), {"release": "3.24", "r": "4.6"})

    def test_a_release_missing_from_config_is_an_error(self):
        with self.assertRaises(SystemExit):
            record("3.0", CFG)  # no R version
        with self.assertRaises(SystemExit):
            record("3.23", {**CFG, "release_dates": {}})  # released, no date


class Packaged(unittest.TestCase):
    def test_tarball_text_and_runiverse_dict_both_become_a_date(self):
        self.assertEqual(packaged_date("2026-09-29 07:42:20 UTC; biocbuild"), "2026-09-29")
        self.assertEqual(packaged_date({"Date": "2026-09-29 07:42:20 UTC", "User": "root"}), "2026-09-29")

    def test_absent_or_unparseable_is_none(self):
        self.assertIsNone(packaged_date(None))
        self.assertIsNone(packaged_date("yesterday"))

    def test_tarball_record_carries_packaged_as_a_date(self):
        dcf = {"Package": "x", "Version": "1.0", "Packaged": "2026-09-29 07:42:20 UTC; biocbuild"}
        self.assertEqual(to_record(dcf, "devel")["Packaged"], "2026-09-29")
        self.assertNotIn("Packaged", to_record({"Package": "x", "Version": "1.0"}, "devel"))

    def test_dropped_when_the_version_shown_is_not_the_one_it_dates(self):
        idx = {"source.ver": {"CelliD": "1.19.0", "limma": "3.68.5"}, "win.binary.ver": {},
               "mac.binary.sonoma-arm64.ver": {}, "mac.binary.big-sur-x86_64.ver": {}}
        pkgs = {"CelliD": {"Version": "1.20.0", "Packaged": "2026-09-29"},
                "limma": {"Version": "3.68.5", "Packaged": "2026-09-29"}}
        apply_downloads(pkgs, idx, "4.6")
        self.assertNotIn("Packaged", pkgs["CelliD"])
        self.assertEqual(pkgs["limma"]["Packaged"], "2026-09-29")


if __name__ == "__main__":
    unittest.main()
