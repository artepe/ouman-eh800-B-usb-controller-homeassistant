"""Read-only OpenHVAC Lab feature tests (no HA, physical controller or network)."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from openhvac_lab.core import InvalidMeasurement, number, utc_time, baseline
from openhvac_lab.doctor import analyze_plant
from openhvac_lab.hydronics import balance_rooms
from openhvac_lab.heating import plan_buffer_heating
from openhvac_lab.ventilation import assess_ventilation
from openhvac_lab.safety import inspect_safety
from openhvac_lab.profiles import text_candidates, csv_candidates, validate_profile
from openhvac_lab.gateway import normalize_bundle
from openhvac_lab.commissioning import review_commissioning, markdown_report
from openhvac_lab.refrigerant import log_ph_svg
from openhvac_lab.multisite import SiteStore, validate_site_report
from openhvac_lab.ai import local_endpoint, explain
from openhvac_lab_server import make_handler


def fixture(file):
    return json.loads((ROOT / "examples/openhvac-lab" / file).read_text(encoding="utf-8"))


class CoreTests(unittest.TestCase):
    def test_finite_measurements(self):
        self.assertEqual(number("21.5"), 21.5)
        for bad in (True, None, "unknown", float("nan"), float("inf")):
            with self.subTest(bad=bad), self.assertRaises(InvalidMeasurement):
                number(bad)
        self.assertEqual(utc_time("2026-11-04T10:00:00+02:00").hour, 8)
        with self.assertRaises(InvalidMeasurement):
            utc_time("2026-11-04T10:00:00")
        self.assertEqual(baseline([3, 3, 4, 3, 3])["median"], 3)


class DoctorTests(unittest.TestCase):
    def test_fault_doctor_explainable_findings(self):
        p = fixture("fault-doctor.json")
        p["current"]["heating_cop"] = 4.7
        result = analyze_plant(p["current"], p["history"])
        flags = {f["code"] for f in result["findings"]}
        self.assertIn("cop_decline", flags)
        self.assertIn("filter_pressure", flags)
        self.assertIn("unmet_supply_target", flags)
        self.assertIn("low_flow", flags)
        self.assertEqual(result["commands_issued"], 0)
        self.assertFalse(result["verified_root_cause"])

    def test_unverified_or_missing_sample_does_not_invent_fault(self):
        self.assertEqual(analyze_plant({})["findings"], [])
        self.assertIn("notes", analyze_plant({"heating_cop": 3.1}))
        with self.assertRaises(ValueError):
            analyze_plant({}, history=[{}] * 10001)

    def test_defrost_history_transition_count(self):
        states = [False,True] * 8
        out = analyze_plant({}, [{"defrost_active": x} for x in states])
        self.assertIn("frequent_defrost", {x["code"] for x in out["findings"]})



    def test_optional_private_ollama_narrative_never_controls(self):
        self.assertEqual(local_endpoint("http://127.0.0.1:11434"),
                         "http://127.0.0.1:11434/api/generate")
        for url in ("https://127.0.0.1:11434", "http://8.8.8.8:11434",
                    "http://127.0.0.1:11434/secret",
                    "http://user:password@127.0.0.1:11434"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                local_endpoint(url)

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self, limit):
                return b'{"response":"Check measured COP history before diagnosing."}'

        calls = []
        def fake_open(req, timeout):
            calls.append((req.full_url, req.data, timeout))
            return FakeResponse()

        result = explain([{
            "code": "cop_decline", "severity": "warning",
            "evidence": {"cop_now": 4.2, "reference_median": 6.0},
            "summary": "Untrusted possible narrative that must not be forwarded",
        }], url="http://192.168.1.9:11434", opener=fake_open)
        self.assertEqual(result["commands_issued"], 0)
        self.assertFalse(result["diagnosis_verified"])
        self.assertNotIn(b"Untrusted possible narrative", calls[0][1])


class HydronicsAndHeatingTests(unittest.TestCase):
    def test_hydronic_prioritization(self):
        out = balance_rooms(fixture("hydronic-balance.json")["rooms"])
        self.assertEqual(out["rooms"][0]["status"], "possible_flow_limitation")
        self.assertTrue(all(not x["auto_change"] for x in out["rooms"]))
        self.assertEqual(out["commands_issued"], 0)
        with self.assertRaises(ValueError):
            balance_rooms([])

    def test_price_storage_schedule_is_advisory(self):
        data = fixture("heating-forecast.json")
        out = plan_buffer_heating(data["config"], data["forecast"])
        self.assertTrue(out["feasible"], out)
        self.assertEqual(len(out["slots"]), 5)
        self.assertEqual(out["commands_issued"], 0)
        self.assertLessEqual(out["final_buffer_kwh_estimate"],
                             out["buffer_capacity_kwh"])
        self.assertTrue(all(0 <= x["heatpump_thermal_kw_suggested"] <= 12
                            for x in out["slots"]))

    def test_impossible_storage_plan_fails_closed(self):
        p = fixture("heating-forecast.json")
        p["config"]["tank_current_c"] = 45
        p["config"]["heatpump_max_thermal_kw"] = .1
        out = plan_buffer_heating(p["config"], p["forecast"])
        self.assertFalse(out["feasible"])
        self.assertEqual(out["commands_issued"], 0)


class VentilationSafetyTests(unittest.TestCase):
    def test_recovery_and_sfp_are_estimates(self):
        result = assess_ventilation(fixture("ventilation.json"))
        self.assertAlmostEqual(result["metrics"]["temperature_recovery_ratio"], .75)
        self.assertIn("estimated_sfp_kw_per_m3s", result["metrics"])
        self.assertEqual(result["commands_issued"], 0)
        self.assertTrue(result["warnings"])

    def test_missing_ventilation_data_does_not_calculate_fake_efficiency(self):
        self.assertNotIn("temperature_recovery_ratio",
                         assess_ventilation({"outdoor_c": 0})["metrics"])

    def test_safety_independent_of_actuator(self):
        data = fixture("safety.json")
        result = inspect_safety(data, now=data["now"])
        ids = {x["code"] for x in result["alerts"]}
        self.assertIn("stale_telemetry", ids)
        self.assertIn("elevated_co2", ids)
        self.assertFalse(result["native_safety_bypass"])
        self.assertEqual(result["commands_issued"], 0)
        data["water_leak"] = True
        self.assertIn("water_leak", {x["code"] for x in
                                    inspect_safety(data, now=data["now"])["alerts"]})


class RegisterAndGatewayTests(unittest.TestCase):
    def test_document_register_candidates_never_write(self):
        out = text_candidates(
            "30001 Outdoor temperature\n40021 Supply target\n"
            "40022 password secret\nNo valid register here",
            source_document="factory_manual.pdf")
        self.assertEqual(out["candidate_count"], 2)
        self.assertEqual(out["registers"][0]["address"], 1)
        self.assertEqual(out["registers"][0]["area"], "input")
        self.assertEqual(out["registers"][1]["area"], "holding")
        self.assertTrue(all(not x["writable"] and not x["reviewed"]
                            for x in out["registers"]))

    def test_csv_register_explorer(self):
        text = "address,name\n30001,Outdoor temperature\n40022,Heating target\n"
        self.assertEqual(csv_candidates(text, source_document="vendor.csv")
                         ["candidate_count"], 2)

    def test_community_catalog_fails_closed(self):
        p = fixture("profile-candidate.json")
        self.assertTrue(validate_profile(p)["read_only"])
        p["registers"][0]["writable"] = True
        with self.assertRaises(ValueError):
            validate_profile(p)
        p["registers"][0]["writable"] = False
        p["source_url"] = "http://fake.example/test"
        with self.assertRaises(ValueError):
            validate_profile(p)

    def test_source_quality_and_network_decoupling(self):
        p = fixture("gateway.json")
        result = normalize_bundle(p["readings"], now=p["now"])
        q = [v["quality"] for v in result["measurements"]]
        self.assertEqual(q, ["fresh", "fresh", "stale"])
        self.assertTrue(all(v["read_only"] for v in result["measurements"]))
        with self.assertRaises(ValueError):
            normalize_bundle([dict(p["readings"][0], source="raw_radio")],
                             now=p["now"])


class TwinCommissioningMultiSiteTests(unittest.TestCase):
    def test_cycle_schematic_no_compressor_control(self):
        fixture_data = fixture("ph-cycle.json")
        svg = log_ph_svg(fixture_data["states"], refrigerant="R290")
        self.assertIn("<svg", svg)
        self.assertIn("Pressure (bar absolute, log scale)", svg)
        self.assertIn("Point-to-point schematic only", svg)
        self.assertNotIn("document.write", svg)
        with self.assertRaises(ValueError):
            log_ph_svg({"suction": fixture_data["states"]["suction"]})

    def test_commissioning_requires_human_acceptance(self):
        p = fixture("commissioning.json")
        result = review_commissioning(p["profile"], p["observations"],
                                      site_id=p["site_id"], checked_at=p["checked_at"])
        self.assertEqual(result["counts"]["observed"], 2)
        self.assertEqual(result["site_acceptance"], "PENDING_OPERATOR_REVIEW")
        self.assertFalse(result["physical_setpoints_changed"])
        self.assertIn("Operator name/signature:", markdown_report(result))

    def test_multi_site_latest_only_sqlite_and_no_write(self):
        with tempfile.TemporaryDirectory() as directory:
            db = SiteStore(Path(directory) / "sites.sqlite3")
            p = fixture("site-report.json")
            first = db.put(p)
            self.assertEqual(db.get(first["site_id"])["status"], "warning")
            self.assertEqual(len(db.list()), 1)
            older = {**p, "observed_at": "2026-11-03T00:00:00Z"}
            with self.assertRaises(ValueError):
                db.put(older)
            self.assertEqual(db.get(first["site_id"])["device_commands_issued"], 0)
            invalid = {**p, "metrics": {"supply": float("nan")}}
            with self.assertRaises(ValueError):
                validate_site_report(invalid)

    def test_multi_site_future_timestamp_rejected(self):
        """A clock-skewed collector must not poison a site's newest snapshot."""
        with tempfile.TemporaryDirectory() as directory:
            db = SiteStore(Path(directory) / "sites.sqlite3")
            p = fixture("site-report.json")
            db.put(p)
            future = {**p, "observed_at": (
                datetime.now(timezone.utc) + timedelta(days=2)).isoformat()}
            with self.assertRaisesRegex(ValueError, "future"):
                db.put(future)
            self.assertEqual(db.get(p["site_id"])["observed_at"],
                             utc_time(p["observed_at"]).isoformat())
            # A subsequent newer, genuine reading is still accepted.
            current = {**p, "observed_at": datetime.now(timezone.utc).isoformat(),
                       "status": "ok"}
            self.assertEqual(db.put(current)["status"], "ok")
            self.assertEqual(db.get(p["site_id"])["status"], "ok")

    def test_local_http_api_requires_long_token(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                make_handler(SiteStore(Path(directory)/"x.db"), "weak")
            self.assertTrue(callable(make_handler(
                SiteStore(Path(directory)/"y.db"), "a-secure-token-with-more-than-24-chars")))

    def test_local_http_api_answers_real_requests(self):
        """Regression: a `headers` method shadowed the request headers, so
        every reply raised TypeError and clients got an empty response."""
        from http.server import ThreadingHTTPServer
        import threading
        import urllib.error
        import urllib.request

        token = "a-secure-token-with-more-than-24-chars"
        with tempfile.TemporaryDirectory() as directory:
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                make_handler(SiteStore(Path(directory) / "z.db"), token))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

            def call(path, data=None, auth=True):
                request = urllib.request.Request(base + path, data=data)
                if auth:
                    request.add_header("Authorization", "Bearer " + token)
                try:
                    with opener.open(request, timeout=5) as response:
                        return response.status, json.loads(response.read())
                except urllib.error.HTTPError as err:
                    return err.code, json.loads(err.read())

            try:
                self.assertEqual(call("/health"),
                                 (200, {"status": "ok", "actuator_commands": 0}))
                self.assertEqual(call("/health", auth=False)[0], 401)
                body = json.dumps(fixture("site-report.json")).encode("utf-8")
                status, reply = call("/ingest", data=body)
                self.assertEqual(status, 200)
                self.assertEqual(reply["site_id"], "demo-building-01")
                self.assertEqual(call("/sites/demo-building-01")[0], 200)
                self.assertEqual(call("/sites/unknown-site")[0], 404)
            finally:
                server.shutdown()
                server.server_close()

    def test_digital_twin_stays_read_only(self):
        content = (ROOT/"www/openhvac-digital-twin-card.js").read_text(encoding="utf-8")
        self.assertIn("hass-more-info", content)
        self.assertIn("class OpenHVACDigitalTwinCard", content)
        self.assertNotIn("callService(", content)
        self.assertNotIn("write_property(", content)


class CliTests(unittest.TestCase):
    def run_cli(self, command, fixture_name, *args):
        process = subprocess.run(
            [sys.executable, str(ROOT/"tools/openhvac_lab_cli.py"),
             command, "--input", str(ROOT/"examples/openhvac-lab"/fixture_name),
             *args],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def test_cli_fault_and_heating(self):
        self.assertIn("findings", self.run_cli("fault-doctor", "fault-doctor.json"))
        self.assertIn("feasible", self.run_cli("heating-forecast", "heating-forecast.json"))

    def test_cli_svg_and_multi_site(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"cycle.svg"
            out = self.run_cli("refrigerant-svg", "ph-cycle.json",
                               "--output", str(path))
            self.assertEqual(out["commands_issued"], 0)
            self.assertTrue(path.read_text(encoding="utf-8").startswith("<svg"))
            db = Path(directory)/"sites.db"
            self.run_cli("multi-site-import", "site-report.json", "--db", str(db))
            p = subprocess.run(
                [sys.executable, str(ROOT/"tools/openhvac_lab_cli.py"),
                 "multi-site-summary", "--db", str(db)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(len(json.loads(p.stdout)["sites"]), 1)


if __name__ == "__main__":
    unittest.main()
