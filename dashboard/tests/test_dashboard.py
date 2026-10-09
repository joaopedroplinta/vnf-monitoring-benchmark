"""Regressões de estatística e dos recortes apresentados ao usuário."""
from pathlib import Path
import sys
import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analytics import LABEL, confidence_separated, summary, volume


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_csv(ROOT / "data.csv")
        cls.df["Ferramenta"] = cls.df.tool.map(LABEL)
        cls.df["N"] = cls.df.n.map(volume)

    def test_original_results_and_intervals(self):
        s = summary(self.df, "rtt_ms")
        first = s[(s.Ferramenta == "eBPF") & (s.n == 100000)].iloc[0]
        self.assertAlmostEqual(first["mean"], 0.5331, places=4)
        self.assertAlmostEqual(first["ci"], 0.0029, places=4)
        self.assertEqual(first["count"], 30)
        self.assertTrue(confidence_separated(self.df, "eBPF", "Sysstat"))

    def test_ci_overlap_and_single_repetition_are_not_claimed_separate(self):
        rows = pd.DataFrame({"Ferramenta": ["eBPF"] * 3 + ["Sysstat"] * 3,
                             "n": [100000] * 6, "N": ["100 mil"] * 6,
                             "rtt_ms": [0.1, 1, 1.9, 0.2, 1.1, 2]})
        self.assertFalse(confidence_separated(rows, "eBPF", "Sysstat"))
        self.assertFalse(confidence_separated(rows.iloc[[0, 3]], "eBPF", "Sysstat"))

    def test_missing_tool_in_one_volume_prevents_global_ci_claim(self):
        rows = self.df[~((self.df.Ferramenta == "Sysstat") & (self.df.n == 100000))]
        self.assertFalse(confidence_separated(rows, "eBPF", "Sysstat"))


class InteractionTests(unittest.TestCase):
    def test_filter_export_and_empty_state_recovery(self):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.tabs), 6)
        self.assertEqual(len(at.dataframe[0].value), 480)

    def test_boxplot_keeps_single_docker_after_focus_was_enabled(self):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        at.toggle[1].set_value(True).run()
        at.multiselect(key="tools").set_value(["Docker"]).run()
        self.assertFalse(at.exception)
        import json
        box = json.loads(at.get("plotly_chart")[3].proto.spec)
        self.assertEqual([trace["name"] for trace in box["data"]], ["Docker"])
        at.multiselect(key="tools").set_value(["Docker"])
        at.multiselect(key="volumes").set_value([100000]).run()
        self.assertFalse(at.exception)
        raw = at.dataframe[0].value
        self.assertEqual(len(raw), 30)
        self.assertEqual(set(raw.tool), {"docker"})
        self.assertEqual(set(raw.n), {100000})
        at.multiselect(key="tools").set_value([]).run()
        self.assertFalse(at.exception)
        self.assertIn("Nenhum resultado", at.info[0].value)
        at.button[0].click().run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.dataframe[0].value), 480)

    def test_resources_and_logarithmic_scale(self):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        for metric in ["cpu_waf", "mem_waf_mb", "cpu_obs", "mem_obs_mb"]:
            at.selectbox[0].set_value(metric).run()
            self.assertFalse(at.exception)
            if metric == "cpu_obs":
                self.assertTrue(any("ruidosa" in info.value for info in at.info))
            if metric in ["cpu_waf", "mem_waf_mb"]:
                self.assertTrue(any("cgroup" in info.value for info in at.info))
        at.toggle(key="log").set_value(True).run()
        self.assertFalse(at.exception)
        import json
        self.assertEqual(json.loads(at.get("plotly_chart")[0].proto.spec)["layout"]["yaxis"]["type"], "log")


if __name__ == "__main__":
    unittest.main()
