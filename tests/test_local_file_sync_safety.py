from pathlib import Path
from unittest import mock

import pytest
from tonie_api.models import Chapter, CreativeTonie, Household

from tonie_podcast_sync.cli import _get_config_value
from tonie_podcast_sync.toniepodcastsync import ToniePodcastSync


def _tonie(seconds_remaining: float = 5400, chapters_remaining: int = 99) -> CreativeTonie:
    return CreativeTonie(
        id="tonie-123",
        householdId="household-1",
        name="Test Tonie",
        imageUrl="http://example.com/img.png",
        secondsRemaining=seconds_remaining,
        secondsPresent=5400 - seconds_remaining,
        chaptersPresent=0,
        chaptersRemaining=chapters_remaining,
        transcoding=False,
        lastUpdate=None,
        chapters=[],
    )


@pytest.fixture
def api():
    """Mock TonieAPI whose cloud state records uploaded chapters."""
    with mock.patch("tonie_podcast_sync.toniepodcastsync.TonieAPI") as api_class:
        api_mock = mock.MagicMock()
        api_mock.get_households.return_value = [
            Household(id="household-1", name="House", ownerName="Owner", access="owner", canLeave=True)
        ]
        api_mock.tonie = _tonie()
        api_mock.get_all_creative_tonies.side_effect = lambda: [api_mock.tonie]
        api_mock.rejected_titles = set()

        def upload(_tonie, _path, title):
            if title in api_mock.rejected_titles:
                return  # tonie-api swallows failed chapter requests without raising
            api_mock.tonie.chapters.append(Chapter(id=title, title=title, file="file", seconds=0, transcoding=True))

        def clear(_tonie):
            api_mock.tonie.chapters.clear()

        api_mock.upload_file_to_tonie.side_effect = upload
        api_mock.clear_all_chapter_of_tonie.side_effect = clear
        api_class.return_value = api_mock
        yield api_mock


def _audio(path: Path, duration_sec: int, title: str, volume_adjustment: int = 0):
    path.write_bytes(b"fake mp3 data")
    audio = mock.MagicMock()
    audio.fpath = path
    audio.title = title
    audio.duration_sec = duration_sec
    audio.published = ""
    audio.volume_adjustment = volume_adjustment
    return audio


def _sync(tps: ToniePodcastSync, files: dict, **kwargs):
    with mock.patch.object(tps, "_build_local_audio_episode", side_effect=lambda path, **_: files[path]):
        return tps.sync_files_to_tonie(list(files), "tonie-123", **kwargs)


def test_missing_directory_leaves_tonie_unchanged(api, tmp_path, capsys):
    tps = ToniePodcastSync("user", "pass")

    result = tps.sync_files_to_tonie(directory=tmp_path / "missing", tonie_id="tonie-123")

    assert result == []
    api.clear_all_chapter_of_tonie.assert_not_called()
    api.upload_file_to_tonie.assert_not_called()
    assert "unchanged" in capsys.readouterr().out


def test_empty_selection_does_not_wipe(api, tmp_path, capsys):
    tps = ToniePodcastSync("user", "pass")
    files = {tmp_path / "long.mp3": _audio(tmp_path / "long.mp3", 600, "Long")}

    result = _sync(tps, files, episode_max_duration_sec=60)

    assert result == []
    api.clear_all_chapter_of_tonie.assert_not_called()
    assert "unchanged" in capsys.readouterr().out


def test_missing_explicit_file_leaves_tonie_unchanged(api, tmp_path, capsys):
    present = tmp_path / "present.mp3"
    present.write_bytes(b"fake mp3 data")
    tps = ToniePodcastSync("user", "pass")

    result = tps.sync_files_to_tonie([present, tmp_path / "missing.mp3"], "tonie-123")

    assert result == []
    api.clear_all_chapter_of_tonie.assert_not_called()
    api.upload_file_to_tonie.assert_not_called()
    assert "missing.mp3" in capsys.readouterr().out


@pytest.mark.usefixtures("api")
def test_directory_scan_matches_uppercase_suffix_and_skips_directories(tmp_path):
    (tmp_path / "upper.MP3").write_bytes(b"fake")
    (tmp_path / "folder.mp3").mkdir()
    tps = ToniePodcastSync("user", "pass")

    paths = tps._resolve_local_audio_paths(directory=tmp_path)

    assert paths == [tmp_path / "upper.MP3"]


def test_preparation_failure_happens_before_wipe(api, tmp_path):
    tps = ToniePodcastSync("user", "pass")
    files = {tmp_path / "a.mp3": _audio(tmp_path / "a.mp3", 60, "A", volume_adjustment=3)}

    with (
        mock.patch.object(tps, "_create_adjusted_local_audio_copy", side_effect=OSError("disk full")),
        pytest.raises(OSError, match="disk full"),
    ):
        _sync(tps, files)

    api.clear_all_chapter_of_tonie.assert_not_called()
    api.upload_file_to_tonie.assert_not_called()


def test_adjusted_copies_are_removed_after_sync(api, tmp_path):
    tps = ToniePodcastSync("user", "pass")
    files = {tmp_path / "a.mp3": _audio(tmp_path / "a.mp3", 60, "A", volume_adjustment=3)}
    uploaded_paths = []
    api.upload_file_to_tonie.side_effect = lambda _tonie, path, _title: uploaded_paths.append(Path(path))

    with mock.patch.object(tps, "_process_audio_content", return_value=b"adjusted"):
        _sync(tps, files)

    assert len(uploaded_paths) == 1
    assert uploaded_paths[0] != tmp_path / "a.mp3"
    assert not uploaded_paths[0].exists()


def test_chapter_missing_in_cloud_is_reported_as_failure(api, tmp_path, capsys):
    api.rejected_titles = {"B"}
    tps = ToniePodcastSync("user", "pass")
    files = {
        tmp_path / "a.mp3": _audio(tmp_path / "a.mp3", 60, "A"),
        tmp_path / "b.mp3": _audio(tmp_path / "b.mp3", 60, "B"),
    }

    result = _sync(tps, files)

    assert [episode.title for episode in result] == ["A"]
    out = capsys.readouterr().out
    assert "Failed to upload 1 episode(s): ['B']" in out
    assert "Successfully uploaded ['A']" in out


def test_append_respects_remaining_seconds(api, tmp_path):
    api.tonie = _tonie(seconds_remaining=100)
    tps = ToniePodcastSync("user", "pass")
    files = {
        tmp_path / "a.mp3": _audio(tmp_path / "a.mp3", 60, "A"),
        tmp_path / "b.mp3": _audio(tmp_path / "b.mp3", 60, "B"),
    }

    result = _sync(tps, files, wipe=False)

    assert [episode.title for episode in result] == ["A"]


def test_append_respects_remaining_chapters(api, tmp_path):
    api.tonie = _tonie(chapters_remaining=1)
    tps = ToniePodcastSync("user", "pass")
    files = {
        tmp_path / "a.mp3": _audio(tmp_path / "a.mp3", 60, "A"),
        tmp_path / "b.mp3": _audio(tmp_path / "b.mp3", 60, "B"),
    }

    result = _sync(tps, files, wipe=False)

    assert [episode.title for episode in result] == ["A"]


def test_get_config_value_supports_plain_dicts():
    assert _get_config_value({"wipe": False}, "wipe", default=True) is False
    assert _get_config_value({}, "wipe", default=True) is True
