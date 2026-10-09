# ark / uark

> 用一个命令创建归档，用另一个命令自动识别并解压。

[![测试](https://github.com/CuiEM/ark-uark/actions/workflows/tests.yml/badge.svg)](https://github.com/CuiEM/ark-uark/actions/workflows/tests.yml)
[![Homebrew](https://github.com/CuiEM/ark-uark/actions/workflows/homebrew.yml/badge.svg)](https://github.com/CuiEM/ark-uark/actions/workflows/homebrew.yml)
[![最新版本](https://img.shields.io/github/v/release/CuiEM/ark-uark?display_name=tag&sort=semver)](https://github.com/CuiEM/ark-uark/releases/latest)
[![许可证](https://img.shields.io/github/license/CuiEM/ark-uark)](LICENSE)

`ark` 和 `uark` 是一对轻量的命令行归档工具：

- `ark` 创建 tar、压缩 tar、ZIP 或单文件压缩归档。
- `uark` 根据文件内容自动识别格式并解压，不需要记住压缩参数。
- 两个命令都显示进度、当前文件和预计剩余时间。
- 支持把完整压缩流切成分卷，也支持从任意分卷开始恢复。

支持 Linux、macOS Apple Silicon 和 Intel，运行时只依赖 Python 标准库及对应的系统压缩工具。

[English documentation](README.md)

## 安装

### macOS

推荐使用 Homebrew。Homebrew 会自动安装 Python、`xz` 和 `zstd`；macOS 已自带 `tar`、`gzip` 和 `bzip2`。

```bash
brew tap CuiEM/ark-uark https://github.com/CuiEM/ark-uark.git
brew install CuiEM/ark-uark/ark-uark
```

如果使用源码或 `pipx` 安装，先安装可选的压缩工具：

```bash
brew install python xz zstd
pipx install git+https://github.com/CuiEM/ark-uark.git
```

### Linux

Debian / Ubuntu 用户先安装运行时和归档工具：

```bash
sudo apt update
sudo apt install -y python3 python3-venv tar gzip bzip2 xz-utils zstd
```

然后使用 `pipx` 安装：

```bash
pipx install git+https://github.com/CuiEM/ark-uark.git
```

也可以安装到项目虚拟环境：

```bash
git clone https://github.com/CuiEM/ark-uark.git
cd ark-uark
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
```

其他 Linux 发行版请安装对应的软件包。ZIP 只使用 Python 标准库；其他格式需要 `tar` 和匹配的压缩工具。

安装后可以运行以下命令检查：

```bash
ark --help
uark --help
```

## 30 秒上手

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

## 支持的格式

| 类别 | `ark -f` | 输入 | 说明 |
| --- | --- | --- | --- |
| Tar | `tar` | 文件、目录或多个路径 | 使用系统 `tar` |
| 压缩 Tar | `tar.gz`、`tar.bz2`、`tar.xz`、`tar.zst` | 文件、目录或多个路径 | 适合目录归档 |
| ZIP | `zip` | 文件、目录或多个路径 | 不支持符号链接 |
| 单文件压缩 | `gz`、`bz2`、`xz`、`zst` | 一个普通文件 | 不接受目录 |

7z 和 RAR 目前只会被识别并给出提示，不会被解压。

## 分卷与安全行为

分卷是完整压缩流按字节切分，文件名形如 `archive.tar.zst.part0000`，不是传统 ZIP 的 `.z01` 结构。所有分卷必须放在同一目录，编号从 `part0000` 开始且不能缺失。

不指定 `-v` 时只生成一个归档。已有同名归档或分卷时，`ark` 会报错并保留原文件。`uark` 默认解压到归档所在目录；如果归档的顶层路径已存在，会停止解压以避免覆盖，可用 `-C` 指定空目录。

要交给其他工具处理分卷，先按顺序合并：

```bash
cat photos.tar.zst.part* > photos.tar.zst
```

解压不可信来源前，请先检查归档内容；`uark` 不提供沙箱隔离。

## 卸载

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

## 开发

运行测试：

```bash
python3 -m unittest discover -s tests -v
```

构建 wheel 和源码包：

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install build
python3 -m build
```

发布和 Homebrew 维护说明见 [RELEASING.md](RELEASING.md)，Homebrew 配方位于 [Formula/ark-uark.rb](Formula/ark-uark.rb)。

## 许可证

[MIT](LICENSE)
