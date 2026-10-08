#!/usr/bin/env python3
"""Create archives and optional raw split volumes compatible with uark."""

import argparse
from collections import deque
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import zipfile


CHUNK = 1024 * 1024
FORMATS = ("tar", "tar.gz", "tar.bz2", "tar.xz", "tar.zst",
           "zip", "gz", "bz2", "xz", "zst")
SINGLE_FILE_FORMATS = {"gz", "bz2", "xz", "zst"}
CODECS = {
    "gz": ["gzip", "-cn"],
    "bz2": ["bzip2", "-c"],
    "xz": ["xz", "-c"],
    "zst": ["zstd", "-cq"],
}
SIZE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*([KMGT]?I?B?|B)?$", re.IGNORECASE)


class ArkError(Exception):
    pass


def parse_size(value):
    match = SIZE_RE.fullmatch(value.strip())
    if not match:
        raise argparse.ArgumentTypeError("分卷大小示例：500M、1.5G、100GiB")
    amount, unit = match.groups()
    unit = (unit or "B").upper()
    scale = {"B": 0, "K": 1, "KB": 1, "KIB": 1,
             "M": 2, "MB": 2, "MIB": 2, "G": 3, "GB": 3, "GIB": 3,
             "T": 4, "TB": 4, "TIB": 4}
    try:
        size = int(Decimal(amount) * (1024 ** scale[unit]))
    except (InvalidOperation, KeyError) as error:
        raise argparse.ArgumentTypeError("分卷大小无效") from error
    if size < 1:
        raise argparse.ArgumentTypeError("分卷大小必须至少为 1 字节")
    return size


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


