from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from common import duplicate_groups, sha256_file
from hash_files import hash_paths


class HashFilesTests(unittest.TestCase):

    def test_sha256_matches_hashlib(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.bin"
            payload = b"qonic-compliance"
            path.write_bytes(payload)
            self.assertEqual(
                sha256_file(path),
                hashlib.sha256(payload).hexdigest().upper(),
            )

    def test_unicode_and_space_path_is_supported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "中文 目录" / "音频 文件.bin"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"audio")
            result = hash_paths([root], root)
            self.assertEqual(len(result["files"]), 1)
            self.assertEqual(result["files"][0]["path"], "中文 目录/音频 文件.bin")

    def test_duplicate_groups_use_content_hash_not_timestamp(self):
        records = [
            {"path": "a.bin", "sha256": "A" * 64},
            {"path": "b.bin", "sha256": "A" * 64},
            {"path": "c.bin", "sha256": "B" * 64},
        ]
        self.assertEqual(
            duplicate_groups(records),
            [{"sha256": "A" * 64, "paths": ["a.bin", "b.bin"]}],
        )


if __name__ == "__main__":
    unittest.main()
