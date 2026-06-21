from pathlib import Path
from unittest import mock

import pytest
from tonie_api.models import CreativeTonie, Household

from tonie_podcast_sync.toniepodcastsync import ToniePodcastSync


@pytest.fixture
def mock_tonie_api_with_tonie():
    """Mock TonieAPI with a configured tonie."""
    with mock.patch("tonie_podcast_sync.toniepodcastsync.TonieAPI") as _mock:
        household = Household(
            id="household-1", name="Test House", ownerName="Test Owner", access="owner", canLeave=True
        )

        tonie = CreativeTonie(
            id="tonie-123",
            householdId="household-1",
            name="Test Tonie",
            imageUrl="http://example.com/img.png",
            secondsRemaining=5400,
            secondsPresent=0,
            chaptersPresent=0,
            chaptersRemaining=99,
            transcoding=False,
            lastUpdate=None,
            chapters=[],
        )

        api_mock = mock.MagicMock()
        api_mock.get_households.return_value = [household]
        api_mock.get_all_creative_tonies.return_value = [tonie]
        _mock.return_value = api_mock
        yield api_mock


def _write_fake_mp3(path: Path) -> Path:
    path.write_bytes(b"fake mp3 data")
    return path


def _build_audiofile(path: Path, duration_sec: int, title: str):
    audio_file = mock.MagicMock()
    audio_file.fpath = path
    audio_file.title = title
    audio_file.duration_sec = duration_sec
    audio_file.published = ""
    return audio_file


def test_sync_files_dry_run_uses_manual_list_order_and_warns_about_time_limit(
    mock_tonie_api_with_tonie, tmp_path, capsys
):
    second = _write_fake_mp3(tmp_path / "02-second.mp3")
    first = _write_fake_mp3(tmp_path / "01-first.mp3")
    third = _write_fake_mp3(tmp_path / "03-third.mp3")

    tps = ToniePodcastSync("user", "pass")

    scanned_files = {
        second: _build_audiofile(second, 120, "Second"),
        first: _build_audiofile(first, 60, "First"),
        third: _build_audiofile(third, 90, "Third"),
    }

    with mock.patch.object(tps, "_build_local_audio_episode", side_effect=lambda path: scanned_files[path]):
        selected = tps.sync_files_to_tonie(
            [second, first, third],
            "tonie-123",
            max_minutes=3,
            dry_run=True,
        )

    assert [item.title for item in selected] == ["Second", "First"]
    mock_tonie_api_with_tonie.upload_file_to_tonie.assert_not_called()
    mock_tonie_api_with_tonie.clear_all_chapter_of_tonie.assert_not_called()

    captured = capsys.readouterr()
    assert "Dry run" in captured.out
    assert "Third" in captured.out
    assert "time limit" in captured.out


def test_sync_files_from_directory_uses_alphabetical_order_and_respects_wipe_false(
    mock_tonie_api_with_tonie, tmp_path
):
    c_file = _write_fake_mp3(tmp_path / "c-file.mp3")
    a_file = _write_fake_mp3(tmp_path / "a-file.mp3")
    b_file = _write_fake_mp3(tmp_path / "b-file.mp3")

    tps = ToniePodcastSync("user", "pass")

    scanned_files = {
        c_file: _build_audiofile(c_file, 30, "C"),
        a_file: _build_audiofile(a_file, 30, "A"),
        b_file: _build_audiofile(b_file, 30, "B"),
    }

    with mock.patch.object(tps, "_build_local_audio_episode", side_effect=lambda path: scanned_files[path]):
        tps.sync_files_to_tonie(directory=tmp_path, tonie_id="tonie-123", wipe=False)

    mock_tonie_api_with_tonie.clear_all_chapter_of_tonie.assert_not_called()
    upload_titles = [call.args[2] for call in mock_tonie_api_with_tonie.upload_file_to_tonie.call_args_list]
    assert upload_titles == ["A", "B", "C"]


def test_sync_files_allows_sort_override_for_explicit_file_list(mock_tonie_api_with_tonie, tmp_path):
    b_file = _write_fake_mp3(tmp_path / "b-file.mp3")
    a_file = _write_fake_mp3(tmp_path / "a-file.mp3")

    tps = ToniePodcastSync("user", "pass")

    scanned_files = {
        b_file: _build_audiofile(b_file, 30, "B"),
        a_file: _build_audiofile(a_file, 30, "A"),
    }

    with mock.patch.object(tps, "_build_local_audio_episode", side_effect=lambda path: scanned_files[path]):
        tps.sync_files_to_tonie([b_file, a_file], "tonie-123", sort_order="alphabetical")

    upload_titles = [call.args[2] for call in mock_tonie_api_with_tonie.upload_file_to_tonie.call_args_list]
    assert upload_titles == ["A", "B"]


def test_extract_local_audio_title_prefers_id3_title_and_falls_back_to_filename(
    mock_tonie_api_with_tonie, tmp_path
):
    titled_file = tmp_path / "fallback-name.mp3"
    titled_file.write_bytes(
        b"ID3\x03\x00\x00\x00\x00\x00\x17"
        b"TIT2\x00\x00\x00\x0d\x00\x00\x03Tagged Title"
        b"audio"
    )

    untitled_file = _write_fake_mp3(tmp_path / "plain-filename.mp3")

    tps = ToniePodcastSync("user", "pass")
    assert mock_tonie_api_with_tonie is not None

    assert tps._extract_local_audio_title(titled_file) == "Tagged Title"
    assert tps._extract_local_audio_title(untitled_file) == "plain-filename"