class Progress:
    def __init__(self, total, current):
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
        if not force and now - self.last_print < (0.15 if self.tty else 5):
            return
        self.last_print = now
        fraction = min(0.999, self.done / self.total) if self.total else 0
        if force and self.done >= self.total:
            fraction = 1
        width = max(10, min(28, shutil.get_terminal_size((100, 20)).columns // 4))
        filled = round(width * fraction)
        eta = "--:--"
        if fraction == 1:
            eta = "00:00"
        elif len(self.samples) > 1:
            elapsed = self.samples[-1][0] - self.samples[0][0]
            speed = (self.samples[-1][1] - self.samples[0][1]) / elapsed if elapsed else 0
            if speed > 0:
                remaining = max(0, int((self.total - self.done) / speed))
                eta = f"{remaining // 3600:d}:{remaining // 60 % 60:02d}:{remaining % 60:02d}"
        prefix = f"[{'#' * filled}{'-' * (width - filled)}] {fraction:6.1%} ETA {eta}  "
        columns = shutil.get_terminal_size((100, 20)).columns
        line = prefix + fit_tail(self.current, max(8, columns - len(prefix) - 1))
        if self.tty:
            sys.stderr.write("\r\x1b[2K" + line)
        elif line != self.last_line:
            sys.stderr.write(line + "\n")
        self.last_line = line
        sys.stderr.flush()

    def finish(self):
        self.done = self.total
        self.render(force=True)
        if self.tty:
            sys.stderr.write("\n")
            sys.stderr.flush()


def entries(sources):
    stack = list(reversed(sources))
    while stack:
        path = stack.pop()
        info = path.lstat()
        yield path, info
        if stat.S_ISDIR(info.st_mode):
            with os.scandir(path) as listing:
                children = sorted((Path(item.path) for item in listing),
                                  key=lambda item: item.name, reverse=True)
            stack.extend(children)


def estimate(sources, fmt):
    total = 1024 if fmt.startswith("tar") else 0
    for path, info in entries(sources):
        if fmt == "zip" and stat.S_ISLNK(info.st_mode):
            raise ArkError(f"ZIP 不支持符号链接：{path}")
        if fmt.startswith("tar"):
            total += 512
            if stat.S_ISREG(info.st_mode):
                total += (info.st_size + 511) // 512 * 512
        elif stat.S_ISREG(info.st_mode):
            total += info.st_size
    return max(1, total)


def format_for(output, requested):
    if requested:
        return requested
    if output:
        name = output.name.lower()
        for fmt in sorted(FORMATS, key=len, reverse=True):
            if name.endswith("." + fmt):
                return fmt
    return "tar.gz"


class VolumeWriter:
    def __init__(self, directory, name, volume):
        self.directory = directory
        self.name = name
        self.volume = volume
        self.current = None
        self.current_size = 0
        self.index = 0
        self.paths = []

    def _open_next(self):
        if self.index > 9999:
            raise ArkError("分卷超过 10000 个；请增大 -v")
        name = f"{self.name}.part{self.index:04d}" if self.volume else self.name
        path = self.directory / name
        self.current = path.open("xb")
        self.paths.append(path)
        self.current_size = 0
        self.index += 1

    def write(self, data):
        view = memoryview(data)
        original = len(view)
        while view:
            if self.current is None:
                self._open_next()
            room = self.volume - self.current_size if self.volume else len(view)
            if room == 0:
                self.current.close()
                self.current = None
                continue
            chunk = view[:room]
            written = self.current.write(chunk)
            self.current_size += written
            view = view[written:]
        return original

    def flush(self):
        if self.current:
            self.current.flush()

    def close(self):
        if self.current:
            self.current.close()
            self.current = None


def compressor_args(fmt):
    codec = fmt.split(".")[-1]
    if codec not in CODECS:
        return None
    command = CODECS[codec]
    if not shutil.which(command[0]):
        raise ArkError(f"缺少压缩工具：{command[0]}")
    return command


def compress_chunks(chunks, command, writer, progress):
    if command is None:
        for chunk in chunks:
            writer.write(chunk)
            progress.advance(len(chunk))
        return

    errors = deque(maxlen=8)
    write_error = []
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

    def drain_output():
        try:
            while chunk := proc.stdout.read(CHUNK):
                writer.write(chunk)
        except BaseException as error:
            write_error.append(error)
            proc.terminate()

    def drain_errors():
        for line in proc.stderr:
            errors.append(line.decode("utf-8", "replace").rstrip())

    threads = [threading.Thread(target=drain_output, daemon=True),
               threading.Thread(target=drain_errors, daemon=True)]
    for thread in threads:
        thread.start()
    try:
        for chunk in chunks:
            proc.stdin.write(chunk)
            progress.advance(len(chunk))
        proc.stdin.close()
        code = proc.wait()
    except BaseException:
        proc.terminate()
        proc.wait()
        raise
    finally:
        for thread in threads:
            thread.join()
    if write_error:
        raise write_error[0]
    if code:
        raise ArkError("压缩失败：" + ("\n".join(errors) or f"退出码 {code}"))


def stream_chunks(stream):
    while chunk := stream.read(CHUNK):
        yield chunk


def compress_tar(sources, base, fmt, writer, progress):
    names = [str(path.relative_to(base)) for path in sources]
    command = ["tar", "-cvf", "-", "-C", str(base),
               "--quoting-style=escape", "--", *names]
    tar = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    errors = deque(maxlen=12)

    def read_names():
        for raw in tar.stderr:
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if line.startswith("tar: "):
                errors.append(line)
            elif line:
                progress.current = line

    reader = threading.Thread(target=read_names, daemon=True)
    reader.start()
    try:
        compress_chunks(stream_chunks(tar.stdout), compressor_args(fmt), writer, progress)
        code = tar.wait()
    except BaseException:
        tar.terminate()
        tar.wait()
        raise
    finally:
        reader.join()
    if code:
        raise ArkError("读取源文件失败：" + ("\n".join(errors) or f"tar 退出码 {code}"))


def compress_single(source, fmt, writer, progress):
    with source.open("rb") as file:
        compress_chunks(stream_chunks(file), compressor_args(fmt), writer, progress)


def compress_zip(sources, base, writer, progress):
    with zipfile.ZipFile(writer, "w", allowZip64=True) as archive:
        for path, info in entries(sources):
            name = path.relative_to(base).as_posix()
            if stat.S_ISDIR(info.st_mode):
                name += "/"
            progress.current = name
            year = min(2107, max(1980, time.localtime(info.st_mtime).tm_year))
            date = time.localtime(info.st_mtime)
            entry = zipfile.ZipInfo(name, (year, date.tm_mon, date.tm_mday,
                                           date.tm_hour, date.tm_min, date.tm_sec))
            entry.create_system = 3
            entry.external_attr = (info.st_mode & 0xFFFF) << 16
            if stat.S_ISDIR(info.st_mode):
                entry.external_attr |= 0x10
                archive.writestr(entry, b"")
            elif stat.S_ISREG(info.st_mode):
                entry.compress_type = zipfile.ZIP_DEFLATED
                with path.open("rb") as source, archive.open(entry, "w", force_zip64=True) as target:
                    for chunk in stream_chunks(source):
                        target.write(chunk)
                        progress.advance(len(chunk))
            else:
                raise ArkError(f"ZIP 不支持此文件类型：{path}")


def main():
    parser = argparse.ArgumentParser(description="创建归档，可选格式和分卷大小")
    parser.add_argument("sources", nargs="+", type=Path, help="要压缩的文件或目录")
    parser.add_argument("-o", "--output", type=Path, help="输出文件名；可从后缀推断格式")
    parser.add_argument("-f", "--format", choices=FORMATS, help="压缩格式（默认 tar.gz）")
    parser.add_argument("-v", "--volume", type=parse_size, metavar="SIZE",
                        help="分卷大小，如 100G；输出 .part0000、.part0001 等")
    args = parser.parse_args()

    sources = [Path(os.path.abspath(path.expanduser())) for path in args.sources]
    for source in sources:
        if not source.exists() and not source.is_symlink():
            raise ArkError(f"源路径不存在：{source}")
    requested_output = args.output.expanduser() if args.output else None
    fmt = format_for(requested_output, args.format)
    if fmt in SINGLE_FILE_FORMATS and (len(sources) != 1 or not sources[0].is_file()):
        raise ArkError(f"{fmt} 只接受单个普通文件；目录请使用 tar.{fmt}")
    if fmt == "zip" and len(sources) > 1 and len(set(sources)) != len(sources):
        raise ArkError("ZIP 输入路径重复")

    default_name = sources[0].name if len(sources) == 1 else "archive"
    if not default_name:
        default_name = "archive"
    output = (requested_output or Path(f"{default_name}.{fmt}")).absolute()
    if re.search(r"\.part\d{4,}$", output.name):
        raise ArkError("-o 请填写基础归档名，不要附加 .part0000")
    output = output.parent.resolve() / output.name
    if output.exists() or output.is_symlink() or list(output.parent.glob(output.name + ".part[0-9]*")):
        raise ArkError(f"输出文件或分卷已存在：{output}")
    for source in sources:
        if output == source.resolve():
            raise ArkError("输出文件不能与源文件相同")
        if stat.S_ISDIR(source.lstat().st_mode) and output.parent.is_relative_to(source.resolve()):
            raise ArkError(f"输出目录不能位于被压缩的目录内：{source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    base = Path(os.path.commonpath([str(source.parent) for source in sources]))
    total = sources[0].stat().st_size if fmt in SINGLE_FILE_FORMATS else estimate(sources, fmt)
    progress = Progress(total, sources[0].name)
    stage = Path(tempfile.mkdtemp(prefix=".ark-", dir=output.parent))
    writer = VolumeWriter(stage, output.name, args.volume)
    try:
        if progress.tty:
            progress.render(force=True)
        if fmt == "zip":
            compress_zip(sources, base, writer, progress)
        elif fmt in SINGLE_FILE_FORMATS:
            compress_single(sources[0], fmt, writer, progress)
        else:
            compress_tar(sources, base, fmt, writer, progress)
        writer.close()
        if not writer.paths:
            raise ArkError("压缩器没有产生输出")
        for path in writer.paths:
            target = output.parent / path.name
            if target.exists() or target.is_symlink():
                raise ArkError(f"输出文件或分卷已存在：{target}")
        published = []
        try:
            for path in writer.paths:
                target = output.parent / path.name
                path.rename(target)
                published.append(target)
        except OSError:
            for target in published:
                target.unlink()
            raise
        stage.rmdir()
        progress.finish()
    except BaseException:
        writer.close()
        if progress.tty:
            sys.stderr.write("\n")
        shutil.rmtree(stage, ignore_errors=True)
        raise


def cli():
    try:
        main()
    except (ArkError, OSError, RuntimeError, ValueError, zipfile.BadZipFile) as error:
        sys.stderr.write(f"ark: {error}\n")
        sys.exit(1)


if __name__ == "__main__":
    cli()
