from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "publication-ready/scripts"
sys.path.insert(0, str(SCRIPTS))

from prepare_release import validate_triage_crosswalk  # noqa: E402
from validate_andrei_documents import validate as validate_andrei_documents  # noqa: E402
from validate_curated_release import (  # noqa: E402
    REQUIRED_PUBLIC_OBJECTS,
    unsupported_clinical_equivalence_lines,
    validate,
)
from validate_release import Gate, validate_infrastructure  # noqa: E402

from deployment.upload_public_release import APPROVED_PUBLIC_OBJECTS  # noqa: E402


class TriageCrosswalkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.crosswalk = json.loads(
            (ROOT / "internal/release-support/schema/triage_crosswalk.source.json").read_text()
        )
        cls.observed_paths = {
            path
            for item in cls.crosswalk["classes"]
            for field in item["fields"]
            for path in (
                [field["observed_release_path"]]
                if field["observed_release_path"]
                else field["related_proxy_release_paths"]
            )
        }

    def test_all_four_classes_and_twenty_fields_are_valid(self):
        validate_triage_crosswalk(self.crosswalk, self.observed_paths)
        fields = [field for item in self.crosswalk["classes"] for field in item["fields"]]
        self.assertEqual([len(item["fields"]) for item in self.crosswalk["classes"]], [5, 6, 4, 5])
        self.assertEqual(len(fields), 20)
        self.assertEqual(
            [field["source_field"] for field in fields if field["mapping_status"] == "Exact"],
            ["bp_alert"],
        )

    def test_missing_class_is_rejected(self):
        invalid = copy.deepcopy(self.crosswalk)
        invalid["classes"].pop()
        with self.assertRaises(ValueError):
            validate_triage_crosswalk(invalid, self.observed_paths)

    def test_unverified_exact_mapping_is_rejected(self):
        invalid = copy.deepcopy(self.crosswalk)
        invalid["classes"][0]["fields"][0]["mapping_status"] = "Exact"
        invalid["classes"][0]["fields"][0]["observed_release_path"] = "invented.path"
        with self.assertRaises(ValueError):
            validate_triage_crosswalk(invalid, self.observed_paths | {"invented.path"})

    def test_positive_clinical_equivalence_claim_is_rejected(self):
        self.assertEqual(
            unsupported_clinical_equivalence_lines(
                "A related proxy is clinically equivalent to the source symptom."
            ),
            ["A related proxy is clinically equivalent to the source symptom."],
        )
        self.assertEqual(
            unsupported_clinical_equivalence_lines(
                "This crosswalk does not assert that a proxy is clinically equivalent."
            ),
            [],
        )


class ReleaseIntegrationTests(unittest.TestCase):
    def test_readme_and_license_match_andrei_sources_exactly(self):
        self.assertEqual(validate_andrei_documents(ROOT), [])
        release = ROOT / "build/public-release/releases/v1"
        for name in ["README.md", "LICENSE.md"]:
            self.assertEqual((ROOT / name).read_bytes(), (release / name).read_bytes())

    def test_curated_release_layout_checksums_and_uploader_are_in_sync(self):
        release = ROOT / "build/public-release/releases/v1"
        errors = validate(release, ROOT, ROOT / "publication-ready")
        self.assertEqual(errors, [])
        actual = {str(path.relative_to(release)) for path in release.rglob("*") if path.is_file()}
        self.assertTrue(REQUIRED_PUBLIC_OBJECTS <= actual)
        self.assertEqual(actual, APPROVED_PUBLIC_OBJECTS)
        self.assertNotIn("schema/generation_logic.source.json", actual)
        self.assertNotIn("schema/triage_crosswalk.source.json", actual)

    def test_terraform_outputs_and_iam_are_complete(self):
        gate = Gate()
        validate_infrastructure(ROOT, gate)
        self.assertEqual(gate.errors, [])


if __name__ == "__main__":
    unittest.main()
