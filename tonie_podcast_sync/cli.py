"""The command line interface module for the tonie-podcast-sync."""

import warnings
from pathlib import Path
from typing import Annotated

import tomli_w
from dynaconf.vendor.box.exceptions import BoxError
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from tonie_api.models import CreativeTonie
from typer import BadParameter, Option, Typer

from tonie_podcast_sync.config import APP_SETTINGS_DIR, settings
from tonie_podcast_sync.constants import MAXIMUM_TONIE_MINUTES
from tonie_podcast_sync.podcast import EpisodeSorting, Podcast
from tonie_podcast_sync.toniepodcastsync import ToniePodcastSync

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")

app = Typer(pretty_exceptions_show_locals=False)
_console = Console()


@app.command()
def update_tonies() -> None:
    """Update configured tonies from podcasts or local audio sources defined in settings.toml."""
    tps = _create_tonie_podcast_sync()
    if not tps:
        return

    for tonie_id, tonie_config in settings.CREATIVE_TONIES.items():
        _sync_tonie_from_config(tps, tonie_id, tonie_config)


@app.command()
def sync_local_files(  # noqa: PLR0913
    tonie_id: Annotated[str, Option("--tonie-id", help="ID of the creative Tonie to update.")],
    directory: Annotated[Path | None, Option("--directory", help="Folder containing .mp3 files to sync.")] = None,
    files: Annotated[
        list[Path] | None,
        Option("--files", help="One or more .mp3 files to sync. Repeat the option for multiple files."),
    ] = None,
    maximum_length: Annotated[
        int,
        Option(
            "--maximum-length",
            min=1,
            max=MAXIMUM_TONIE_MINUTES,
            help="Maximum combined playback time in minutes.",
        ),
    ] = MAXIMUM_TONIE_MINUTES,
    episode_sorting: Annotated[
        str | None,
        Option(
            "--episode-sorting",
            help="Local audio ordering: 'manual' keeps --files order, 'alphabetical' sorts by filename.",
        ),
    ] = None,
    volume_adjustment: Annotated[
        int,
        Option("--volume-adjustment", help="Volume adjustment in dB for local MP3 files."),
    ] = 0,
    episode_min_duration_sec: Annotated[
        int,
        Option(
            "--episode-min-duration-sec",
            min=0,
            help="Skip local files shorter than this many seconds.",
        ),
    ] = 0,
    episode_max_duration_sec: Annotated[
        int,
        Option(
            "--episode-max-duration-sec",
            min=1,
            help="Skip local files longer than this many seconds.",
        ),
    ] = MAXIMUM_TONIE_MINUTES * 60,
    wipe: Annotated[
        bool | None,
        Option("--wipe/--no-wipe", help="Clear the Tonie before uploading new local files."),
    ] = None,
    dry_run: Annotated[
        bool | None,
        Option("--dry-run", help="Preview which files would be uploaded without changing the Tonie."),
    ] = None,
) -> None:
    """Sync local MP3 files directly from the CLI."""
    tps = _create_tonie_podcast_sync()
    if not tps:
        return

    wipe = True if wipe is None else wipe
    dry_run = False if dry_run is None else dry_run

    if directory is not None and files:
        msg = "Provide either --directory or --files, not both."
        raise BadParameter(msg)
    if directory is None and not files:
        msg = "Provide either --directory or at least one --files value."
        raise BadParameter(msg)

    tps.sync_files_to_tonie(
        tonie_id=tonie_id,
        directory=directory,
        files=files,
        max_minutes=maximum_length,
        wipe=wipe,
        sort_order=episode_sorting,
        dry_run=dry_run,
        volume_adjustment=volume_adjustment,
        episode_min_duration_sec=episode_min_duration_sec,
        episode_max_duration_sec=episode_max_duration_sec,
    )


def _create_tonie_podcast_sync() -> ToniePodcastSync | None:
    """Create ToniePodcastSync instance from settings.

    Returns:
        ToniePodcastSync instance if successful, None otherwise
    """
    try:
        return ToniePodcastSync(settings.TONIE_CLOUD_ACCESS.USERNAME, settings.TONIE_CLOUD_ACCESS.PASSWORD)
    except BoxError:
        _console.print(
            "There was an error getting the username or password. Please create the settings file or set the "
            "environment variables TPS_TONIE_CLOUD_ACCESS_USERNAME and TPS_TONIE_CLOUD_ACCESS_PASSWORD.",
        )
        return None


