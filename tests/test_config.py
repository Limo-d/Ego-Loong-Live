from pathlib import Path
import unittest

from backend.config import load_config


class ConfigTests(unittest.TestCase):
    def test_default_config(self):
        config = load_config(mock_override=True)
        self.assertTrue(config["mode"]["mock"])
        self.assertFalse(config["rgb"]["allow_crop"])
        self.assertTrue(config["rgb"]["preserve_full_frame"])
        self.assertEqual(config["rgb"]["max_fps"], 30)
        self.assertTrue(config["hand"]["anchor_initial_palm"])
        self.assertEqual(config["topics"]["hand"]["type"], "hand_frame/msg/HandFrame")
        self.assertTrue(Path(config["hand"]["geometry_config"]).is_file())
        left_calib = config["tactile"]["bend_decoupling"]["calibration_left"]
        self.assertTrue((Path(config["_project_root"]) / left_calib).is_file())
        self.assertEqual(
            config["tactile"]["bend_decoupling"]["calibration_right"],
            "config/tactile/joint_decouple_calib_right.npz",
        )


if __name__ == "__main__":
    unittest.main()
