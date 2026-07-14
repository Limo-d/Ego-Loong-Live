import unittest
from pathlib import Path

from backend.tactile_processor import POINTS, SENSOR_NAMES, TactileProcessor


ROOT = Path(__file__).resolve().parents[1]


class TactileMappingTests(unittest.TestCase):
    def test_verified_layout(self):
        self.assertEqual(len(POINTS), 68)
        self.assertEqual(len(SENSOR_NAMES), 68)
        self.assertEqual(SENSOR_NAMES[:4], ("A0", "A1", "A2", "A3"))
        self.assertEqual(SENSOR_NAMES[20], "F0")
        self.assertEqual(SENSOR_NAMES[-1], "F47")
        self.assertAlmostEqual(POINTS[20][0], 0.637)
        self.assertAlmostEqual(POINTS[27][0], 0.247)

    def test_filter_and_no_mirror(self):
        cfg = {"baseline_frames": 2, "noise_gate": 1.5, "ema_rise": .45, "ema_fall": .22,
               "fixed_min": 0, "fixed_max": 160, "auto_range": False,
               "contact_threshold": 4, "high_threshold": 20,
               "mirror_left": False, "mirror_right": False}
        processor = TactileProcessor(cfg, "left")
        processor.process([10] * 68)
        baseline = processor.process([10] * 68)
        self.assertTrue(baseline["baseline_ready"])
        result = processor.process([50] + [10] * 67)
        self.assertFalse(result["mirror"])
        self.assertGreater(result["smoothed"][0], 0)
        self.assertEqual(len(result["display"]), 68)

    def test_frontend_side_specific_mapping(self):
        view = (ROOT / "frontend/js/tactile_view.js").read_text(encoding="utf-8")
        page = (ROOT / "frontend/dashboard.html").read_text(encoding="utf-8")
        self.assertIn("LEFT_VISUAL_SOURCE[36+offset]=60+offset", view)
        self.assertIn("LEFT_VISUAL_SOURCE[60+offset]=36+offset", view)
        self.assertIn("this.side==='right'?1-p[0]:p[0]", view)
        self.assertIn('.tactile-card[data-side="right"] .tactile-hand-image{transform:scaleX(-1)}', page)


if __name__ == "__main__":
    unittest.main()
