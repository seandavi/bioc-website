"""python3 -m unittest discover -s pipeline -p 'test_*.py'"""
import json
import unittest
from unittest import mock

from pipeline import packages

from pipeline.packages import apply_downloads, bin_dirs


def index(src, win=None, arm=None, x86=None):
    return {"source.ver": src, "win.binary.ver": win or {},
            "mac.binary.sonoma-arm64.ver": arm or {}, "mac.binary.big-sur-x86_64.ver": x86 or {}}


class FromRuniverse(unittest.TestCase):
    def records(self, published):
        # The bioc universe lists a data package (ALL) alongside software.
        universe = json.dumps([{"Package": "limma", "Version": "3.68.5"},
                               {"Package": "ALL", "Version": "1.54.0"}])
        with mock.patch("pipeline.packages.fetch", return_value=universe):
            return packages.from_runiverse("bioc", "devel", published)

    def test_packages_the_software_repository_does_not_publish_are_dropped(self):
        self.assertEqual(list(self.records({"limma": "3.68.5"})), ["limma"])

    def test_nothing_is_added_for_published_names_missing_from_the_universe(self):
        self.assertEqual(list(self.records({"limma": "3.68.5", "Ularcirc": "1.30.0"})), ["limma"])


class ApplyDownloads(unittest.TestCase):
    def test_links_every_binary_the_repository_serves(self):
        pkgs = {"limma": {"Version": "3.68.5", "source.ver": "src/contrib/limma_3.68.5.tar.gz"}}
        v = {"limma": "3.68.5"}
        apply_downloads(pkgs, index(v, v, v, v), "4.6")
        r = pkgs["limma"]
        self.assertEqual(r["win.binary.ver"], "bin/windows/contrib/4.6/limma_3.68.5.zip")
        self.assertEqual(r["mac.binary.sonoma-arm64.ver"], "bin/macosx/sonoma-arm64/contrib/4.6/limma_3.68.5.tgz")
        self.assertEqual(r["mac.binary.big-sur-x86_64.ver"], "bin/macosx/big-sur-x86_64/contrib/4.6/limma_3.68.5.tgz")

    def test_version_comes_from_the_repository_not_the_metadata_origin(self):
        # CelliD, 2026-09-29: r-universe built 1.20.0; bioconductor.org 3.23 serves 1.19.0.
        pkgs = {"CelliD": {"Version": "1.20.0", "source.ver": "src/contrib/CelliD_1.20.0.tar.gz"}}
        corrected, unserved = apply_downloads(pkgs, index({"CelliD": "1.19.0"}), "4.6")
        self.assertEqual(pkgs["CelliD"]["Version"], "1.19.0")
        self.assertEqual(pkgs["CelliD"]["source.ver"], "src/contrib/CelliD_1.19.0.tar.gz")
        self.assertEqual(corrected, {"CelliD": "1.20.0"})
        self.assertEqual(unserved, [])

    def test_binary_links_at_its_own_version_and_absent_ones_are_omitted(self):
        # KEGGREST: the Windows binary trails the source; no macOS binaries listed.
        pkgs = {"KEGGREST": {"Version": "1.52.2"}}
        apply_downloads(pkgs, index({"KEGGREST": "1.52.2"}, win={"KEGGREST": "1.51.1"}), "4.6")
        r = pkgs["KEGGREST"]
        self.assertEqual(r["win.binary.ver"], "bin/windows/contrib/4.6/KEGGREST_1.51.1.zip")
        self.assertNotIn("mac.binary.sonoma-arm64.ver", r)
        self.assertNotIn("mac.binary.big-sur-x86_64.ver", r)

    def test_a_package_the_repository_does_not_serve_gets_no_download_link(self):
        pkgs = {"Ularcirc": {"Version": "1.30.0", "source.ver": "src/contrib/Ularcirc_1.30.0.tar.gz"}}
        _, unserved = apply_downloads(pkgs, index({}), "4.6")
        self.assertNotIn("source.ver", pkgs["Ularcirc"])
        self.assertEqual(unserved, ["Ularcirc"])

    def test_arm64_directory_follows_the_r_version(self):
        self.assertIn("mac.binary.sonoma-arm64.ver", bin_dirs("4.6"))
        self.assertIn("mac.binary.big-sur-arm64.ver", bin_dirs("4.5"))


if __name__ == "__main__":
    unittest.main()
