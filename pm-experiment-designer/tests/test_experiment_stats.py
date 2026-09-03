import importlib.util
import pathlib
import unittest


SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "experiment_stats.py"
SPEC = importlib.util.spec_from_file_location("experiment_stats", SCRIPT)
stats = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(stats)


class ExperimentStatsTests(unittest.TestCase):
    def test_proportion_sample_size_is_deterministic(self):
        result = stats.sample_size_proportion(0.10, 0.10, "relative", 0.05, 0.80)
        self.assertEqual(result["per_group"], 14749)
        self.assertEqual(result["total_two_groups"], 29498)

    def test_absolute_mde(self):
        result = stats.sample_size_proportion(0.10, 0.02, "absolute", 0.05, 0.80)
        self.assertAlmostEqual(result["treatment"], 0.12)
        self.assertAlmostEqual(result["absolute_delta"], 0.02)

    def test_mean_sample_size(self):
        result = stats.sample_size_mean(12, 2, 0.05, 0.80)
        self.assertEqual(result["per_group"], 566)

    def test_balanced_split_passes_srm(self):
        result = stats.srm([5000, 5000], [0.5, 0.5], 0.01)
        self.assertAlmostEqual(result["p_value"], 1.0)
        self.assertFalse(result["srm_failed"])

    def test_skewed_split_fails_srm(self):
        result = stats.srm([5500, 4500], [0.5, 0.5], 0.01)
        self.assertLess(result["p_value"], 0.01)
        self.assertTrue(result["srm_failed"])

    def test_rejects_invalid_treatment_rate(self):
        with self.assertRaises(ValueError):
            stats.sample_size_proportion(0.9, 0.2, "relative", 0.05, 0.8)


if __name__ == "__main__":
    unittest.main()
