"""Portable tests for local, advisory-only OpenHVAC AI behaviour."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import unittest

FILE = Path(__file__).resolve().parents[1] / "custom_components/openhvac/ai_guide.py"
spec = importlib.util.spec_from_file_location("openhvac_ai_guide", FILE)
ai = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ai
spec.loader.exec_module(ai)

class AdvisorTests(unittest.TestCase):
    def test_private_only_endpoint(self):
        self.assertEqual(ai.validate_local_ai_url("http://192.168.10.50:11434/"),
                         "http://192.168.10.50:11434")
        self.assertEqual(ai.validate_local_ai_url(""), "")
        for bad in [
            "https://192.168.10.50:11434",
            "http://8.8.8.8:11434",
            "http://evil.invalid:11434",
            "http://192.168.10.50:8080",
            "http://192.168.10.50:11434/admin",
            "http://user:password@192.168.10.50:11434",
            "http://0.0.0.0:11434",
        ]:
            with self.subTest(url=bad), self.assertRaises(ValueError):
                ai.validate_local_ai_url(bad)

    def test_small_model_name(self):
        self.assertEqual(ai.validate_model("qwen2.5:0.5b"), "qwen2.5:0.5b")
        with self.assertRaises(ValueError):
            ai.validate_model("bad model; rm -rf /")

    def test_no_private_or_unverified_fields_in_prompt(self):
        data = {"measurement_1":56.5, "measurement_9":58.5,
                "measurement_16":35.1,
                "password":"secret", "host":"192.168.10.15",
                "l1_curve_0c":63, "measurement_6":120}
        result = ai.safe_prompt("EH-800B", "Explain the curve", data, [])
        self.assertIn("58.5", result)
        self.assertNotIn("secret", result)
        self.assertNotIn("192.168.10.15", result)
        self.assertNotIn("l1_curve_0c\": 63", result)
        self.assertIn("UNKNOWN", result)

    def test_offline_guide_is_immediate_and_english(self):
        output = ai.offline_answer("EH-800B", "What is L1 fine adjustment?",
                     {"measurement_1":55.5, "measurement_9":58.0},
                     ["Valve and supply target differ"])
        self.assertIn("fine adjustment", output.lower())
        self.assertIn("NO physical controller settings were changed", output)
        self.assertIn("55.5", output)

    def test_invalid_sensor_values_are_skipped(self):
        points = ai.selected_measurements({
            "measurement_9":float("nan"), "measurement_10":float("inf"),
            "measurement_16":True, "measurement_1":55.3})
        self.assertEqual(len(points), 1)
        self.assertEqual(points["Calculated L1 supply-water target (°C)"],55.3)

class FakeResponse:
    status = 200
    content_length = 100

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    class Content:
        async def read(self, max_size):
            import json
            response = {
                "response": json.dumps({
                    "answer": "Check the measured water temperature before changing the curve."
                })
            }
            return json.dumps(response).encode()

    content = Content()

class FakeSession:
    def __init__(self): self.calls=[]
    def post(self,url,**kwargs):
        self.calls.append((url,kwargs))
        return FakeResponse()

class OllamaProtocolTests(unittest.TestCase):
    def test_request_is_explanatory_only(self):
        session=FakeSession()
        response=asyncio.run(ai.query_local_ollama(
            session,"http://192.168.10.50:11434", "qwen2.5:0.5b",
            ai.safe_prompt("EH-800B","Explain L1 heating curve",
                           {"measurement_9":58.5},[])))
        self.assertIn("measured water",response)
        url,opts=session.calls[0]
        self.assertEqual(url,"http://192.168.10.50:11434/api/generate")
        self.assertFalse(opts["json"]["stream"])
        self.assertFalse(opts["allow_redirects"])
        self.assertNotIn("tools",opts["json"])
        self.assertNotIn("write",url)

if __name__=="__main__":
    unittest.main()
