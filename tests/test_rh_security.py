"""R0-R3 security, configuration and redirect regressions (no RH cloud calls)."""
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

from test_rh_client import load_rh_client, RecordingSession
from test_rh_outputs import load_rh_outputs

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_config_module():
    package_name = "rh_config_stage_test_pkg"
    package = types.ModuleType(package_name)
    package.__path__ = [str(ROOT / "nodes")]
    sys.modules[package_name] = package
    name = package_name + ".rh_config"
    spec = importlib.util.spec_from_file_location(name, ROOT / "nodes" / "rh_config.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.module = load_config_module()
        self.node = self.module.RH_Config()
        self.settings = {
            "api_keys": {"international": "int-secret", "domestic": "cn-secret"},
            "trusted_custom_endpoints": {"https://gateway.sample.org": "custom-secret"},
        }
        self.node.load_config_file = lambda: dict(self.settings)

    def test_one_file_loader_and_legacy_contract(self):
        spec = self.node.INPUT_TYPES()
        self.assertEqual(list(spec["required"]), ["api_key", "workflow_or_app_id", "base_url"])
        self.assertEqual(list(spec["optional"]), ["is_ai_app", "query_api", "site"])
        self.assertEqual(spec["optional"]["site"][0], ["international", "domestic", "custom"])
        self.assertEqual(self.node.RETURN_TYPES, ("RH_CONFIG",))

    def test_new_nodes_default_to_international(self):
        result = self.node.create_config("", "2109843724737204225", "https://www.runninghub.cn",
                                         site="international")[0]
        self.assertEqual(result["base_url"], "https://www.runninghub.ai")
        self.assertEqual(result["api_key"], "int-secret")
        self.assertEqual(result["workflow_or_app_id"], "2109843724737204225")

    def test_legacy_prompts_keep_the_original_url(self):
        cfg = self.node.create_config("", "id", "https://www.runninghub.cn")[0]
        self.assertEqual(cfg["base_url"], "https://www.runninghub.cn")
        self.assertEqual(cfg["api_key"], "cn-secret")
        cfg = self.node.create_config("", "id", "https://www.runninghub.ai")[0]
        self.assertEqual(cfg["api_key"], "int-secret")

    def test_migrated_linked_official_urls_remain_usable(self):
        # A legacy external STRING connection forces site='custom' during
        # graph migration, even when its runtime value is an official RH URL.
        # Preserving only the link is insufficient if the backend rejects it.
        for address, key in (
            ("https://www.runninghub.ai", "int-secret"),
            ("https://www.runninghub.cn", "cn-secret"),
        ):
            with self.subTest(address=address):
                result = self.node.create_config("", "2109843724737204225",
                                                 address, site="custom")[0]
                self.assertEqual(result["base_url"], address)
                self.assertEqual(result["api_key"], key)

    def test_region_mismatch_never_uses_other_regions_key(self):
        self.settings["api_keys"].pop("domestic")
        with self.assertRaisesRegex(ValueError, "Missing API Key"):
            self.node.create_config("", "id", "https://www.runninghub.cn", site="domestic")

    def test_custom_requires_a_local_exact_origin_registration(self):
        cfg = self.node.create_config("", "id", "https://gateway.sample.org/", site="custom")[0]
        self.assertEqual(cfg["api_key"], "custom-secret")
        with self.assertRaisesRegex(ValueError, "authorized"):
            self.node.create_config("", "id", "https://evil.sample.org", site="custom")

    def test_custom_widget_key_cannot_authorize_an_untrusted_origin(self):
        with self.assertRaisesRegex(ValueError, "authorized"):
            self.node.create_config("user-entered-secret", "id", "https://evil.sample.org", site="custom")

    def test_string_app_id_type_must_be_preserved(self):
        with self.assertRaisesRegex(ValueError, "STRING"):
            self.node.create_config("", 2109843724737204225, "", site="international")

    def test_node_key_override_requires_authorized_destination(self):
        cfg = self.node.create_config("override", "app", "", site="international")[0]
        self.assertEqual(cfg["api_key"], "override")
        with self.assertRaisesRegex(ValueError, "private or loopback"):
            self.node.create_config("override", "app", "https://127.0.0.1:8190", site="custom")

    def test_client_binding_same_existing_keys(self):
        from importlib import import_module
        security = import_module(self.module.__package__ + ".rh_security")
        self.assertEqual(security.CONFIG_PATH.name, "config.json")
        self.assertNotIn("config.local.json", security.load_private_config.__code__.co_consts)


class NetworkSafetyTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_rh_client()
        self.security = sys.modules[self.mod.__package__ + ".rh_security"]

    def test_malicious_api_origins_are_rejected_before_network(self):
        bad = [
            "http://www.runninghub.ai", "https://www.runninghub.ai.evil.org",
            "https://www.runninghub.ai@evil.org", "https://127.0.0.1:8190",
            "https://10.0.0.1", "https://[::1]", "https://localhost",
            "https://evil.org/path", "https://evil.org/?apiKey=x",
        ]
        calls = []
        session = RecordingSession({"code": 0, "data": {"taskId": "mock"}})
        for origin in bad:
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                self.mod.RHClient("secret", origin, session=session)
        self.assertEqual(session.calls, [])

    def test_every_official_credentialed_call_disables_redirect(self):
        session = RecordingSession({"code": 0, "data": {"taskId": "mock"}})
        client = self.mod.RHClient("secret", "https://www.runninghub.ai", session=session)
        client.create_task("id")
        self.assertIs(session.calls[0][1]["allow_redirects"], False)

    def test_create_redirect_is_uncertain_and_never_retries(self):
        class Redirect:
            status_code = 307
            headers = {"Location": "https://evil.org/steal"}
            def raise_for_status(self): pass
            def json(self): return {"code": 0}
        session = RecordingSession({})
        session.post = lambda url, **kwargs: (session.calls.append((url,kwargs)) or Redirect())
        client = self.mod.RHClient("secret", "https://www.runninghub.ai", session=session)
        with self.assertRaises(self.mod.RHTaskSubmissionUncertainError):
            client.create_task("id")
        self.assertEqual(len(session.calls), 1)

    def test_custom_origin_is_only_allowed_when_locally_authorized(self):
        with patch.object(self.security, "load_private_config",
                          return_value={"trusted_custom_endpoints": {"https://gateway.sample.org": "k"}}):
            client = self.mod.RHClient("k", "https://gateway.sample.org", session=RecordingSession({}))
            self.assertEqual(client.base_url, "https://gateway.sample.org")

    def test_token_not_in_network_query_errors(self):
        session = RecordingSession({"code": 1, "msg": "bad secret-key https://evil.org/path", "data": None})
        client = self.mod.RHClient("secret-key", "https://www.runninghub.ai", session=session)
        result = client.query_task("mock")
        self.assertNotIn("secret-key", result.error)
        self.assertNotIn("evil.org", result.error)

    def test_media_redirect_to_private_address_is_blocked(self):
        outputs = load_rh_outputs()
        class FakeResponse:
            status_code = 302
            headers = {"Location": "http://127.0.0.1:8188/"}
            def close(self): pass
        calls = []
        session = types.SimpleNamespace(get=lambda *a, **k: (calls.append((a,k)) or FakeResponse()))
        with self.assertRaises(ValueError):
            outputs.safe_media_get("https://cdn.sample.org/signed.mp4", session=session)
        self.assertEqual(len(calls), 1)
        self.assertIs(calls[0][1]["allow_redirects"], False)

    def test_media_redirect_limit_is_bounded(self):
        outputs = load_rh_outputs()
        class Redirect:
            status_code = 302
            headers = {"Location": "/next"}
            def close(self): pass
        calls = []
        session = types.SimpleNamespace(get=lambda *a, **k: (calls.append((a,k)) or Redirect()))
        with self.assertRaisesRegex(ValueError, "too many"):
            outputs.safe_media_get("https://cdn.sample.org/a", session=session)
        self.assertEqual(len(calls), 4)

class SafetyEdgeTests(unittest.TestCase):
    def test_redirect_query_is_normalized_as_api_error_without_second_post(self):
        client_mod = load_rh_client()
        calls = []
        class Redirect:
            status_code = 302
            def raise_for_status(self): pass
        session = RecordingSession({})
        session.post = lambda *a, **k: (calls.append((a,k)) or Redirect())
        value = client_mod.RHClient("secret", "https://www.runninghub.ai", session=session).query_task("task")
        self.assertEqual(value.status, "API_ERROR")
        self.assertIn("redirect", value.error.lower())
        self.assertEqual(len(calls), 1)

    def test_upload_response_lost_is_never_retried(self):
        from test_rh_utils_baseline import load_rh_utils
        utils = load_rh_utils()
        calls = []
        def dropped(*args, **kwargs):
            calls.append((args,kwargs))
            raise utils.requests.exceptions.RequestException("https://secret-host/sample?apiKey=private")
        with patch.object(utils.requests, "post", side_effect=dropped):
            with self.assertRaises(RuntimeError) as caught:
                utils.upload_file_to_rh("private", "https://www.runninghub.ai",
                                        b"xyz", "a.bin", "application/octet-stream", "file")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("private", str(caught.exception))
        self.assertNotIn("secret-host", str(caught.exception))

    def test_stream_size_limit_removes_incomplete_download(self):
        from tempfile import TemporaryDirectory
        outputs = load_rh_outputs()
        class Response:
            status_code = 200
            headers = {"Content-Type":"video/mp4"}
            def raise_for_status(self): pass
            def iter_content(self, chunk_size): yield b"012345"
            def close(self): pass
        session = types.SimpleNamespace(get=lambda *a, **k: Response())
        item = outputs.RHOutputItem(index=0, url="https://cdn.sample.org/private.mp4")
        with TemporaryDirectory() as folder, patch.object(outputs, "MAX_DOWNLOAD_BYTES", 4):
            with self.assertRaisesRegex(ValueError, "size limit"):
                outputs.download_output_item(item, folder, session=session)
            self.assertFalse(list(pathlib.Path(folder).glob("*.part")))
            self.assertFalse(list(pathlib.Path(folder).glob("*.mp4")))

if __name__ == "__main__":
    unittest.main()
