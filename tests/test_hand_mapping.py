import unittest
import copy
import math

import numpy as np

from backend.config import load_config
from backend.hand_pose_processor import HandPoseProcessor


class HandMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.processor = HandPoseProcessor(load_config()["hand"])

    def state(self):
        state = [0.0] * 27
        state[19] = 1.0
        state[23] = 1.0
        return state

    def test_joint_and_bone_count(self):
        result = self.processor.process(self.state(), "left")
        self.assertEqual(len(result["points"]), 21)
        self.assertEqual(len(result["bones"]), 20)
        self.assertEqual(len(result["angles"]), 19)
        self.assertEqual(result["angles"][0]["name"], "index.MCP flex")
        self.assertEqual(result["angles"][16]["name"], "thumb.MCP flex")

    def test_right_uses_same_lengths_with_mirrored_offsets(self):
        left = np.asarray(self.processor.process(self.state(), "left")["points"])
        right = np.asarray(self.processor.process(self.state(), "right")["points"])
        # Each hand consumes its own calibrated CMC rotation, so complete pose
        # mirroring is not a valid data-contract requirement.  Geometry still
        # shares identical bone lengths, while only configured chain roots are
        # mirrored across the local thumb-side axis.
        for root_index in (1, 5, 9, 13, 17):
            self.assertTrue(np.allclose(left[root_index, :2], right[root_index, :2], atol=1e-6))
            self.assertAlmostEqual(left[root_index, 2], -right[root_index, 2], places=6)
        for start, end in self.processor.process(self.state(), "left")["bones"]:
            left_length = np.linalg.norm(left[end] - left[start])
            right_length = np.linalg.norm(right[end] - right[start])
            self.assertAlmostEqual(left_length, right_length, places=6)

    def test_first_valid_palm_quaternion_is_zeroed_per_hand(self):
        config = copy.deepcopy(load_config()["hand"])
        anchored = HandPoseProcessor(config)
        absolute_config = copy.deepcopy(config)
        absolute_config["anchor_initial_palm"] = False
        absolute = HandPoseProcessor(absolute_config)
        tilted = self.state()
        angle = math.radians(63)
        tilted[23:27] = [math.cos(angle / 2), 0.0, 0.0, math.sin(angle / 2)]

        anchored_points = np.asarray(anchored.process(tilted, "left")["points"])
        canonical_points = np.asarray(absolute.process(self.state(), "left")["points"])
        self.assertTrue(np.allclose(anchored_points, canonical_points, atol=1e-6))
        self.assertTrue(np.allclose(anchored_points[0], [-0.014, 0.0, 0.0], atol=1e-9))

    def test_absent_hand_resets_palm_reference(self):
        processor = HandPoseProcessor(copy.deepcopy(load_config()["hand"]))
        tilted = self.state()
        angle = math.radians(45)
        tilted[23:27] = [math.cos(angle / 2), math.sin(angle / 2), 0.0, 0.0]
        first = np.asarray(processor.process(tilted, "right")["points"])
        processor.process([1.0e9] * 27, "right")
        reconnected = np.asarray(processor.process(tilted, "right")["points"])
        self.assertTrue(np.allclose(first, reconnected, atol=1e-6))


if __name__ == "__main__":
    unittest.main()
