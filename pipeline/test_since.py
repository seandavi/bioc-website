"""python3 -m unittest discover -s pipeline -p 'test_*.py'"""
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from pipeline.net import commit_date, packaged_date
from pipeline.packages import apply_downloads, from_runiverse
from pipeline.since import history, manifest_first, manifest_lists, missing, record, releases
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


class Missing(unittest.TestCase):
    CFG = {"r_ver_for_bioc_ver": {v: "x" for v in ("1.6", "2.5", "2.6", "3.0", "3.10", "3.11", "3.12")}}

    def test_every_config_release_from_2_5_up_to_before_must_be_on_disk(self):
        self.assertEqual(missing(["2.5", "3.0", "3.11"], self.CFG, "3.12"), ["2.6", "3.10"])
        self.assertEqual(missing(["2.5", "2.6", "3.0", "3.10", "3.11"], self.CFG, "3.12"), [])

    def test_no_2_5_is_a_gap_and_older_or_newer_releases_are_not(self):
        self.assertEqual(missing(["3.0", "3.10"], self.CFG, "3.11"), ["2.5", "2.6"])
        self.assertEqual(missing([], self.CFG, "2.5"), [])

    def test_a_release_dir_without_packages_is_not_on_disk(self):
        with tempfile.TemporaryDirectory() as d:
            for version, names in {"2.5": ["a"], "2.6": [], "3.0": ["a"]}.items():
                os.makedirs(f"{d}/{version}/bioc")
                with open(f"{d}/{version}/bioc/packages.json", "w") as fh:
                    json.dump({n: {} for n in names}, fh)
            os.makedirs(f"{d}/3.1")  # no packages.json at all
            _, seen, _ = history(d, before="3.2")
        self.assertEqual(seen, ["2.5", "3.0"])
        self.assertEqual(missing(seen, self.CFG, "3.10"), ["2.6"])


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


    def test_manifest_history_reads_or_earlier_at_1_6_only(self):
        cfg = {**CFG, "r_ver_for_bioc_ver": {**CFG["r_ver_for_bioc_ver"], "1.6": "2.1"},
               "release_dates": {**CFG["release_dates"], "1.6": "5/18/2005"}}
        self.assertEqual(record("1.6", cfg, "1.6"),
                         {"release": "1.6", "r": "2.1", "date": "2005-05-18", "orEarlier": True})
        self.assertNotIn("orEarlier", record("2.5", cfg, "1.6"))


class Manifest(unittest.TestCase):
    def test_first_is_the_oldest_release_listing_the_package_in_numeric_order(self):
        lists = {"3.10": "Package: b\n\nPackage: c\n", "1.6": "## comment\nPackage: a \n",
                 "3.9": "Package: a\nPackage: b\n", "3.24": "Package: d\n"}
        self.assertEqual(manifest_first(lists), {"a": "1.6", "b": "3.9", "c": "3.10", "d": "3.24"})

    def test_lists_reads_software_txt_per_release_branch_and_devel(self):
        def git(*a):
            subprocess.run(["git", "-C", d, *a], check=True, capture_output=True)
        with tempfile.TemporaryDirectory() as d:
            git("init", "-q", "-b", "devel")
            git("config", "user.email", "t@example.org")
            git("config", "user.name", "t")
            for branch, text in [("devel", "Package: new\n"), ("RELEASE_1_6", "Package: old\n")]:
                git("checkout", "-q", "-B", branch)
                with open(f"{d}/software.txt", "w") as fh:
                    fh.write(text)
                git("add", "software.txt")
                git("commit", "-q", "-m", branch)
            cfg = {"devel_version": "3.24", "release_dates": {"1.5": "x", "1.6": "x"}}
            self.assertEqual(manifest_lists(cfg, url=f"file://{d}"),
                             {"1.6": "Package: old\n", "3.24": "Package: new\n"})


class Packaged(unittest.TestCase):
    def test_tarball_text_and_runiverse_dict_both_become_a_date(self):
        self.assertEqual(packaged_date("2026-09-29 07:42:20 UTC; biocbuild"), "2026-09-29")
        self.assertEqual(packaged_date({"Date": "2026-09-29 07:42:20 UTC", "User": "root"}), "2026-09-29")

    def test_absent_or_unparseable_is_none(self):
        self.assertIsNone(packaged_date(None))
        self.assertIsNone(packaged_date("yesterday"))

    def test_commit_time_becomes_a_utc_date(self):
        self.assertEqual(commit_date(1786233599), "2026-08-08")  # 23:59:59 UTC
        self.assertEqual(commit_date(1786233600), "2026-08-09")  # 00:00:00 UTC
        self.assertIsNone(commit_date(None))

    def test_tarball_record_carries_packaged_as_updated(self):
        dcf = {"Package": "x", "Version": "1.0", "Packaged": "2026-09-29 07:42:20 UTC; biocbuild"}
        rec = to_record(dcf, "devel")
        self.assertEqual(rec["Updated"], "2026-09-29")
        self.assertNotIn("Packaged", rec)
        self.assertNotIn("Updated", to_record({"Package": "x", "Version": "1.0"}, "devel"))

    def test_runiverse_record_is_dated_by_its_commit_not_its_rebuild(self):
        pkg = {"Package": "limma", "Version": "3.68.5", "Packaged": {"Date": "2026-09-09 01:00:00 UTC"},
               "_commit": {"time": 1786233600}}
        with mock.patch("pipeline.packages.fetch", return_value=json.dumps([pkg])):
            rec = from_runiverse("bioc-release", "RELEASE_3_23")["limma"]
        self.assertEqual(rec["Updated"], "2026-08-09")
        self.assertNotIn("Packaged", rec)

    def test_dropped_when_the_version_shown_is_not_the_one_it_dates(self):
        idx = {"source.ver": {"CelliD": "1.19.0", "limma": "3.68.5"}, "win.binary.ver": {},
               "mac.binary.sonoma-arm64.ver": {}, "mac.binary.big-sur-x86_64.ver": {}}
        pkgs = {"CelliD": {"Version": "1.20.0", "Updated": "2026-09-29"},
                "limma": {"Version": "3.68.5", "Updated": "2026-09-29"}}
        apply_downloads(pkgs, idx, "4.6")
        self.assertNotIn("Updated", pkgs["CelliD"])
        self.assertEqual(pkgs["limma"]["Updated"], "2026-09-29")


if __name__ == "__main__":
    unittest.main()
