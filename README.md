# ark / uark

[中文](#中文) | [English](#english)

Two small Linux and macOS commands for working with archives. `ark` creates archives;
`uark` detects the archive format and extracts it. Both show a progress bar,
the current file and an estimated time remaining.

## 中文

### 功能

- `ark`：压缩文件或目录，可选择格式和分卷大小。
- `uark`：根据文件内容识别格式并解压，无须记住 `tar` 的参数。
- 两个命令都在终端显示进度条、当前文件和预计剩余时间。重定向输出时会降低刷新频率。

### 环境要求

支持 Linux 和 macOS（Apple Silicon / Intel）、Python 3.10 及以上版本。处理 tar 归档支持 Linux 的 GNU tar 和 macOS 自带的 BSD tar，无须在 macOS 上额外安装 GNU tar。使用相应压缩格式时，还需要系统安装 `gzip`、`bzip2`、`xz` 或 `zstd`。ZIP 由 Python 标准库处理，不需要额外的 Python 依赖。GNU tar 解压时可使用可选的 `stdbuf` / `gstdbuf` 改善文件名的刷新速度。

例如在 Debian / Ubuntu 上安装完整的系统依赖：

```bash
sudo apt update
sudo apt install python3 python3-venv tar gzip bzip2 xz-utils zstd
```

macOS 自带 `tar`、`gzip` 和 `bzip2`。通过 Homebrew 安装 Python 和其余压缩工具：

```bash
brew install python xz zstd
```

只使用 `tar`、`tar.gz`、`tar.bz2` 或 ZIP 时，无须安装 `xz` / `zstd`。macOS 创建 tar 归档时不会附带 AppleDouble `._*` 元数据文件或扩展属性，方便与 Linux 交换文件。

### 从 GitHub 源码安装

从 GitHub 克隆项目：

```bash
git clone https://github.com/CuiEM/ark-uark.git
cd ark-uark
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
ark --help
uark --help
```

激活虚拟环境后即可使用两个命令。以后进入项目目录，运行 `. .venv/bin/activate` 即可再次使用。若已安装 `pipx`，也可以直接安装到用户命令目录：

```bash
pipx install git+https://github.com/CuiEM/ark-uark.git
```

### 卸载

如果通过 `pipx` 安装：

```bash
pipx uninstall ark-uark
```

如果通过 `uv tool install` 安装，运行 `uv tool uninstall ark-uark`。如果按上面的步骤安装在项目虚拟环境中，先进入项目目录并激活环境，再运行：

```bash
. .venv/bin/activate
python3 -m pip uninstall ark-uark
```

卸载命令不会删除克隆的源码目录。

### 常用命令

```bash
# 默认格式为 tar.gz，输出到当前目录
ark photos

# 指定格式和输出文件；也可以只用 -o 后缀推断格式
ark photos -f tar.zst -o photos.tar.zst
ark photos -o photos.zip

# 每卷最多 2 GiB；输出 photos.tar.zst.part0000、part0001 等
ark photos -f tar.zst -v 2G -o photos.tar.zst

# 指定任意一卷，uark 会寻找同一目录下的其他分卷；默认解压到压缩包所在目录
uark photos.tar.zst.part0000

# 也可指定解压目录
uark photos.zip -C restored

# 多个源文件可以合并为一个归档
ark a.txt b.txt -o files.zip
```

### 格式与分卷

| 格式 | `ark -f` | 输入 |
| --- | --- | --- |
| Tar 及压缩 Tar | `tar`、`tar.gz`、`tar.bz2`、`tar.xz`、`tar.zst` | 文件、目录或多个路径 |
| ZIP | `zip` | 文件、目录或多个路径；不支持符号链接 |
| 单文件压缩 | `gz`、`bz2`、`xz`、`zst` | 单个普通文件 |

目前不支持 7z 和 RAR。`uark` 会识别并提示这两类文件，但不会解压。

`-v` 接受字节数或 `K`、`M`、`G`、`T`、`KiB`、`MiB`、`GiB`、`TiB`，均按 1024 进制计算。例如 `-v 1.5G`。不指定 `-v` 时只生成一个文件。已有同名输出或分卷时，`ark` 会报错，不会覆盖它们。

`uark` 默认把内容解压到压缩包所在目录，不额外建立同名文件夹。若归档内的顶层路径已存在，默认解压会报错，避免覆盖原有内容；可用 `-C` 选择其他位置。

分卷是把**完整压缩流按字节切开**，不是传统 ZIP 的 `.z01` 多卷格式。`uark` 会自动拼接；其他工具使用前，可按顺序合并：

```bash
cat photos.tar.zst.part* > photos.tar.zst
```

所有分卷必须放在同一目录，编号从 `part0000` 开始且不能缺失。预计时间按已处理字节计算，压缩率或磁盘速度变化时会波动。解压来源不可信的归档前，请先检查其内容；`uark` 不是隔离沙箱。

### 开发与测试

```bash
python3 -m unittest discover -s tests -v
```

### 构建安装包

在虚拟环境中构建 wheel 和源码包：

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install build
python3 -m build
```

产物位于 `dist/`。wheel 为纯 Python 包，可用于 macOS 的 Apple Silicon 和 Intel Mac，以及 Linux；运行时仍需上述 Python 和系统工具。在目标机器的虚拟环境中安装：

```bash
python3 -m pip install dist/ark_uark-*.whl
ark --help
uark --help
```

项目采用 MIT License。

## English

### What it does

- `ark` creates archives with a selected format and optional volume size.
- `uark` identifies an archive from its contents and extracts it.
- Both commands show a progress bar, current file and ETA. Output is less frequent when redirected.

### Requirements

Linux or macOS (Apple Silicon / Intel), with Python 3.10 or newer. Tar archives support GNU tar on Linux and the built-in BSD tar on macOS; installing GNU tar on macOS is unnecessary. Install `gzip`, `bzip2`, `xz` or `zstd` for the corresponding compression formats. ZIP uses Python's standard library; there are no third-party Python runtime dependencies. Optional `stdbuf` / `gstdbuf` helps update file names promptly when extracting with GNU tar.

On Debian / Ubuntu, install the full set of system tools with:

```bash
sudo apt update
sudo apt install python3 python3-venv tar gzip bzip2 xz-utils zstd
```

macOS includes `tar`, `gzip` and `bzip2`. Install Python and the remaining compression tools with Homebrew:

```bash
brew install python xz zstd
```

`xz` / `zstd` is unnecessary if you only use `tar`, `tar.gz`, `tar.bz2` or ZIP. Tar archives created on macOS omit AppleDouble `._*` metadata entries and extended attributes for portability to Linux.

### Install from GitHub source

Clone the project from GitHub:

```bash
git clone https://github.com/CuiEM/ark-uark.git
cd ark-uark
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
ark --help
uark --help
```

The commands are available while the virtual environment is active. Run `. .venv/bin/activate` when you return to the project later. If `pipx` is installed, you can instead install the commands into your user command directory:

```bash
pipx install git+https://github.com/CuiEM/ark-uark.git
```

### Uninstall

If you installed with `pipx`:

```bash
pipx uninstall ark-uark
```

If you used `uv tool install`, run `uv tool uninstall ark-uark`. For an installation in the project virtual environment, enter the project directory, activate the environment, then run:

```bash
. .venv/bin/activate
python3 -m pip uninstall ark-uark
```

Uninstalling does not remove the cloned source directory.

### Usage

```bash
# tar.gz by default; write to the current directory
ark photos

# Select a format explicitly, or infer it from the output suffix
ark photos -f tar.zst -o photos.tar.zst
ark photos -o photos.zip

# Limit each volume to 2 GiB
ark photos -f tar.zst -v 2G -o photos.tar.zst

# Point uark at any volume; it finds the others beside it and extracts alongside them
uark photos.tar.zst.part0000

# Or choose a destination directory
uark photos.zip -C restored

# Put multiple inputs into one archive
ark a.txt b.txt -o files.zip
```

### Formats and volumes

| Format | `ark -f` | Input |
| --- | --- | --- |
| Tar and compressed Tar | `tar`, `tar.gz`, `tar.bz2`, `tar.xz`, `tar.zst` | Files, directories or multiple paths |
| ZIP | `zip` | Files, directories or multiple paths; symbolic links are unsupported |
| Single-file compression | `gz`, `bz2`, `xz`, `zst` | One regular file |

7z and RAR are not supported yet. `uark` recognizes them and reports that it cannot extract them.

`-v` accepts bytes or `K`, `M`, `G`, `T`, `KiB`, `MiB`, `GiB`, `TiB`. Units use powers of 1024, so `-v 1.5G` is valid. Without `-v`, `ark` writes one file. Existing archives and volumes are never overwritten.

By default, `uark` extracts beside the archive without adding a wrapper directory. It reports an error if an archived top-level path already exists there, preventing an overwrite. Use `-C` to choose another destination.

Volumes are **consecutive slices of one compressed byte stream**, not conventional ZIP `.z01` volumes. `uark` reads them directly. To use another tool, join the volumes in order first:

```bash
cat photos.tar.zst.part* > photos.tar.zst
```

Keep every volume in the same directory, starting at `part0000` with no gaps. The ETA is based on bytes processed and may change with compression ratio or disk speed. Inspect untrusted archives before extracting them; `uark` is not a sandbox.

### Development and tests

```bash
python3 -m unittest discover -s tests -v
```

### Build distribution packages

Build a wheel and source distribution in a virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install build
python3 -m build
```

Artifacts are written to `dist/`. The pure Python wheel works on Apple Silicon and Intel Macs, as well as Linux, and still requires the Python version and system tools listed above. Install it in a virtual environment on the target machine:

```bash
python3 -m pip install dist/ark_uark-*.whl
ark --help
uark --help
```

Licensed under the MIT License.