def _sync_tonie_from_config(
    tps: ToniePodcastSync, tonie_id: str, tonie_config: object
) -> None:
    """Sync one configured Tonie from the settings file.

    Args:
        tps: Authenticated ToniePodcastSync instance used for the sync.
        tonie_id: Target creative Tonie ID from the settings file.
        tonie_config: Dynaconf-backed config section for the Tonie. Must define exactly one
            of `podcast`, `audio_folder`, or `audio_files`. Shared options include
            `maximum_length`, `episode_sorting`, `volume_adjustment`,
            `episode_min_duration_sec`, `episode_max_duration_sec`, and `wipe`.

    Raises:
        ValueError: If the config mixes podcast and local audio sources, or defines none.
    """
    podcast_url = _get_config_value(tonie_config, "podcast")
    audio_folder = _get_config_value(tonie_config, "audio_folder")
    audio_files = _normalize_audio_files_setting(_get_config_value(tonie_config, "audio_files"))
    wipe = _get_config_value(tonie_config, "wipe", default=True)

    if podcast_url:
        if audio_folder or audio_files:
            msg = f"Tonie '{tonie_id}' must not mix podcast and local audio settings."
            raise ValueError(msg)
        podcast = _create_podcast_from_config(tonie_config)
        tps.sync_podcast_to_tonie(podcast, tonie_id, tonie_config.maximum_length, wipe=wipe)
        return

    if audio_folder or audio_files:
        sync_kwargs = {
            "tonie_id": tonie_id,
            "max_minutes": tonie_config.maximum_length,
            "wipe": wipe,
            "sort_order": _get_config_value(tonie_config, "episode_sorting"),
            "volume_adjustment": _get_config_value(tonie_config, "volume_adjustment", 0),
            "episode_min_duration_sec": _get_config_value(tonie_config, "episode_min_duration_sec", 0),
            "episode_max_duration_sec": _get_config_value(
                tonie_config,
                "episode_max_duration_sec",
                MAXIMUM_TONIE_MINUTES * 60,
            ),
        }
        if audio_folder:
            sync_kwargs["directory"] = Path(audio_folder)
        if audio_files:
            sync_kwargs["files"] = [Path(path) for path in audio_files]

        tps.sync_files_to_tonie(**sync_kwargs)
        return

    msg = f"Tonie '{tonie_id}' must configure one source: podcast, audio_folder, or audio_files."
    raise ValueError(msg)


def _get_config_value(
    config: object, key: str, default: object = None
) -> object:
    """Read a config value with `.get()` first and attribute fallback.

    Args:
        config: Dynaconf section, dict-like object, or mock providing values.
        key: Field name to read.
        default: Value returned when the key is missing.

    Returns:
        The configured value, or `default` when neither lookup style yields a value.
    """
    if hasattr(config, "get"):
        value = config.get(key, default=default)
        if value is not default:
            return value

    config_vars = vars(config) if hasattr(config, "__dict__") else {}
    if key in config_vars:
        return config_vars[key]

    if isinstance(config, dict):
        return config.get(key, default)

    return default


def _normalize_audio_files_setting(audio_files: str | list[str] | None) -> list[str]:
    """Normalize the `audio_files` config value into a list of paths.

    Args:
        audio_files: Value from settings.toml. Valid values are `None`, a single string path,
            or a list of string paths.

    Returns:
        A list of path strings in the configured order.

    Raises:
        ValueError: If `audio_files` is neither a string nor a list of strings.
    """
    if audio_files is None:
        return []
    if isinstance(audio_files, str):
        return [audio_files]
    if isinstance(audio_files, list) and all(isinstance(path, str) for path in audio_files):
        return audio_files

    msg = "'audio_files' must be a string path or a list of string paths."
    raise ValueError(msg)


