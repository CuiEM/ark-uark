"""End-to-end checks for the two commands and their volume format."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        (self.source / "nested").mkdir(parents=True)
        (self.source / "nested" / "data.bin").write_bytes(os.urandom(4096))
        (self.source / "中文.txt").write_text("archive test\n", encoding="utf-8")

    def command(self, module, *args, expect_success=True):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(PROJECT / "src") + os.pathsep + environment.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-m", f"ark_uark.{module}", *(str(arg) for arg in args)],
            cwd=self.root, env=environment, text=True, capture_output=True,
            check=False,
        )
        if expect_success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stderr)
        return result

    def assert_round_trip(self, destination):
        for relative in ("nested/data.bin", "中文.txt"):
            self.assertEqual(
                (destination / "source" / relative).read_bytes(),
                (self.source / relative).read_bytes(),
            )

    def test_tar_and_zip_formats(self):
        formats = ("tar", "tar.gz", "tar.bz2", "tar.xz", "tar.zst", "zip")
        for fmt in formats:
            codec = fmt.split(".")[-1]
            if fmt.startswith("tar") and not shutil.which("tar"):
                continue
            if codec in ("gz", "bz2", "xz", "zst") and not shutil.which(
                {"gz": "gzip", "bz2": "bzip2", "xz": "xz", "zst": "zstd"}[codec]
            ):
                continue
            with self.subTest(fmt=fmt):
                archive = self.root / f"bundle.{fmt}"
                destination = self.root / f"unpacked-{fmt}"
                self.command("ark", self.source, "-o", archive)
                self.command("uark", archive, "-C", destination)
                self.assert_round_trip(destination)

    def test_default_format(self):
        if not shutil.which("tar") or not shutil.which("gzip"):
            self.skipTest("GNU tar and gzip are required")
        self.command("ark", self.source)
        archive = self.root / "source.tar.gz"
        self.assertTrue(archive.is_file())
        destination = self.root / "default-unpacked"
        self.command("uark", archive, "-C", destination)
        self.assert_round_trip(destination)

    def test_default_extraction_uses_archive_directory(self):
        for fmt in ("tar.gz", "zip", "gz"):
            with self.subTest(fmt=fmt):
                archive_dir = self.root / f"archives-{fmt}"
                archive_dir.mkdir()
                source = self.source / "中文.txt" if fmt == "gz" else self.source
                archive = archive_dir / f"bundle.{fmt}"
                self.command("ark", source, "-o", archive)
                self.command("uark", archive)
                self.assertFalse((archive_dir / "bundle.unpacked").exists())
                if fmt == "gz":
                    self.assertEqual((archive_dir / "bundle").read_bytes(), source.read_bytes())
                else:
                    self.assert_round_trip(archive_dir)

    def test_default_extraction_does_not_overwrite(self):
        archive_dir = self.root / "existing-output"
        archive_dir.mkdir()
        archive = archive_dir / "bundle.zip"
        self.command("ark", self.source, "-o", archive)
        existing = archive_dir / "source"
        existing.mkdir()
        (existing / "sentinel.txt").write_text("keep", encoding="utf-8")
        result = self.command("uark", archive, expect_success=False)
        self.assertIn("输出路径已存在", result.stderr)
        self.assertEqual((existing / "sentinel.txt").read_text(encoding="utf-8"), "keep")
        self.assertFalse((existing / "nested").exists())
        self.assertFalse(list(archive_dir.glob(".unpack-*")))

    def test_split_tar_zstd_and_zip(self):
        for fmt in ("tar.zst", "zip"):
            if fmt == "tar.zst" and (not shutil.which("tar") or not shutil.which("zstd")):
                continue
            with self.subTest(fmt=fmt):
                archive = self.root / f"split.{fmt}"
                self.command("ark", self.source, "-v", "256", "-o", archive)
                parts = sorted(self.root.glob(archive.name + ".part*"))
                self.assertGreater(len(parts), 1)
                self.assertTrue(all(0 < part.stat().st_size <= 256 for part in parts))
                destination = self.root / f"split-unpacked-{fmt}"
                self.command("uark", parts[1], "-C", destination)
                self.assert_round_trip(destination)

    def test_split_single_file_formats(self):
        source = self.source / "中文.txt"
        for fmt in ("gz", "bz2", "xz", "zst"):
            program = {"gz": "gzip", "bz2": "bzip2", "xz": "xz", "zst": "zstd"}[fmt]
            if not shutil.which(program):
                continue
            with self.subTest(fmt=fmt):
                archive = self.root / f"sample.{fmt}"
                destination = self.root / f"single-{fmt}"
                self.command("ark", source, "-f", fmt, "-v", "9", "-o", archive)
                self.command("uark", self.root / f"sample.{fmt}.part0000", "-C", destination)
                self.assertEqual((destination / "sample").read_bytes(), source.read_bytes())

    def test_refuses_overwrite_and_invalid_destination(self):
        output = self.root / "existing.zip"
        output.write_bytes(b"keep this file")
        self.command("ark", self.source, "-o", output, expect_success=False)
        self.assertEqual(output.read_bytes(), b"keep this file")

        inside = self.source / "newdir" / "archive.tar.gz"
        self.command("ark", self.source, "-o", inside, expect_success=False)
        self.assertFalse(inside.parent.exists())

    def test_missing_volume_is_rejected(self):
        archive = self.root / "incomplete.zip"
        self.command("ark", self.source, "-v", "256", "-o", archive)
        (self.root / "incomplete.zip.part0001").unlink()
        result = self.command("uark", self.root / "incomplete.zip.part0000", expect_success=False)
        self.assertIn("分卷缺失", result.stderr)
        self.assertFalse(list(self.root.glob(".unpack-*")))


if __name__ == "__main__":
    unittest.main()
