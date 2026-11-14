import copy
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from .api import create_app, VALIDATOR


PATH = "/api/v1/simulation/runs/demo-run/astronauts/A01/inputs"


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def test_recalculates_and_validates(self):
        first = self.client.get(PATH)
        second = self.client.get(PATH)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.headers["cache-control"], "no-store")
        a, b = first.json(), second.json()
        VALIDATOR.validate(a)
        VALIDATOR.validate(b)
        self.assertEqual(len(a["items"]), 1)
        self.assertIsNone(a["next_cursor"])
        x, y = a["items"][0], b["items"][0]
        self.assertNotEqual(x["record_id"], y["record_id"])
        self.assertLess(x["observed_at"], y["observed_at"])
        self.assertNotEqual(x["physiological"]["heart_rate"]["value"], y["physiological"]["heart_rate"]["value"])
        self.assertEqual(sum(len(x[g]) for g in ("physiological", "self_assessment", "environment")), 20)
        for key in ("earth_latency", "simulated_daylight_duration", "social_interaction_duration"):
            self.assertEqual(x["environment"][key]["quality"], "missing")
            self.assertIsNone(x["environment"][key]["value"])
        sleep = x["self_assessment"]["sleep_duration"]
        self.assertLess(sleep["period_start"], sleep["period_end"])
        self.assertLessEqual(sleep["period_end"], sleep["observed_at"])

    def test_invalid_requests_do_not_advance(self):
        for query in ("limit=1", "cursor=x", "from=2026-01-01T00:00:00Z", "unexpected=x"):
            r = self.client.get(PATH + "?" + query)
            self.assertEqual(r.status_code, 422)
            self.assertEqual(r.json()["error"]["code"], "invalid_query")
        self.assertEqual(self.client.get(PATH.replace("demo-run", "missing")).json()["error"]["code"], "run_not_found")
        self.assertEqual(self.client.get(PATH.replace("A01", "missing")).json()["error"]["code"], "astronaut_not_found")
        self.assertEqual(self.app.state.sequences, {})

    def test_openapi_matches_responses(self):
        spec = self.client.get("/openapi.json").json()
        self.assertEqual(spec["info"]["version"], "1.1.0")
        operation = next(iter(spec["paths"].values()))["get"]
        self.assertEqual(len(operation["parameters"]), 2)
        schema = copy.deepcopy(spec["components"]["schemas"]["InputsResponse"])
        schema["components"] = spec["components"]
        Draft202012Validator(schema).validate(self.client.get(PATH).json())

    def test_independent_streams(self):
        other = TestClient(create_app())
        self.client.get(PATH.replace("A01", "AST-001"))
        a = self.client.get(PATH).json()["items"][0]
        b = other.get(PATH).json()["items"][0]
        self.assertEqual(a["physiological"]["heart_rate"]["value"], b["physiological"]["heart_rate"]["value"])

    def test_concurrent_calls_have_unique_records(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(lambda _: self.client.get(PATH), range(12)))
        self.assertTrue(all(r.status_code == 200 for r in responses))
        ids = {r.json()["items"][0]["record_id"] for r in responses}
        self.assertEqual(len(ids), 12)

    def test_invalid_generation_returns_error_without_advancing(self):
        with patch("Project.simulated_inputs_app.api.VALIDATOR") as validator:
            validator.validate.side_effect = ValueError("invalid")
            response = self.client.get(PATH)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "simulation_unavailable")
        self.assertEqual(self.app.state.sequences, {})


if __name__ == "__main__":
    unittest.main()
