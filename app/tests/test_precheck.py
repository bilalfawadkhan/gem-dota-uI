import pytest

from gemstudio.precheck import MAGIC, ReplayFileError, check_replay_file


def test_accepts_the_fixture(fixture_dem):
    assert check_replay_file(fixture_dem) == fixture_dem


def test_missing_file(tmp_path):
    with pytest.raises(ReplayFileError, match="not found"):
        check_replay_file(tmp_path / "nope.dem")


def test_compressed_replay_is_explained(tmp_path):
    packed = tmp_path / "match.dem.bz2"
    packed.write_bytes(b"BZh9")
    with pytest.raises(ReplayFileError, match="compressed"):
        check_replay_file(packed)


def test_wrong_extension(tmp_path):
    other = tmp_path / "notes.txt"
    other.write_bytes(MAGIC)
    with pytest.raises(ReplayFileError, match=r"\.dem"):
        check_replay_file(other)


def test_empty_file(tmp_path):
    empty = tmp_path / "empty.dem"
    empty.write_bytes(b"")
    with pytest.raises(ReplayFileError, match="empty"):
        check_replay_file(empty)


def test_wrong_header(tmp_path):
    junk = tmp_path / "junk.dem"
    junk.write_bytes(b"not a replay at all")
    with pytest.raises(ReplayFileError, match="not look like"):
        check_replay_file(junk)
