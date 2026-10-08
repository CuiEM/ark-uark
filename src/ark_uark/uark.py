#!/usr/bin/env python3
"""Extract common archives with one live progress line."""

import argparse
from bisect import bisect_right
import bz2
from collections import deque
import gzip
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unicodedata
import zipfile

from .tar_tools import tar_program


CHUNK = 1024 * 1024
PART_RE = re.compile(r"^(.*)\.part(\d{4,})$")
MAGIC = {
    b"\x1f\x8b": "gz",
    b"BZh": "bz2",
    b"\xfd7zXZ\x00": "xz",
    b"\x28\xb5\x2f\xfd": "zst",
}


class UnpackError(Exception):
    pass


def display_width(value):
    return sum(0 if unicodedata.combining(char) else
               2 if unicodedata.east_asian_width(char) in "WF" else 1
               for char in value)


def fit_tail(value, width):
    value = "".join(char if unicodedata.category(char)[0] != "C" else "?"
                    for char in value)
    if display_width(value) <= width:
        return value
    result = ""
    for char in reversed(value):
        if display_width(result) + display_width(char) > width - 3:
            break
        result = char + result
    return "..." + result


class PartsReader:
    def __init__(self, parts):
        self.parts = iter(parts)
        self.current = None

    def read(self, size=-1):
        chunks = []
        remaining = size
        while remaining != 0:
            if self.current is None:
                try:
                    self.current = next(self.parts).open("rb")
                except StopIteration:
                    break
            chunk = self.current.read(remaining)
            if not chunk:
                self.current.close()
                self.current = None
                continue
            chunks.append(chunk)
            if size > 0:
                remaining -= len(chunk)
        return b"".join(chunks)

    def close(self):
        if self.current is not None:
            self.current.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class SplitSeekableReader:
    def __init__(self, parts):
        self.parts = parts
        self.offsets = [0]
        for part in parts:
            self.offsets.append(self.offsets[-1] + part.stat().st_size)
        self.position = 0
        self.current_index = None
        self.current_file = None

    def read(self, size=-1):
        remaining = self.offsets[-1] - self.position
        if size >= 0:
            remaining = min(remaining, size)
        chunks = []
        while remaining > 0:
            index = bisect_right(self.offsets, self.position) - 1
            if index != self.current_index:
                self.close_file()
                self.current_file = self.parts[index].open("rb")
                self.current_index = index
            self.current_file.seek(self.position - self.offsets[index])
            chunk = self.current_file.read(min(remaining, self.offsets[index + 1] - self.position))
            if not chunk:
                raise OSError(f"分卷读取未完成：{self.parts[index]}")
            chunks.append(chunk)
            self.position += len(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def seek(self, offset, whence=0):
        base = {0: 0, 1: self.position, 2: self.offsets[-1]}.get(whence)
        if base is None or base + offset < 0:
            raise OSError("无效的分卷定位")
        self.position = base + offset
        return self.position

    def tell(self):
        return self.position

    def seekable(self):
        return True

    def readable(self):
        return True

    def close_file(self):
        if self.current_file:
            self.current_file.close()
        self.current_file = None
        self.current_index = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close_file()


class Progress:
    def __init__(self, total, current=""):
        self.total = total
        self.done = 0
        self.current = current
        self.started = time.monotonic()
        self.last_print = 0
        self.samples = deque()
        self.tty = sys.stderr.isatty()
        self.last_line = None

    def advance(self, amount):
        self.done += amount
        now = time.monotonic()
        self.samples.append((now, self.done))
        while self.samples and now - self.samples[0][0] > 15:
            self.samples.popleft()
        self.render(now)

    def render(self, now=None, force=False):
        now = now or time.monotonic()
        if not self.tty and not force and now - self.started < 5:
            return
        interval = 0.15 if self.tty else 5
        if not force and now - self.last_print < interval:
            return
        self.last_print = now
        fraction = min(1, self.done / self.total) if self.total else 1
        width = max(10, min(28, shutil.get_terminal_size((100, 20)).columns // 4))
        filled = round(width * fraction)
        bar = "#" * filled + "-" * (width - filled)
        eta = "--:--"
        if fraction == 1:
            eta = "00:00"
        elif len(self.samples) > 1:
            elapsed = self.samples[-1][0] - self.samples[0][0]
            speed = (self.samples[-1][1] - self.samples[0][1]) / elapsed if elapsed else 0
            if speed > 0:
                remaining = int((self.total - self.done) / speed)
                eta = f"{remaining // 3600:d}:{remaining // 60 % 60:02d}:{remaining % 60:02d}"
        prefix = f"[{bar}] {fraction:6.1%} ETA {eta}  "
        columns = shutil.get_terminal_size((100, 20)).columns
        available = max(8, columns - len(prefix) - 1)
        name = fit_tail(self.current, available)
        line = prefix + name
        if self.tty:
            sys.stderr.write("\r\x1b[2K" + line)
        else:
            if line == self.last_line:
                return
            sys.stderr.write(line + "\n")
        self.last_line = line
        sys.stderr.flush()

    def finish(self):
        self.done = self.total
        self.render(force=True)
        if self.tty:
            sys.stderr.write("\n")
            sys.stderr.flush()


def parts_for(path):
    match = PART_RE.match(path.name)
    if not match:
        return [path], path.name
    stem, digits = match.groups()
    matches = sorted(path.parent.glob(stem + ".part*"))
    numbered = []
    for candidate in matches:
        item = PART_RE.match(candidate.name)
        if item and item.group(1) == stem and len(item.group(2)) == len(digits):
            numbered.append((int(item.group(2)), candidate))
    numbered.sort()
    if not numbered or [i for i, _ in numbered] != list(range(len(numbered))):
        raise UnpackError("分卷缺失或不是从 part0000 开始")
    return [candidate for _, candidate in numbered], stem


def tar_header(header):
    if len(header) < 512:
        return None
    try:
        return tarfile.TarInfo.frombuf(header[:512], encoding="utf-8", errors="replace")
    except (tarfile.TarError, ValueError):
        return None


def peek_zstd(parts):
    proc = subprocess.Popen(["zstd", "-dcq"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def feed():
        try:
            with PartsReader(parts) as source:
                while chunk := source.read(CHUNK):
                    proc.stdin.write(chunk)
        except (BrokenPipeError, OSError, ValueError):
            pass
        finally:
            try:
                proc.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass

    feeder = threading.Thread(target=feed, daemon=True)
    feeder.start()
    try:
        return proc.stdout.read(512)
    finally:
        proc.terminate()
        feeder.join()
        proc.wait()
        proc.stdout.close()


def detect(parts):
    with PartsReader(parts) as source:
        header = source.read(65536)
    if header.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "zip", ""
    if header.startswith(b"7z\xbc\xaf\x27\x1c"):
        raise UnpackError("7z 格式需要单独安装 7z，当前命令尚不支持")
    if header.startswith((b"Rar!\x1a\x07\x00", b"Rar!\x1a\x07\x01\x00")):
        raise UnpackError("RAR 格式需要单独安装 7z 或 unrar，当前命令尚不支持")
    info = tar_header(header)
    if info:
        return "tar", info.name
    for magic, kind in MAGIC.items():
        if not header.startswith(magic):
            continue
        if kind == "zst":
            if not shutil.which("zstd"):
                raise UnpackError("zstd 未安装")
            inner = peek_zstd(parts)
        else:
            opener = {"gz": gzip.GzipFile, "bz2": bz2.BZ2File, "xz": lzma.LZMAFile}[kind]
            with PartsReader(parts) as source:
                with opener(fileobj=source, mode="rb") if kind == "gz" else opener(source, "rb") as compressed:
                    inner = compressed.read(512)
        info = tar_header(inner)
        return ("tar." + kind, info.name) if info else (kind, "")
    raise UnpackError("无法识别压缩格式")


def default_name(logical_name):
    lower = logical_name.lower()
    for suffix in (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst",
                   ".tgz", ".tbz2", ".txz", ".tzst", ".zip",
                   ".tar", ".gz", ".bz2", ".xz", ".zst"):
        if lower.endswith(suffix):
            return logical_name[:-len(suffix)]
    return logical_name


def pump(parts, proc, progress):
    try:
        for part in parts:
            with part.open("rb") as source:
                while chunk := source.read(CHUNK):
                    proc.stdin.write(chunk)
                    progress.advance(len(chunk))
    except BrokenPipeError:
        pass
    finally:
        try:
            proc.stdin.close()
        except BrokenPipeError:
            pass


def run_stream(parts, command, progress, output=None, show_names=False,
               names_on_stderr=False):
    errors = deque(maxlen=12)
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=output or subprocess.PIPE,
                            stderr=subprocess.PIPE)

    def read_names():
        for line in proc.stdout:
            name = line.decode("utf-8", "replace").rstrip("\r\n")
            if name:
                progress.current = name

    def read_errors():
        for raw in proc.stderr:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if names_on_stderr and line.startswith("x "):
                progress.current = line[2:]
            else:
                errors.append(line)

    threads = [threading.Thread(target=read_errors, daemon=True)]
    if show_names:
        threads.append(threading.Thread(target=read_names, daemon=True))
    for thread in threads:
        thread.start()
    try:
        pump(parts, proc, progress)
        code = proc.wait()
    except BaseException:
        proc.terminate()
        proc.wait()
        raise
    finally:
        for thread in threads:
            thread.join()
    if code:
        raise UnpackError("解压失败：" + ("\n".join(errors) or f"退出码 {code}"))


def extract_tar(parts, kind, destination, progress):
    program, implementation = tar_program()
    option = {"tar": [], "tar.gz": ["-z"], "tar.bz2": ["-j"],
              "tar.xz": ["-J"], "tar.zst": ["--zstd"]}[kind]
    options = ["--no-same-owner", "--no-same-permissions"]
    if implementation == "gnu":
        options += ["--no-overwrite-dir", "--warning=no-timestamp",
                    "--quoting-style=escape"]
    elif kind == "tar.zst":
        # Older macOS libarchive versions have no built-in zstd support.
        option = ["--use-compress-program", "zstd -dcq"]
    command = [program, *option, "-xvf", "-", "-C", str(destination), *options]
    if implementation == "gnu":
        buffer = shutil.which("stdbuf") or shutil.which("gstdbuf")
        if buffer:
            command = [buffer, "-oL", *command]
    run_stream(parts, command, progress, show_names=implementation == "gnu",
               names_on_stderr=implementation == "bsd")


def extract_single(parts, logical_name, kind, destination, progress):
    name = default_name(logical_name)
    if name == logical_name:
        name += ".out"
    output = destination / name
    if output.exists():
        raise UnpackError(f"输出文件已存在：{output}")
    progress.current = name
    command = {"gz": ["gzip", "-dc"], "bz2": ["bzip2", "-dc"],
               "xz": ["xz", "-dc"], "zst": ["zstd", "-dcq"]}[kind]
    try:
        with output.open("xb") as target:
            run_stream(parts, command, progress, output=target)
    except BaseException:
        output.unlink(missing_ok=True)
        raise


def extract_zip(parts, destination, progress):
    source = parts[0].open("rb") if len(parts) == 1 else SplitSeekableReader(parts)
    with source, zipfile.ZipFile(source) as archive:
        files = archive.infolist()
        progress.total = sum(item.file_size for item in files if not item.is_dir())
        base = destination.resolve()
        for item in files:
            relative = PurePosixPath(item.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise UnpackError(f"ZIP 包含不安全路径：{item.filename}")
            if stat.S_ISLNK(item.external_attr >> 16):
                raise UnpackError(f"ZIP 包含符号链接：{item.filename}")
            target = destination.joinpath(*relative.parts)
            if not target.resolve().is_relative_to(base):
                raise UnpackError(f"ZIP 路径超出目标目录：{item.filename}")
            progress.current = item.filename
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, target.open("xb") as output:
                while chunk := source.read(CHUNK):
                    output.write(chunk)
                    progress.advance(len(chunk))


def publish_staging(staging, destination):
    entries = list(staging.iterdir())
    for source in entries:
        target = destination / source.name
        if target.exists() or target.is_symlink():
            shutil.rmtree(staging)
            raise UnpackError(f"输出路径已存在：{target}")

    published = []
    try:
        for source in entries:
            target = destination / source.name
            if target.exists() or target.is_symlink():
                raise UnpackError(f"输出路径已存在：{target}")
            source.rename(target)
            published.append((source, target))
    except BaseException:
        for source, target in reversed(published):
            target.rename(source)
        raise
    staging.rmdir()


def main():
    parser = argparse.ArgumentParser(description="自动识别格式并显示解压进度、当前文件和 ETA")
    parser.add_argument("archive", type=Path, help="压缩包路径；分卷可指定任一 partNNNN")
    parser.add_argument("-C", "--directory", type=Path, help="解压到指定目录（默认压缩包所在目录）")
    args = parser.parse_args()
    archive = args.archive.expanduser().resolve()
    if not archive.is_file():
        raise UnpackError(f"文件不存在：{archive}")
    parts, logical_name = parts_for(archive)
    kind, first_name = detect(parts)
    final = args.directory.expanduser().resolve() if args.directory else archive.parent
    staging = None
    if args.directory:
        final.mkdir(parents=True, exist_ok=True)
        destination = final
    else:
        staging = Path(tempfile.mkdtemp(prefix=".unpack-", dir=archive.parent))
        destination = staging

    total = sum(part.stat().st_size for part in parts)
    progress = Progress(total, first_name or logical_name)
    try:
        if progress.tty:
            progress.render(force=True)
        if kind == "zip":
            extract_zip(parts, destination, progress)
        elif kind.startswith("tar"):
            extract_tar(parts, kind, destination, progress)
        else:
            extract_single(parts, logical_name, kind, destination, progress)
        if staging:
            publish_staging(staging, final)
            staging = None
        progress.finish()
    except BaseException:
        if progress.tty:
            sys.stderr.write("\n")
        if staging and staging.exists():
            if any(staging.iterdir()):
                sys.stderr.write(f"未完成的文件保留在：{staging}\n")
            else:
                staging.rmdir()
        raise


def cli():
    try:
        main()
    except (UnpackError, OSError, EOFError, RuntimeError, ValueError,
            zipfile.BadZipFile) as error:
        sys.stderr.write(f"{Path(sys.argv[0]).name}: {error}\n")
        sys.exit(1)


if __name__ == "__main__":
    cli()
