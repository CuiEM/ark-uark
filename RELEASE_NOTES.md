First release of ark / uark for Linux and macOS.

- Create and extract tar, compressed tar, ZIP and single-file compression formats.
- Split archives into volumes and extract directly from any volume.
- Display progress, the current file and estimated time remaining.
- Use macOS's built-in BSD tar, with support for Apple Silicon and Intel Macs.

Install on macOS with Homebrew:

```bash
brew tap CuiEM/ark-uark https://github.com/CuiEM/ark-uark.git
brew install CuiEM/ark-uark/ark-uark
```

Homebrew installs Python and the required compression tools automatically.
The Python wheel and source distribution are also available below.
