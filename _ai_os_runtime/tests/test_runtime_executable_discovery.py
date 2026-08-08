import importlib.util
import os
import sys
from pathlib import Path
from unittest import TestCase, mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("runtime_executables", SCRIPTS / "runtime_executables.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RuntimeExecutableDiscoveryTests(TestCase):
    def test_prefers_configured_then_path_discovery(self):
        with mock.patch.object(MODULE.Path, "is_file", return_value=True):
            with mock.patch.dict(os.environ, {"AI_OS_DOCKER_BIN": "/custom/docker"}):
                self.assertEqual(MODULE.docker_binary(), "/custom/docker")
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(MODULE.shutil, "which", return_value="/path/docker"):
            self.assertEqual(MODULE.docker_binary(), "/path/docker")

    def test_returns_none_when_host_psql_is_absent(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(MODULE.shutil, "which", return_value=None), mock.patch.object(MODULE.Path, "is_file", return_value=False):
            self.assertIsNone(MODULE.psql_binary())