def _create_podcast_from_config(config: object) -> Podcast:
    """Create a Podcast instance from configuration.

    Args:
        config: The configuration section for a Tonie.

    Returns:
        Configured Podcast instance.
    """
    excluded_title_strings = _get_config_value(config, "excluded_title_strings", [])
    pinned_episode_names = _get_config_value(config, "pinned_episode_names", [])
    episode_max_duration_sec = _get_config_value(config, "episode_max_duration_sec", MAXIMUM_TONIE_MINUTES * 60)

    return Podcast(
        config.podcast,
        episode_sorting=config.episode_sorting,
        volume_adjustment=config.volume_adjustment,
        episode_min_duration_sec=config.episode_min_duration_sec,
        episode_max_duration_sec=episode_max_duration_sec,
        excluded_title_strings=excluded_title_strings,
        pinned_episode_names=pinned_episode_names,
    )


@app.command()
def list_tonies() -> None:
    """Print an overview of all creative-tonies."""
    tps = _create_tonie_podcast_sync()
    if tps:
        tps.print_tonies_overview()
    else:
        _console.print("Could not find credentials. Please run 'tonie-podcast-sync create-settings-file' first.")


@app.command()
def create_settings_file() -> None:
    """Create a settings file in your user home."""
    username, password = _get_credentials()

    tps = _validate_and_create_tps(username, password)
    if not tps:
        return

    tonies = tps.get_tonies()
    tonie_configs = _configure_tonies(tonies)

    _save_settings_file(tonie_configs)


def _get_credentials() -> tuple[str, str]:
    """Get user credentials from existing secrets or prompt user.

    Returns:
        Tuple of (username, password)
    """
    secrets_file = APP_SETTINGS_DIR / ".secrets.toml"

    if secrets_file.exists() and Confirm.ask("You already have secrets set, do you want to keep them?"):
        return settings.TONIE_CLOUD_ACCESS.USERNAME, settings.TONIE_CLOUD_ACCESS.PASSWORD

    username = Prompt.ask("Enter your Tonie CloudAPI username")
    password = Prompt.ask("Enter your password for Tonie CloudAPI", password=True)

    if Confirm.ask("Do you want to save your login data in a .secrets.toml file"):
        _save_credentials(username, password)

    return username, password


def _save_credentials(username: str, password: str) -> None:
    """Save user credentials to secrets file.

    Args:
        username: The Tonie Cloud username
        password: The Tonie Cloud password
    """
    APP_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    secrets_file = APP_SETTINGS_DIR / ".secrets.toml"

    with secrets_file.open("wb") as file:
        tomli_w.dump({"tonie_cloud_access": {"username": username, "password": password}}, file)


def _validate_and_create_tps(username: str, password: str) -> ToniePodcastSync | None:
    """Validate credentials and create ToniePodcastSync instance.

    Args:
        username: The Tonie Cloud username
        password: The Tonie Cloud password

    Returns:
        ToniePodcastSync instance if successful, None otherwise
    """
    try:
        return ToniePodcastSync(user=username, pwd=password)
    except KeyError:
        _console.print("It seems like you are not able to login, please provide different login data.")
        return None


def _configure_tonies(tonies: list[CreativeTonie]) -> dict:
    """Interactively configure podcasts for tonies.

    Args:
        tonies: List of available creative tonies

    Returns:
        Dictionary of tonie configurations
    """
    configs = {}

    for tonie in tonies:
        podcast_url = Prompt.ask(
            f"Which podcast do you want to set for Tonie {tonie.name} with ID {tonie.id}?\n"
            "Please enter the URL to the podcast, or leave empty if you don't want to set it.",
        )

        if not podcast_url:
            continue

        configs[tonie.id] = {"podcast": podcast_url, "name": tonie.name}
        _configure_tonie_settings(configs, tonie)

    return configs


def _configure_tonie_settings(configs: dict, tonie: CreativeTonie) -> None:
    """Configure settings for a specific tonie.

    Args:
        configs: The configuration dictionary to update
        tonie: The tonie to configure
    """
    _ask_episode_order(configs, tonie)
    _ask_maximum_tonie_length(configs, tonie)
    _ask_minimum_episode_length(configs, tonie)
    _ask_volume_adjustment(configs, tonie)
    _ask_wipe_setting(configs, tonie)


