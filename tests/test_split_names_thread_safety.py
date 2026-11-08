import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from kahi_impactu_utils import Utils


class ConcurrentModel:
    def __init__(self):
        self.active_calls = 0
        self.concurrent_call_detected = False
        self.state_lock = threading.Lock()

    def _predict(self, result):
        with self.state_lock:
            self.active_calls += 1
            if self.active_calls > 1:
                self.concurrent_call_detected = True
        time.sleep(0.005)
        with self.state_lock:
            self.active_calls -= 1
        return [result]

    def predict_ethnicity(self, _name):
        return self._predict({"label": "Hispanic", "score": 0.99})

    def predict_race(self, _name):
        return self._predict({"label": "hispanic"})


class SplitNamesThreadSafetyTest(unittest.TestCase):
    def test_shared_racebert_model_is_serialized(self):
        model = ConcurrentModel()

        with patch.object(Utils, "_model", model):
            with ThreadPoolExecutor(max_workers=24) as executor:
                results = list(
                    executor.map(Utils.split_names, ["Juan Perez Gomez"] * 96)
                )

        self.assertFalse(model.concurrent_call_detected)
        self.assertTrue(all(result["full_name"] for result in results))

    def test_repeated_hyphens_do_not_create_empty_name_parts(self):
        result = Utils.split_names(
            "Español---Francés En", countryOrigin="ES"
        )

        self.assertNotIn("", result["first_names"])
        self.assertNotIn("", result["last_names"])
        self.assertEqual(result["initials"], "EF")


if __name__ == "__main__":
    unittest.main()
