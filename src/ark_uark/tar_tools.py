"""Identify the tar implementation selected by PATH."""

import shutil
import subprocess


def tar_program():
    program = shutil.which("tar")
    if program is None:
        raise RuntimeError("缺少归档工具：tar（支持 GNU tar 和 macOS BSD tar）")
    result = subprocess.run([program, "--version"], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, errors="replace",
                            check=False)
    if result.returncode == 0:
        if "bsdtar" in result.stdout.lower():
            return program, "bsd"
        if "GNU tar" in result.stdout:
            return program, "gnu"
    raise RuntimeError("不支持此 tar 实现；请使用 GNU tar 或 macOS BSD tar")
