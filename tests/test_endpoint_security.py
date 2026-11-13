"""Endpoint trust validation tests without network activity."""

import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rh_endpoint_under_test", ROOT / "nodes" / "rh_config.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EndpointSecurityTests(unittest.TestCase):
    def test_official_https_domains_are_accepted(self):
        self.assertEqual(MODULE._validated_endpoint("https://www.runninghub.ai/"), "https://www.runninghub.ai")
        self.assertEqual(MODULE._validated_endpoint("https://www.runninghub.cn"), "https://www.runninghub.cn")

    def test_untrusted_workflow_urls_are_rejected(self):
        endpoints = [
            "https://www.runninghub.ai.evil.example",
            "https://127.0.0.1",
            "http://www.runninghub.ai",
            "https://www.runninghub.ai/some-path",
            "https://www.runninghub.ai?wrong=1",
            "https://www.runninghub.cn" + chr(64) + "evil.example",
        ]
        for url in endpoints:
            with self.subTest(url=url), self.assertRaises(ValueError):
                MODULE._validated_endpoint(url)

    def test_private_trust_list_must_name_the_exact_https_origin(self):
        host = "https://custom-proxy.example"
        with self.assertRaisesRegex(ValueError, "Untrusted"):
            MODULE._validated_endpoint(host)

        self.assertEqual(MODULE._validated_endpoint(host, {"proxy": host}), host)
        with self.assertRaises(ValueError):
            MODULE._validated_endpoint("http://custom-proxy.example", {"proxy": "http://custom-proxy.example"})
        with self.assertRaises(ValueError):
            MODULE._validated_endpoint(host + "/api", {"proxy": host})


if __name__ == "__main__":
    unittest.main()
