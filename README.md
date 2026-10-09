# ark / uark

> 用一个命令创建归档，用另一个命令自动识别并解压。
>
> Create archives with confidence. Extract them without remembering tar flags.

[![Tests](https://github.com/CuiEM/ark-uark/actions/workflows/tests.yml/badge.svg)](https://github.com/CuiEM/ark-uark/actions/workflows/tests.yml)
[![Homebrew](https://github.com/CuiEM/ark-uark/actions/workflows/homebrew.yml/badge.svg)](https://github.com/CuiEM/ark-uark/actions/workflows/homebrew.yml)
[![Latest release](https://img.shields.io/github/v/release/CuiEM/ark-uark?display_name=tag&sort=semver)](https://github.com/CuiEM/ark-uark/releases/latest)
[![License](https://img.shields.io/github/license/CuiEM/ark-uark)](LICENSE)

`ark` 和 `uark` 是一对轻量的命令行归档工具：

- `ark` 创建 tar、压缩 tar、ZIP 或单文件压缩归档。
- `uark` 根据文件内容自动识别格式并解压，不需要记住压缩参数。
- 两个命令都显示进度、当前文件和预计剩余时间。
- 支持把完整压缩流切成分卷，也支持从任意分卷开始恢复。

支持 Linux、macOS Apple Silicon 和 Intel，运行时只依赖 Python 标准库及对应的系统压缩工具。

## 中文

### 安装

macOS 用户推荐使用 Homebrew：

```bash
brew tap CuiEM/ark-uark https://github.com/CuiEM/ark-uark.git
brew install CuiEM/ark-uark/ark-uark
```

Homebrew 会自动安装 Python、`xz` 和 `zstd`。安装完成后，两个命令立即可用：

```bash
ark --help
uark --help
```

也可以通过 `pipx` 安装：

```bash
pipx install git+https://github.com/CuiEM/ark-uark.git
```

从源码安装：

```bash
git clone https://github.com/CuiEM/ark-uark.git
cd ark-uark
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
```

Python 安装只负责提供命令。使用 `tar.gz`、`tar.bz2`、`tar.xz` 或 `tar.zst` 时，还需要系统中有对应的 `tar` 和压缩工具；ZIP 使用 Python 标准库，不需要额外依赖。

### 30 秒上手

```bash
# 默认创建 tar.gz
ark photos

# 从输出文件名推断格式
ark photos -o photos.zip

# 显式选择格式
ark photos -f tar.zst -o photos.tar.zst

# 将压缩流切成每卷最多 2 GiB 的分卷
ark photos -f tar.zst -v 2G -o photos.tar.zst

# 指定任意一卷即可自动找到同目录下的其他分卷
uark photos.tar.zst.part0000

# 指定解压目录
uark photos.zip -C restored

# 合并多个文件或目录
ark a.txt b.txt -o files.zip
```

### 支持的格式

| 类别 | `ark -f` | 输入 | 说明 |
| --- | --- | --- | --- |
| Tar | `tar` | 文件、目录或多个路径 | 使用系统 `tar` |
| 压缩 Tar | `tar.gz`、`tar.bz2`、`tar.xz`、`tar.zst` | 文件、目录或多个路径 | 适合目录归档 |
| ZIP | `zip` | 文件、目录或多个路径 | 不支持符号链接 |
| 单文件压缩 | `gz`、`bz2`、`xz`、`zst` | 一个普通文件 | 不接受目录 |

7z 和 RAR 目前只会被识别并给出提示，不会被解压。

### 分卷与安全行为

分卷是完整压缩流按字节切分，文件名形如 `archive.tar.zst.part0000`，不是传统 ZIP 的 `.z01` 结构。所有分卷必须放在同一目录，编号从 `part0000` 开始且不能缺失。

不指定 `-v` 时只生成一个归档。已有同名归档或分卷时，`ark` 会报错并保留原文件。`uark` 默认解压到归档所在目录；如果归档的顶层路径已存在，会停止解压以避免覆盖，可用 `-C` 指定空目录。

要交给其他工具处理分卷，先按顺序合并：

```bash
cat photos.tar.zst.part* > photos.tar.zst
```

解压不可信来源前，请先检查归档内容；`uark` 不提供沙箱隔离。

### 卸载

Homebrew：

```bash
brew uninstall ark-uark
brew untap CuiEM/ark-uark
```

pipx：

```bash
pipx uninstall ark-uark
```

虚拟环境：

```bash
. .venv/bin/activate
python3 -m pip uninstall ark-uark
```

## English

### Install

On macOS, Homebrew is the recommended option:

```bash
brew tap CuiEM/ark-uark https://github.com/CuiEM/ark-uark.git
brew install CuiEM/ark-uark/ark-uark
```

Homebrew installs Python, `xz` and `zstd` automatically. Verify the installation with:

```bash
ark --help
uark --help
```

Install with `pipx`:

```bash
pipx install git+https://github.com/CuiEM/ark-uark.git
```

Or install from source:

```bash
git clone https://github.com/CuiEM/ark-uark.git
cd ark-uark
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
```

The Python package provides the commands but does not bundle system compressors. Tar archives require `tar` and the matching compressor; ZIP uses Python's standard library.

### Quick start

```bash
# Create tar.gz by default
ark photos

# Infer the format from the output suffix
ark photos -o photos.zip

# Choose a format explicitly
ark photos -f tar.zst -o photos.tar.zst

# Split the compressed stream into 2 GiB volumes
ark photos -f tar.zst -v 2G -o photos.tar.zst

# Point uark at any volume; it finds the rest beside it
uark photos.tar.zst.part0000

# Extract into a chosen directory
uark photos.zip -C restored

# Combine multiple files or directories
ark a.txt b.txt -o files.zip
```

### Supported formats

| Category | `ark -f` | Input | Notes |
| --- | --- | --- | --- |
| Tar | `tar` | Files, directories or multiple paths | Uses the system `tar` |
| Compressed tar | `tar.gz`, `tar.bz2`, `tar.xz`, `tar.zst` | Files, directories or multiple paths | Best for directory archives |
| ZIP | `zip` | Files, directories or multiple paths | Symbolic links are unsupported |
| Single-file compression | `gz`, `bz2`, `xz`, `zst` | One regular file | Directories are rejected |

7z and RAR are recognized and reported, but are not extracted.

### Volumes and safety

Volumes are consecutive byte slices of one compressed stream, named like `archive.tar.zst.part0000`. They are not conventional ZIP `.z01` volumes. Keep every volume together, starting at `part0000` with no gaps.

Without `-v`, `ark` writes one archive. Existing archives and volumes are never overwritten. By default, `uark` extracts beside the archive and stops if an archived top-level path already exists; use `-C` to choose an empty destination.

To use another tool, join the volumes first:

```bash
cat photos.tar.zst.part* > photos.tar.zst
```

Inspect untrusted archives before extracting them; `uark` is not a sandbox.

### Uninstall

Homebrew:

```bash
brew uninstall ark-uark
brew untap CuiEM/ark-uark
```

pipx:

```bash
pipx uninstall ark-uark
```

Virtual environment:

```bash
. .venv/bin/activate
python3 -m pip uninstall ark-uark
```

## Development

Run the test suite locally:

```bash
python3 -m unittest discover -s tests -v
```

Build the wheel and source distribution:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install build
python3 -m build
```

Release and Homebrew maintenance instructions are in [RELEASING.md](RELEASING.md). The Homebrew formula lives at [Formula/ark-uark.rb](Formula/ark-uark.rb).

## License

[MIT](LICENSE)
