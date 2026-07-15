import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from backend.tactile_processor import POINTS, SENSOR_NAMES, TactileProcessor
from scripts.calibrate_tactile_bend import save_calibration


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

    def test_display_deadzone_hides_idle_residuals(self):
        cfg = {"baseline_frames": 1, "noise_gate": 0.5, "ema_rise": 1.0, "ema_fall": 1.0,
               "fixed_min": 0, "fixed_max": 20, "auto_range": False,
               "contact_threshold": 3, "display_deadzone": 3, "high_threshold": 10}
        processor = TactileProcessor(cfg, "left")
        processor.process([10] * 68)

        idle = processor.process([12] + [10] * 67)
        self.assertEqual(idle["smoothed"][0], 2)
        self.assertEqual(idle["display"][0], 0)
        self.assertEqual(idle["contact_count"], 0)

        contact = processor.process([14] + [10] * 67)
        self.assertEqual(contact["smoothed"][0], 4)
        self.assertGreater(contact["display"][0], 0)
        self.assertEqual(contact["contact_count"], 1)

    def test_negative_baseline_drift_is_not_pressure(self):
        cfg = {"baseline_frames": 1, "noise_gate": 0.5, "ema_rise": 1.0, "ema_fall": 1.0,
               "fixed_min": 0, "fixed_max": 20, "auto_range": False,
               "contact_threshold": 3, "display_deadzone": 3, "high_threshold": 10}
        processor = TactileProcessor(cfg, "left")
        processor.process([10] * 68)
        result = processor.process([8] + [10] * 67)
        self.assertEqual(result["smoothed"][0], 0)
        self.assertEqual(result["display"][0], 0)

    def test_joint_pose_atlas_removes_bend_signal(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "left.npz"
            poses = np.stack((np.zeros(14), np.full(14, 10.0)))
            tactile = np.stack((np.full(68, 10.0), np.full(68, 20.0)))
            np.savez_compressed(
                path,
                calib_version=np.int32(5), sensor_type=np.int32(1), pose_mode=np.array("joint"),
                bend_center=np.full(14, 5.0), bend_scale=np.full(14, 5.0), atlas_bends=poses,
                atlas_fingers=tactile[:, :20].reshape(2, 5, 2, 2), atlas_palm=tactile[:, 20:],
            )
            cfg = {"baseline_frames": 1, "noise_gate": 0.5, "ema_rise": 1.0, "ema_fall": 1.0,
                   "fixed_min": 0, "fixed_max": 20, "auto_range": False,
                   "contact_threshold": 3, "display_deadzone": 3, "high_threshold": 10,
                   "bend_decoupling": {"enabled": True, "calibration_left": str(path),
                                        "max_pose_distance": 2.0}}
            processor = TactileProcessor(cfg, "left")
            state_open = [0.0] * 27
            processor.process([10] * 68, state_open)
            state_bent = [0.0] * 27
            for index in (16, 18, 0, 2, 3, 4, 6, 7, 8, 10, 11, 12, 14, 15):
                state_bent[index] = 10.0

            bent = processor.process([20] * 68, state_bent)
            self.assertTrue(bent["bend_decoupling"]["applied"])
            self.assertEqual(bent["maximum"], 0)

            contact_values = [20] * 68
            contact_values[0] += 5
            contact = processor.process(contact_values, state_bent)
            self.assertEqual(contact["smoothed"][0], 5)
            self.assertEqual(contact["contact_count"], 1)

    def test_calibration_writer_marks_hand_side(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "right.npz"
            count = save_calibration(path, "right", np.ones((24, 68)), np.ones((24, 14)))
            with np.load(path, allow_pickle=True) as data:
                self.assertEqual(count, 24)
                self.assertEqual(int(data["sensor_type"]), 2)
                self.assertEqual(data["atlas_fingers"].shape, (24, 5, 2, 2))
                self.assertEqual(data["atlas_palm"].shape, (24, 48))


if __name__ == "__main__":
    unittest.main()
