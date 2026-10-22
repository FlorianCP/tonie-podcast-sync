# Installation

## Prerequisites

Before installing tonie-podcast-sync, ensure you have:

- **Python** >= 3.10; use a security-patched runtime, with pip >= 26.2.2 when installing via pip
- **ffmpeg** (optional, required only if using the `volume_adjustment` feature)

### Installing ffmpeg

=== "macOS"
    ```bash
    brew install ffmpeg
    ```

=== "Ubuntu/Debian"
    ```bash
    sudo apt update
    sudo apt install ffmpeg
    ```

=== "Windows"
    Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

## Install via pip

The easiest way to install tonie-podcast-sync is via pip:

```bash
pip install tonie-podcast-sync
```

Use pip >= 26.2.2 and certifi >= 2026.10.19 for the eMudhra trust-store update.
Update existing Python installations as well as application dependencies; upgrading this package
does not replace the runtime's bundled pip or certificate stores.
Even patched Python releases can bundle an older ensurepip seed. For development, use the
repository's pinned uv to create and sync environments rather than bootstrapping pip with ensurepip.

This will install the package and make the `tonie-podcast-sync` command available in your terminal.

## Verify Installation

To verify the installation was successful:

```bash
tonie-podcast-sync --help
```

You should see the help output with available commands.

## Update to Latest Version

To update to the latest version:

```bash
pip install --upgrade tonie-podcast-sync
```

## Next Steps

Once installed, proceed to the [Quick Start Guide](quickstart.md) to set up your configuration.