def _save_settings_file(configs: dict) -> None:
    """Save tonie configurations to settings file.

    Args:
        configs: Dictionary of tonie configurations
    """
    settings_file = APP_SETTINGS_DIR / "settings.toml"

    with settings_file.open("wb") as file:
        tomli_w.dump({"creative_tonies": configs}, file)


def _ask_episode_order(configs: dict, tonie: CreativeTonie) -> None:
    """Ask user for episode sorting preference.

    Args:
        configs: The configuration dictionary to update
        tonie: The tonie being configured
    """
    episode_order = Prompt.ask(
        "How would you like your podcast episodes sorted?",
        choices=list(EpisodeSorting),
        default=EpisodeSorting.BY_DATE_NEWEST_FIRST,
    )
    configs[tonie.id]["episode_sorting"] = episode_order


def _ask_maximum_tonie_length(configs: dict, tonie: CreativeTonie) -> None:
    """Ask user for maximum tonie length.

    Args:
        configs: The configuration dictionary to update
        tonie: The tonie being configured
    """
    max_length = IntPrompt.ask(
        "What should be the maximum total duration of all episodes on this tonie?\n"
        f"Defaults to {MAXIMUM_TONIE_MINUTES} minutes (the tonie's maximum).\n"
        "Only episodes up to these many minutes in total will be uploaded.\n",
        default=90,
    )

    if max_length is None or max_length <= 0 or max_length > MAXIMUM_TONIE_MINUTES:
        if max_length is not None:
            _console.print(
                f"The value you have entered is out of range. Will be set to default value of {MAXIMUM_TONIE_MINUTES}.",
            )
        configs[tonie.id]["maximum_length"] = MAXIMUM_TONIE_MINUTES
    else:
        configs[tonie.id]["maximum_length"] = max_length


def _ask_minimum_episode_length(configs: dict, tonie: CreativeTonie) -> None:
    """Ask user for minimum episode length.

    Args:
        configs: The configuration dictionary to update
        tonie: The tonie being configured
    """
    min_length = IntPrompt.ask(
        "What should be the minimum length (in sec) of each episode?\n"
        "Defaults to the minimum of 0 seconds, ie. no minimum length considered.\n"
        "Podcast episodes shorter than this value will not be uploaded.",
        default=0,
    )

    if min_length is None or min_length < 0:
        if min_length is not None and min_length < 0:
            _console.print("The value you have set is less than 0 and will be set to 0.")
        configs[tonie.id]["episode_min_duration_sec"] = 0
    elif min_length > 60 * configs[tonie.id]["maximum_length"]:
        _console.print(
            "The value you have set conflicts with the configured maximum available length for the tonie. "
            "It will be set to the maximum, but this might result in no episode being downloaded.",
        )
        configs[tonie.id]["episode_min_duration_sec"] = 60 * configs[tonie.id]["maximum_length"]
    else:
        configs[tonie.id]["episode_min_duration_sec"] = min_length


def _ask_volume_adjustment(configs: dict, tonie: CreativeTonie) -> None:
    """Ask user for volume adjustment setting.

    Args:
        configs: The configuration dictionary to update
        tonie: The tonie being configured
    """
    volume_adjustment = IntPrompt.ask(
        "Would you like to adjust the volume of the Episodes?\n"
        "If set, the downloaded audio will be adjusted by the given amount in dB.\n"
        "Defaults to 0, i.e. no adjustment",
        default=0,
    )

    if volume_adjustment is None or volume_adjustment < 0:
        if volume_adjustment is not None and volume_adjustment < 0:
            _console.print("The value you have set is less than 0 and will be set to 0.")
        configs[tonie.id]["volume_adjustment"] = 0
    else:
        configs[tonie.id]["volume_adjustment"] = volume_adjustment


def _ask_wipe_setting(configs: dict, tonie: CreativeTonie) -> None:
    """Ask user for wipe setting.

    Args:
        configs: The configuration dictionary to update
        tonie: The tonie being configured
    """
    wipe = Confirm.ask(
        "Should existing content be wiped before syncing new episodes?\n"
        "If set to 'yes', the tonie will be cleared before adding new content.\n"
        "If set to 'no', new episodes will be appended to existing content.\n"
        "Defaults to 'yes' (wipe existing content)",
        default=True,
    )
    configs[tonie.id]["wipe"] = wipe


if __name__ == "__main__":
    app()
