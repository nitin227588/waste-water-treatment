"""Run with python -m unittest -v test_analyze.py."""
import csv
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import analyze


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def data(self, rows):
        path = self.root / "input.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["experiment_id", "treatment", "replicate_id", "time_h", "parameter", "value", "unit"])
            writer.writerows(rows)
        return path

    def pair(self, start=200, end=40, parameter="COD", unit="mg/L"):
        return [["E", "T", "R1", 0, parameter, start, unit], ["E", "T", "R1", 24, parameter, end, unit]]

    def calculate(self, rows):
        return analyze.analyze(analyze.read_measurements(self.data(rows)))

    def test_known_pair(self):
        pairs, summary, _ = self.calculate(self.pair())
        self.assertAlmostEqual(pairs[0]["removal_percent"], 80)
        self.assertIsNone(summary[0]["sd_removal_percent"])

    def test_mean_paired_percentages_and_sample_sd(self):
        rows = self.pair(100, 20) + [["E", "T", "R2", 0, "COD", 200, "mg/L"], ["E", "T", "R2", 24, "COD", 60, "mg/L"]]
        _, summary, _ = self.calculate(rows)
        self.assertAlmostEqual(summary[0]["mean_removal_percent"], 75)
        self.assertAlmostEqual(summary[0]["sd_removal_percent"], math.sqrt(50))

    def test_negative_removal_preserved(self):
        pairs, _, warnings = self.calculate(self.pair(100, 120))
        self.assertAlmostEqual(pairs[0]["removal_percent"], -20)
        self.assertTrue(warnings)

    def test_zero_baseline_undefined(self):
        pairs, summary, _ = self.calculate(self.pair(0, 10))
        self.assertIsNone(pairs[0]["removal_percent"])
        self.assertEqual(summary[0]["n_removal"], 0)

    def test_ph_has_no_removal(self):
        pairs, _, _ = self.calculate(self.pair(7, 8, "pH", "pH"))
        self.assertIsNone(pairs[0]["removal_percent"])
        self.assertEqual(pairs[0]["change"], 1)

    def test_missing_value_rejected(self):
        with self.assertRaises(analyze.DataError):
            self.calculate(self.pair(100, ""))

    def test_nonfinite_negative_rejected(self):
        for value in ("NaN", "inf", -1):
            with self.subTest(value=value), self.assertRaises(analyze.DataError):
                self.calculate(self.pair(100, value))

    def test_duplicate_time_rejected(self):
        rows = self.pair()
        with self.assertRaises(analyze.DataError):
            self.calculate(rows + [rows[0]])

    def test_baseline_required(self):
        rows = self.pair()
        rows[0][3] = 1
        with self.assertRaises(analyze.DataError):
            self.calculate(rows)

    def test_followup_required(self):
        with self.assertRaises(analyze.DataError):
            self.calculate(self.pair()[:1])

    def test_mixed_units_within_replicate_rejected(self):
        rows = self.pair()
        rows[1][-1] = "g/L"
        with self.assertRaises(analyze.DataError):
            self.calculate(rows)

    def test_units_normalized_between_replicates(self):
        rows = self.pair() + [["E", "T", "R2", 0, "COD", 0.2, "g/L"], ["E", "T", "R2", 24, "COD", 0.04, "g/L"]]
        _, summary, _ = self.calculate(rows)
        self.assertEqual(summary[0]["n_pairs"], 2)
        self.assertAlmostEqual(summary[0]["mean_baseline"], 200)
        self.assertEqual(summary[0]["unit"], "mg/L")

    def test_different_endpoints_not_pooled(self):
        rows = self.pair() + [["E", "T", "R2", 0, "COD", 200, "mg/L"], ["E", "T", "R2", 48, "COD", 20, "mg/L"]]
        _, summary, _ = self.calculate(rows)
        self.assertEqual(len(summary), 2)

    def test_controls_separate(self):
        rows = self.pair() + [["E", "control", "R1", 0, "COD", 200, "mg/L"], ["E", "control", "R1", 24, "COD", 180, "mg/L"]]
        _, summary, _ = self.calculate(rows)
        self.assertEqual(len(summary), 2)

    def test_literature_summary_not_raw_input(self):
        path = self.root / "literature.csv"
        path.write_text("source_id,metric,value\n1,TP_removal,95.1\n", encoding="utf-8")
        with self.assertRaises(analyze.DataError):
            analyze.read_measurements(path)

    def test_html_escaping_and_valid_svg(self):
        rows = self.pair()
        for row in rows:
            row[1] = "<script>alert(1)</script>"
        output = self.root / "results"
        meta = analyze.run(self.data(rows), output, "SYNTHETIC <demo>")
        report = (output / "report.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>", report)
        self.assertIn("&lt;script&gt;", report)
        self.assertEqual(meta["measurement_count"], 2)
        for filename in ("timecourses.svg", "removal.svg"):
            ET.parse(output / filename)

    def test_existing_output_not_overwritten(self):
        output = self.root / "results"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_text("keep")
        with self.assertRaises(analyze.DataError):
            analyze.run(self.data(self.pair()), output, "TEST")
        self.assertEqual(sentinel.read_text(), "keep")

    def test_invalid_data_no_results(self):
        output = self.root / "results"
        with self.assertRaises(analyze.DataError):
            analyze.run(self.data(self.pair(100, "")), output, "TEST")
        self.assertFalse(output.exists())

    def test_partial_defined_removal_counts(self):
        rows = self.pair() + [["E", "T", "R2", 0, "COD", 0, "mg/L"], ["E", "T", "R2", 24, "COD", 5, "mg/L"]]
        _, summary, _ = self.calculate(rows)
        self.assertEqual(summary[0]["n_pairs"], 2)
        self.assertEqual(summary[0]["n_removal"], 1)
        self.assertAlmostEqual(summary[0]["mean_removal_percent"], 80)
        self.assertIsNone(summary[0]["sd_removal_percent"])

    def test_demo_end_to_end(self):
        output = self.root / "demo"
        analyze.run(Path(__file__).with_name("synthetic_measurements.csv"), output, "SYNTHETIC DEMONSTRATION")
        with (output / "summary.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        cod = next(r for r in rows if r["treatment"] == "treated" and r["parameter"] == "COD")
        self.assertEqual(float(cod["mean_removal_percent"]), 75)
        self.assertEqual(len(list(output.iterdir())), 6)


if __name__ == "__main__":
    unittest.main()

