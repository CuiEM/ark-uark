# Publishing a release

The project repository also serves as the Homebrew tap. GitHub releases provide
the Python packages; `Formula/ark-uark.rb` pins the source for Homebrew installs.

1. Update the version in `setup.cfg` and `src/ark_uark/__init__.py`, and update
   `RELEASE_NOTES.md` for the new release.
2. Run the tests and package build, commit the changes, and push `main`.
3. Create and push an annotated tag matching the package version, such as
   `v0.1.1`. The Release workflow verifies the version, runs tests, builds the
   wheel and source distribution, and publishes their GitHub Release assets.
4. Download the new tag's source archive and calculate its SHA-256:

   ```bash
   curl -fL https://github.com/CuiEM/ark-uark/archive/refs/tags/v0.1.1.tar.gz -o ark-uark-v0.1.1.tar.gz
   shasum -a 256 ark-uark-v0.1.1.tar.gz
   ```

5. Update the `url` and `sha256` in `Formula/ark-uark.rb`. Keep published tags
   unchanged so existing downloads remain valid.
6. Validate the formula from a local tap checkout:

   ```bash
   brew reinstall --build-from-source CuiEM/ark-uark/ark-uark
   brew test CuiEM/ark-uark/ark-uark
   brew audit --strict CuiEM/ark-uark/ark-uark
   ```

7. Commit and push the formula update. The Homebrew workflow checks installation,
   functional tests and auditing on Apple Silicon and Intel Macs.

Users receive the new version with `brew update` and `brew upgrade ark-uark`.
