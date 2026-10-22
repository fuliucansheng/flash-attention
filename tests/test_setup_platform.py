"""Check wheel platform selection without executing CUDA build setup."""

import ast
from pathlib import Path
import platform
import sys
import sysconfig
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def load_get_platform():
    source = Path(__file__).resolve().parents[1] / "setup.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [n for n in node.names if n.name in {"sys", "sysconfig", "platform"}]
            if names:
                nodes.append(ast.Import(names=names))
        elif isinstance(node, ast.FunctionDef) and node.name == "get_platform":
            nodes.append(node)
    namespace = {}
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    exec(compile(module, str(source), "exec"), namespace)
    return namespace["get_platform"]


class WheelPlatformTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.get_platform = staticmethod(load_get_platform())

    def test_windows_uses_python_platform(self):
        # A 64-bit x86 Python can run on an ARM64 Windows host. The process
        # platform determines wheel compatibility, not the host CPU name.
        cases = [
            ("win-arm64", "ARM64", "win_arm64"),
            ("win-amd64", "AMD64", "win_amd64"),
            ("win-amd64", "ARM64", "win_amd64"),
            ("win32", "AMD64", "win32"),
        ]
        for python_platform, host_machine, expected in cases:
            with self.subTest(python=python_platform, host=host_machine):
                with patch.object(sys, "platform", "win32"), patch.object(
                    sysconfig, "get_platform", return_value=python_platform
                ), patch.object(platform, "machine", return_value=host_machine):
                    self.assertEqual(self.get_platform(), expected)

    def test_linux_platforms_are_preserved(self):
        for machine in ("x86_64", "aarch64"):
            with self.subTest(machine=machine):
                with patch.object(sys, "platform", "linux"), patch.object(
                    platform, "uname", return_value=SimpleNamespace(machine=machine)
                ):
                    self.assertEqual(self.get_platform(), "linux_" + machine)

    def test_macos_platform_is_preserved(self):
        with patch.object(sys, "platform", "darwin"), patch.object(
            platform, "mac_ver", return_value=("14.5.1", ("", "", ""), "x86_64")
        ):
            self.assertEqual(self.get_platform(), "macosx_14.5_x86_64")

    def test_unsupported_platform_is_rejected(self):
        with patch.object(sys, "platform", "freebsd14"):
            with self.assertRaisesRegex(ValueError, "Unsupported platform: freebsd14"):
                self.get_platform()


if __name__ == "__main__":
    unittest.main()
