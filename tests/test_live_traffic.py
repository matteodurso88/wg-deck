"""End-to-end synthetic WireGuard traffic monitoring tests.

Tests never read a real /etc/wireguard config, prompt Polkit or change links.
"""
from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wg_deck.core.traffic import (
    TrafficRow, parse_traffic_snapshot, read_native_traffic,
)
from wg_deck.core.discovery import Inventory
from wg_deck.core.models import ProfileSnapshot, TunnelState


SOURCE = Path(__file__).resolve().parents[1] / "privileged" / "wgdeck_inventory.py"
SPEC = importlib.util.spec_from_file_location("wgdeck_metrics_publisher", SOURCE)
assert SPEC is not None and SPEC.loader is not None
PUBLISHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PUBLISHER)


class MetricsSecurityTests(unittest.TestCase):
    def test_root_publisher_sums_peer_transfer_and_does_not_publish_public_keys(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "traffic.tsv"
            def output(*args):
                responses = {
                    ("show", "interfaces"): "demo-lab demo-vpn",
                    ("show", "demo-lab", "transfer"): "PRIVATE-PEER-PUB-KEY-A 110 55\nPRIVATE-PEER-PUB-KEY-B 220 66\n",
                    ("show", "demo-lab", "latest-handshakes"): "PRIVATE-PEER-PUB-KEY-A 1700000010\nPRIVATE-PEER-PUB-KEY-B 0\n",
                    ("show", "demo-vpn", "transfer"): "PRIVATE-PEER-PUB-KEY-C 600 300\n",
                    ("show", "demo-vpn", "latest-handshakes"): "PRIVATE-PEER-PUB-KEY-C 1700000008\n",
                }
                return responses[args]
            with (
                patch.object(PUBLISHER.os, "geteuid", return_value=0),
                patch.object(PUBLISHER.os, "fchown"),
                patch.object(PUBLISHER, "_wg_lines", side_effect=output),
            ):
                PUBLISHER.publish_traffic(
                    ("demo-lab", "demo-vpn", "down-lab"), path,
                    reader_gid=os.getgid(), now=1700000020,
                )
            raw = path.read_bytes()
            self.assertNotIn(b"PRIVATE", raw)
            self.assertNotIn(b"PeerKey", raw)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
            rows = parse_traffic_snapshot(raw, now=1700000020)
            self.assertEqual(rows["demo-lab"], TrafficRow(True, 330, 121, 1700000010))
            self.assertEqual(rows["demo-vpn"], TrafficRow(True, 600, 300, 1700000008))
            self.assertEqual(rows["down-lab"], TrafficRow(False, 0, 0, None))

    def test_missing_privileged_wg_never_publishes_fabricated_down_or_zero(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / "traffic.tsv"
            with patch.object(PUBLISHER.os, "geteuid", return_value=0), patch.object(
                PUBLISHER, "_wg_lines", return_value=None
            ), patch.object(PUBLISHER.os, "fchown"):
                PUBLISHER.publish_traffic(("demo-vpn",), file, reader_gid=os.getgid())
            self.assertFalse(file.exists())

    def test_missing_active_transfer_uses_explicit_unavailable_marker(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / "traffic.tsv"
            with (
                patch.object(PUBLISHER.os, "geteuid", return_value=0),
                patch.object(PUBLISHER.os, "fchown"),
                patch.object(PUBLISHER, "_wg_lines", side_effect=[
                    "demo-vpn", None, None,
                ]),
            ):
                PUBLISHER.publish_traffic(("demo-vpn",), file, reader_gid=os.getgid(), now=1700000020)
            rows = parse_traffic_snapshot(file.read_bytes(), now=1700000020)
            self.assertEqual(rows["demo-vpn"], TrafficRow(True, None, None, None))

    def test_reject_stale_future_duplicate_secret_like_and_out_of_range_snapshots(self):
        cases = [
            b"WGDECK-TRAFFIC-V1\t100\nwg0\tUP\t1\t2\t3\n",   # stale
            b"WGDECK-TRAFFIC-V1\t200\nwg0\tUP\t1\t2\t3\n",   # future
            b"WGDECK-TRAFFIC-V1\t180\nwg0\tUP\t1\t2\t3\nwg0\tUP\t1\t2\t3\n",
            b"WGDECK-TRAFFIC-V1\t180\n../bad\tUP\t1\t2\t3\n",
            b"WGDECK-TRAFFIC-V1\t180\nwg0\tUP\tKEY\t2\t3\n",
            b"WGDECK-TRAFFIC-V1\t180\nwg0\tUP\t18446744073709551616\t2\t3\n",
            b"WGDECK-TRAFFIC-V1\t180\nwg0\tDOWN\t1\t2\t3\n",
        ]
        for data in cases:
            with self.subTest(data=data[:60]), self.assertRaises(ValueError):
                parse_traffic_snapshot(data, now=180)

    def test_unprivileged_reader_rejects_symlink_or_untrusted_group_write(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "stats.tsv"
            target.write_bytes(b"WGDECK-TRAFFIC-V1\t180\nwg0\tUP\t12\t24\t0\n")
            target.chmod(0o640)
            info = target.stat()
            root = SimpleNamespace(st_mode=info.st_mode, st_uid=0, st_size=info.st_size)
            with patch("wg_deck.core.traffic.os.fstat", return_value=root):
                self.assertEqual(read_native_traffic(target, now=180)["wg0"].tx_bytes, 24)
            with patch("wg_deck.core.traffic.os.fstat", return_value=SimpleNamespace(
                st_mode=stat.S_IFREG | 0o664, st_uid=0, st_size=info.st_size,
            )):
                self.assertIsNone(read_native_traffic(target, now=180))
            link = Path(directory) / "link.tsv"
            link.symlink_to(target)
            self.assertIsNone(read_native_traffic(link, now=180))

    def test_inventory_worker_overrides_nonprivileged_zero_and_keeps_native_filter(self):
        from wg_deck.ui.window import InventoryWorker
        names = ("demo-vpn", "demo-lab")
        discovery = Inventory((
            ProfileSnapshot("demo-vpn", TunnelState.UP),
            ProfileSnapshot("demo-lab", TunnelState.DOWN),
            ProfileSnapshot("stray-interface", TunnelState.UP),
        ), (), "wireguard-tools", True)
        result = []
        worker = InventoryWorker()
        worker.signals.finished.connect(result.append)
        with (
            patch("wg_deck.ui.window.read_native_names", return_value=names),
            patch("wg_deck.ui.window.discover", return_value=discovery),
            patch("wg_deck.ui.window.read_native_traffic", return_value={
                "demo-vpn": TrafficRow(True, 4900, 360, 1700000010),
                "demo-lab": TrafficRow(False, 0, 0, None),
            }),
        ):
            worker.run()
        self.assertEqual([p.name for p in result[0].profiles], list(names))
        self.assertEqual(result[0].profiles[0].rx_bytes, 4900)
        self.assertEqual(result[0].profiles[0].tx_bytes, 360)
        self.assertEqual(result[0].profiles[0].last_handshake, 1700000010)

    def test_systemd_root_timer_is_read_only_and_netlink_scoped(self):
        unit = (SOURCE.parent / "wg-deck-inventory.service").read_text()
        timer = (SOURCE.parent / "wg-deck-inventory.timer").read_text()
        self.assertIn("CapabilityBoundingSet=CAP_CHOWN CAP_NET_ADMIN", unit)
        self.assertIn("RestrictAddressFamilies=AF_UNIX AF_NETLINK", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("ReadOnlyPaths=/etc/wireguard", unit)
        self.assertIn("ReadWritePaths=/run", unit)
        self.assertIn("OnUnitInactiveSec=10s", timer)
        self.assertIn("Unit=wg-deck-inventory.service", timer)
        self.assertNotIn("wg-quick up", unit + timer)

    def test_qt_total_transfer_updates_and_unavailable_is_not_zero(self):
        import subprocess
        import sys
        script = r"""
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from wg_deck.ui.window import MainWindow
from wg_deck.core.discovery import Inventory
from wg_deck.core.models import ProfileSnapshot, TunnelState
app = QApplication([])
window = MainWindow(demo=True)
first = Inventory((ProfileSnapshot("demo-vpn", TunnelState.UP,
                                  rx_bytes=1024, tx_bytes=2048),), ())
second = Inventory((ProfileSnapshot("demo-vpn", TunnelState.UP,
                                   rx_bytes=3072, tx_bytes=4096),), ())
window.accept_inventory(first)
assert "3.0 KiB" in window.metrics[3].text()
with patch("wg_deck.ui.window.time.monotonic", return_value=100):
    window._traffic_sample = (90, {"demo-vpn": (1024, 2048)})
    window.accept_inventory(second)
assert "/s" in window.metric_details[3].text()
unavailable = Inventory((ProfileSnapshot("demo-vpn", TunnelState.UP,
                                        rx_bytes=None, tx_bytes=None),), ())
window.accept_inventory(unavailable)
assert window.metrics[3].text() == "Unavailable"
assert "unavailable" in window.metric_details[3].text().lower()
window.close()
"""
        with tempfile.TemporaryDirectory() as folder:
            env = os.environ.copy()
            env["QT_QPA_PLATFORM"] = "offscreen"
            env["XDG_CONFIG_HOME"] = folder
            env.pop("PYTHONPATH", None)
            result = subprocess.run(
                [sys.executable, "-c", script], env=env, capture_output=True,
                text=True, timeout=40, check=False,
            )
        self.assertEqual(
            result.returncode, 0,
            f"Traffic UI smoke failed: {result.stdout}\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
