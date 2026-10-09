# ark / uark

> Create archives with confidence. Extract them without remembering tar flags.

[![Tests](https://github.com/CuiEM/ark-uark/actions/workflows/tests.yml/badge.svg)](https://github.com/CuiEM/ark-uark/actions/workflows/tests.yml)
[![Homebrew](https://github.com/CuiEM/ark-uark/actions/workflows/homebrew.yml/badge.svg)](https://github.com/CuiEM/ark-uark/actions/workflows/homebrew.yml)
[![Latest release](https://img.shields.io/github/v/release/CuiEM/ark-uark?display_name=tag&sort=semver)](https://github.com/CuiEM/ark-uark/releases/latest)
[![License](https://img.shields.io/github/license/CuiEM/ark-uark)](LICENSE)

`ark` and `uark` are lightweight command-line archive tools:

- `ark` creates tar, compressed tar, ZIP and single-file compression archives.
- `uark` detects the format from the file contents and extracts it for you.
- Both commands show progress, the current file and an estimated time remaining.
- Any compressed stream can be split into volumes and restored from any volume.

Supported platforms are Linux and macOS on both Apple Silicon and Intel. The runtime uses Python's standard library plus the system compressor required by the selected format.

[简体中文文档](README.zh-CN.md)

## Installation

### macOS

Homebrew is the recommended installation method. It installs Python, `xz` and `zstd` automatically; macOS already provides `tar`, `gzip` and `bzip2`.

```bash
brew tap CuiEM/ark-uark https://github.com/CuiEM/ark-uark.git
brew install CuiEM/ark-uark/ark-uark
```

For a source or `pipx` installation, install the optional compressors first:

```bash
brew install python xz zstd
pipx install git+https://github.com/CuiEM/ark-uark.git
```

### Linux

On Debian or Ubuntu, install the runtime and archive tools first:

```bash
sudo apt update
sudo apt install -y python3 python3-venv tar gzip bzip2 xz-utils zstd
```

Then install with `pipx`:

```bash
pipx install git+https://github.com/CuiEM/ark-uark.git
```

Or install into a project virtual environment:

```bash
git clone https://github.com/CuiEM/ark-uark.git
cd ark-uark
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install .
```

Other Linux distributions need equivalent packages. ZIP only uses Python's standard library; the other formats need `tar` and the matching compressor.

Verify either installation with:

```bash
ark --help
uark --help
```

## Quick start

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

## Supported formats

| Category | `ark -f` | Input | Notes |
| --- | --- | --- | --- |
| Tar | `tar` | Files, directories or multiple paths | Uses the system `tar` |
| Compressed tar | `tar.gz`, `tar.bz2`, `tar.xz`, `tar.zst` | Files, directories or multiple paths | Best for directory archives |
| ZIP | `zip` | Files, directories or multiple paths | Symbolic links are unsupported |
| Single-file compression | `gz`, `bz2`, `xz`, `zst` | One regular file | Directories are rejected |

7z and RAR are recognized and reported, but are not extracted.

## Volumes and safety

Volumes are consecutive byte slices of one compressed stream, named like `archive.tar.zst.part0000`. They are not conventional ZIP `.z01` volumes. Keep every volume together, starting at `part0000` with no gaps.

Without `-v`, `ark` writes one archive. Existing archives and volumes are never overwritten. By default, `uark` extracts beside the archive and stops if an archived top-level path already exists; use `-C` to choose an empty destination.

To use another tool, join the volumes first:

```bash
cat photos.tar.zst.part* > photos.tar.zst
```

Inspect untrusted archives before extracting them; `uark` is not a sandbox.

## Uninstall

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
