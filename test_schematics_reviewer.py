import tempfile
import unittest
from pathlib import Path

from schematics_reviewer import SchematicsReviewer


class SchematicsReviewerTests(unittest.TestCase):
    def test_reports_missing_schematic(self):
        result = SchematicsReviewer().review("/tmp/does-not-exist.sch")

        self.assertEqual(result.findings[0].severity, "Critical")
        self.assertIn("does not exist", result.findings[0].message)

    def test_detects_missing_differential_polarity(self):
        with tempfile.TemporaryDirectory() as directory:
            schematic = Path(directory) / "design.net"
            schematic.write_text("Net D3P2_TXP[0] J10 B08 CONN2 C23\n", encoding="utf-8")

            result = SchematicsReviewer().review(schematic, "PCIe")

        messages = "\n".join(finding.message for finding in result.findings)
        self.assertIn("missing the N polarity", messages)

    def test_detects_power_without_decoupling(self):
        with tempfile.TemporaryDirectory() as directory:
            schematic = Path(directory) / "power.sch"
            schematic.write_text("U1 VDD VCC GND\n", encoding="utf-8")

            result = SchematicsReviewer().review(schematic, "power delivery")

        categories = [finding.category for finding in result.findings]
        self.assertIn("Power delivery", categories)

    def test_renders_reference_prompt_note(self):
        with tempfile.TemporaryDirectory() as directory:
            schematic = Path(directory) / "simple.sch"
            schematic.write_text("U1 GPIO1 GPIO2\n", encoding="utf-8")

            result = SchematicsReviewer().review(schematic)

        self.assertIn("No datasheets or reference materials were supplied", result.to_text())


if __name__ == "__main__":
    unittest.main()
