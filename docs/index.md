# tonie-podcast-sync

[![All Contributors](https://img.shields.io/badge/all_contributors-6-orange.svg?style=flat-square)](contributing.md)
[![PyPI](https://img.shields.io/pypi/v/tonie-podcast-sync)](https://pypi.org/project/tonie-podcast-sync)

**tonie-podcast-sync** allows syncing podcast episodes to [creative tonies](https://tonies.com).

!!! warning "Disclaimer"
    This is a purely private project and has no association with Boxine GmbH.

[![Demo GIF](https://raw.githubusercontent.com/alexhartm/tonie-podcast-sync/main/ressources/tps.gif)](https://asciinema.org/a/644812 "Demo of tonie-podcast-sync")

## Key Features

- 📻 **Podcast Syncing** - Automatically sync podcast episodes to your creative tonies
- 🎵 **Local MP3 Syncing** - Upload local audio folders or explicit MP3 file lists to a tonie
- ⚙️ **Flexible Configuration** - Configure source type, sorting, duration limits, wipe mode, and volume adjustments
- 🎯 **Smart Filtering** - Filter episodes or local files by duration, title keywords, pinning, or custom criteria
- 🖥️ **Multiple Interfaces** - Use via CLI, Python library, or Docker container
- 📦 **Easy Setup** - Simple installation via pip with minimal configuration

## How It Works

1. Configure your tonie credentials and a source for each creative Tonie (`podcast`, `audio_folder`, or `audio_files`)
2. Map those sources to specific creative tonies
3. Run the sync command to fetch podcast episodes or upload local MP3 files
4. Press the tonie's ear for 3 seconds to trigger the sync on your TonieBox

## Quick Links

- [Installation Guide](installation.md) - Get started in minutes
- [CLI Usage](usage/cli.md) - Command-line interface guide
- [Python Library](usage/library.md) - Use in your own scripts
- [Configuration](configuration/settings.md) - Detailed configuration options

## Support the Project

If you find this project useful, please consider:

- ⭐ Starring the [GitHub repository](https://github.com/alexhartm/tonie-podcast-sync)
- 🐛 [Reporting bugs](https://github.com/alexhartm/tonie-podcast-sync/issues)
- 💡 [Suggesting features](https://github.com/alexhartm/tonie-podcast-sync/issues)
- 🤝 [Contributing](contributing.md) to the project
