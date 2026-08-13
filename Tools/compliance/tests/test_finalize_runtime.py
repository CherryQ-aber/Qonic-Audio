from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import finalize_third_party_compliance as finalize


class FinalizeRuntimeTests(unittest.TestCase):
    def _runtime_root(self, parent: Path, *, with_license: bool = True) -> Path:
        root = parent / "cpython-runtime"
        root.mkdir()
        (root / "python.exe").write_bytes(b"synthetic executable")
        if with_license:
            (root / "LICENSE.txt").write_text("PSF synthetic fixture", encoding="utf-8")
        return root

    def test_explicit_runtime_root_validates_cpython_version_and_license(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._runtime_root(Path(temp_dir))
            with mock.patch.object(
                finalize,
                "_read_runtime_identity",
                return_value=("CPython", "3.12.1"),
            ):
                self.assertEqual(finalize.resolve_python_runtime_root(root), root.resolve())

    def test_runtime_root_requires_license(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._runtime_root(Path(temp_dir), with_license=False)
            with self.assertRaisesRegex(FileNotFoundError, "LICENSE.txt"):
                finalize.validate_python_runtime_root(root)

    def test_runtime_root_rejects_wrong_implementation_or_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._runtime_root(Path(temp_dir))
            with mock.patch.object(
                finalize,
                "_read_runtime_identity",
                return_value=("PyPy", "3.12.1"),
            ):
                with self.assertRaisesRegex(ValueError, "需要 CPython"):
                    finalize.validate_python_runtime_root(root)
            with mock.patch.object(
                finalize,
                "_read_runtime_identity",
                return_value=("CPython", "3.12.9"),
            ):
                with self.assertRaisesRegex(ValueError, "3.12.1"):
                    finalize.validate_python_runtime_root(root)

    def test_auto_discovery_uses_valid_active_environment_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            parent = Path(temp_dir)
            invalid = parent / "missing-runtime"
            valid = self._runtime_root(parent)
            with (
                mock.patch.object(
                    finalize,
                    "_runtime_root_candidates",
                    return_value=[invalid, valid],
                ),
                mock.patch.object(
                    finalize,
                    "_read_runtime_identity",
                    return_value=("CPython", "3.12.1"),
                ),
            ):
                self.assertEqual(finalize.resolve_python_runtime_root(), valid.resolve())


if __name__ == "__main__":
    unittest.main()
