import unittest

from src.fusion.fusion_engine import FusionEngine


class TestFusionBasic(unittest.TestCase):
    def test_simple_fusion_and_cooldown(self):
        config = {
            "weights": {"vision": 0.6, "audio": 0.4, "text": 0.0},
            "threshold_on": 0.7,
            "threshold_off": 0.3,
            "cooldown_sec": 5.0,
            "half_life_sec": 1.0,
        }
        engine = FusionEngine(config)

        events = [
            # First trigger
            {"time": 1.0, "modality": "vision", "score": 0.8},
            {"time": 1.1, "modality": "audio", "score": 0.7},
            # Force the fused score to decay below threshold_off so the engine can re-arm.
            {"time": 2.6, "modality": "vision", "score": 0.0},
            # Would normally trigger, but should be ignored due to cooldown.
            {"time": 3.0, "modality": "vision", "score": 0.9},
            {"time": 3.1, "modality": "audio", "score": 0.9},
            # Ensure the internal scores stay low before the next trigger.
            {"time": 6.0, "modality": "vision", "score": 0.0},
            # Second trigger after cooldown
            {"time": 7.0, "modality": "vision", "score": 0.8},
            {"time": 7.1, "modality": "audio", "score": 0.8},
        ]

        triggers = engine.fuse(events)
        self.assertEqual(len(triggers), 2)
        self.assertAlmostEqual(triggers[0]["time"], 1.1)
        self.assertAlmostEqual(triggers[1]["time"], 7.1)

    def test_hysteresis(self):
        config = {
            "weights": {"vision": 1.0, "audio": 0.0, "text": 0.0},
            "threshold_on": 0.8,
            "threshold_off": 0.4,
            "cooldown_sec": 1.0,
            "half_life_sec": 0.1,  # Fast decay
        }
        engine = FusionEngine(config)

        events = [
            {"time": 1.0, "modality": "vision", "score": 0.9},  # ON
            {"time": 1.1, "modality": "vision", "score": 0.7},  # Stays ON
            {"time": 1.2, "modality": "vision", "score": 0.5},  # Stays ON
            {"time": 1.3, "modality": "vision", "score": 0.3},  # OFF
            {"time": 2.5, "modality": "vision", "score": 0.9},  # ON again
        ]

        triggers = engine.fuse(events)
        self.assertEqual(len(triggers), 2)
        self.assertAlmostEqual(triggers[0]["time"], 1.0)
        self.assertAlmostEqual(triggers[1]["time"], 2.5)


if __name__ == "__main__":
    unittest.main()
