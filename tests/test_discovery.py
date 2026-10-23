"""Read-only discovery tests with synthetic fixtures and injected commands."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from wg_deck.core.discovery import (
    discover,
    system_runner,
    parse_endpoint,
    parse_handshake,
    parse_interface_names,
    parse_ip_links,
    parse_systemd_instances,
    parse_transfer,
    valid_interface,
)
from wg_deck.core.models import TunnelState


class ParserTests(unittest.TestCase):
    def test_valid_names_block_traversal_and_overlong_interfaces(self):
        self.assertTrue(valid_interface("wg0"))
        for name in ("../../x", "", "..", "name with spaces", "very-long-interface-name"):
            self.assertFalse(valid_interface(name), name)

    def test_peer_aggregates_without_retaining_keys(self):
        self.assertEqual(parse_transfer("peer_a 400 200\npeer_b 100 50\n"), (500, 250))
        self.assertEqual(parse_handshake("peer_a 0\npeer_b 123456\n"), 123456)
        self.assertEqual(parse_endpoint("abc example.com:51820\n"), "example.com:51820")

    def test_runner_rejects_unsafe_commands_without_invocation(self):
        self.assertEqual(system_runner(("wg", "showconf", "wg0")), (127, ""))
        self.assertEqual(system_runner(("systemctl", "stop", "wg-quick@wg0")), (127, ""))
        self.assertEqual(system_runner(("wg", "show", "../bad", "transfer")), (127, ""))

    def test_names_and_malformed_ip_json(self):
        self.assertEqual(parse_interface_names("wg0 wg1 ../../danger"), {"wg0", "wg1"})
        self.assertEqual(parse_systemd_instances("wg-quick@wg0.service enabled\nwg-quick@.service disabled\n"), {"wg0"})
        self.assertEqual(parse_ip_links('[{"ifname":"wg1"},{"ifname":"verylonginterfacename"}]'), {"wg1"})
        self.assertEqual(parse_ip_links("not json"), set())


class DiscoveryTests(unittest.TestCase):
    def test_inventory_does_not_open_config_or_change_connections(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "home.conf").write_text("[Interface]\nPrivateKey = secret-do-not-read\n")
            (path / "bad name.conf").write_text("ignored")
            commands = []

            def runner(args):
                commands.append(args)
                responses = {
                    ("wg", "show", "interfaces"): (0, "home wg0"),
                    ("ip", "-j", "link", "show", "type", "wireguard"): (0, '[{"ifname":"wg0"}]'),
                    ("systemctl", "list-unit-files", "--type=service", "--no-legend", "--no-pager", "wg-quick@*.service"): (0, ""),
                    ("wg", "--version"): (0, "wireguard-tools v1"),
                    ("wg", "show", "home", "endpoints"): (0, "fake-peer vpn.example:51820"),
                    ("wg", "show", "home", "latest-handshakes"): (0, "fake-peer 1234"),
                    ("wg", "show", "home", "transfer"): (0, "fake-peer 100 20"),
                    ("wg", "show", "wg0", "endpoints"): (0, ""),
                    ("wg", "show", "wg0", "latest-handshakes"): (0, ""),
                    ("wg", "show", "wg0", "transfer"): (0, ""),
                }
                return responses.get(args, (127, ""))

            result = discover(directories=(path,), runner=runner)
            self.assertEqual([p.name for p in result.profiles], ["home", "wg0"])
            self.assertEqual(result.profiles[0].state, TunnelState.UP)
            self.assertEqual(result.profiles[0].rx_bytes, 100)
            self.assertFalse(any("secret-do-not-read" in str(x) for x in result.profiles))
            self.assertFalse(any("up" in args or "down" in args or "showconf" in args for args in commands))

    def test_ip_observed_up_but_wg_permission_denied_has_unknown_counters(self):
        def runner(command):
            if command == ("ip", "-j", "link", "show", "type", "wireguard"):
                return 0, '[{"ifname":"demo-vpn"}]'
            if command == ("wg", "--version"):
                return 0, "wireguard-tools"
            return 1, "permission denied"

        snapshot = discover(directories=(), runner=runner, extra_names=("demo-vpn",))
        self.assertEqual(snapshot.profiles[0].state, TunnelState.UP)
        self.assertIsNone(snapshot.profiles[0].rx_bytes)
        self.assertIsNone(snapshot.profiles[0].tx_bytes)

    def test_unprivileged_tools_failure_does_not_imply_connected(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "lab.conf").write_text("[Interface]\n")
            result = discover(directories=(Path(directory),), runner=lambda args: (1, "permission denied"))
            self.assertEqual(result.profiles[0].state, TunnelState.UNKNOWN)
            self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
