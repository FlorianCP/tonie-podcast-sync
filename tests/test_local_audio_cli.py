from pathlib import Path
from unittest import mock

from typer.testing import CliRunner

from tonie_podcast_sync.cli import app, update_tonies

runner = CliRunner()


def test_update_tonies_uses_audio_folder_config_for_local_files():
    mock_settings = mock.MagicMock()
    mock_settings.TONIE_CLOUD_ACCESS.USERNAME = "test_user"
    mock_settings.TONIE_CLOUD_ACCESS.PASSWORD = "test_pass"

    mock_tonie_config = mock.MagicMock()
    mock_tonie_config.maximum_length = 45
    mock_tonie_config.audio_folder = "/audio/bedtime"
    mock_tonie_config.get = mock.MagicMock(
        side_effect=lambda key, default=None: {
            "audio_folder": "/audio/bedtime",
            "audio_files": default,
            "episode_sorting": "alphabetical",
            "volume_adjustment": 2,
            "episode_min_duration_sec": 15,
            "episode_max_duration_sec": 1200,
            "wipe": False,
        }.get(key, default)
    )

    mock_settings.CREATIVE_TONIES = {"test-tonie-id": mock_tonie_config}

    with (
        mock.patch("tonie_podcast_sync.cli.settings", mock_settings),
        mock.patch("tonie_podcast_sync.cli.ToniePodcastSync") as mock_tps_class,
        mock.patch("tonie_podcast_sync.cli.Podcast") as mock_podcast_class,
    ):
        mock_tps_instance = mock.MagicMock()
        mock_tps_class.return_value = mock_tps_instance

        update_tonies()

        mock_podcast_class.assert_not_called()

        mock_tps_instance.sync_files_to_tonie.assert_called_once_with(
            tonie_id="test-tonie-id",
            directory=Path("/audio/bedtime"),
            max_minutes=45,
            wipe=False,
            sort_order="alphabetical",
            volume_adjustment=2,
            episode_min_duration_sec=15,
            episode_max_duration_sec=1200,
        )


def test_update_tonies_uses_audio_files_config_for_local_files():
    mock_settings = mock.MagicMock()
    mock_settings.TONIE_CLOUD_ACCESS.USERNAME = "test_user"
    mock_settings.TONIE_CLOUD_ACCESS.PASSWORD = "test_pass"

    files = ["/audio/a.mp3", "/audio/b.mp3"]
    mock_tonie_config = mock.MagicMock()
    mock_tonie_config.maximum_length = 30
    mock_tonie_config.get = mock.MagicMock(
        side_effect=lambda key, default=None: {
            "audio_folder": default,
            "audio_files": files,
            "episode_sorting": "manual",
            "volume_adjustment": -1,
            "episode_min_duration_sec": 5,
            "episode_max_duration_sec": 600,
            "wipe": True,
        }.get(key, default)
    )

    mock_settings.CREATIVE_TONIES = {"test-tonie-id": mock_tonie_config}

    with (
        mock.patch("tonie_podcast_sync.cli.settings", mock_settings),
        mock.patch("tonie_podcast_sync.cli.ToniePodcastSync") as mock_tps_class,
        mock.patch("tonie_podcast_sync.cli.Podcast") as mock_podcast_class,
    ):
        mock_tps_instance = mock.MagicMock()
        mock_tps_class.return_value = mock_tps_instance

        update_tonies()

        mock_podcast_class.assert_not_called()

        mock_tps_instance.sync_files_to_tonie.assert_called_once_with(
            tonie_id="test-tonie-id",
            files=[Path("/audio/a.mp3"), Path("/audio/b.mp3")],
            max_minutes=30,
            wipe=True,
            sort_order="manual",
            volume_adjustment=-1,
            episode_min_duration_sec=5,
            episode_max_duration_sec=600,
        )


def test_help_mentions_local_audio_sync_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "sync-local-files" in result.stdout


def test_sync_local_files_command_help_mentions_directory_and_files_options():
    result = runner.invoke(app, ["sync-local-files", "--help"])

    assert result.exit_code == 0
    assert "--directory" in result.stdout
    assert "--files" in result.stdout
