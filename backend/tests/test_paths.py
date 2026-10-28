import os

import pytest

from app.services.paths import PathValidationError, is_within, validate_scan_root


def test_valid_folder(tmp_path):
    assert validate_scan_root(str(tmp_path)) == tmp_path.resolve()


@pytest.mark.parametrize("raw", ["", "relative/folder", "a\x00b"])
def test_rejects_bad_input(raw):
    with pytest.raises(PathValidationError):
        validate_scan_root(raw)


def test_rejects_missing_and_file(tmp_path):
    with pytest.raises(PathValidationError, match="does not exist"):
        validate_scan_root(str(tmp_path / "nope"))
    f = tmp_path / "f.txt"
    f.write_text("x")
    with pytest.raises(PathValidationError, match="not a folder"):
        validate_scan_root(str(f))


def test_rejects_overlap_with_data_dir(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    with pytest.raises(PathValidationError, match="overlaps"):
        validate_scan_root(str(tmp_path), forbidden=[data])
    with pytest.raises(PathValidationError, match="overlaps"):
        validate_scan_root(str(data), forbidden=[data])


def test_is_within_blocks_traversal(tmp_path):
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    assert is_within(root / "sub", root)
    assert not is_within(root / ".." / "elsewhere", root)
    assert not is_within(tmp_path / "rootless", root)  # prefix but not child


@pytest.mark.skipif(os.name == "nt", reason="symlinks need admin rights on Windows")
def test_is_within_resolves_symlinks(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside)
    assert not is_within(root / "link", root)


def test_unicode_and_spaces(tmp_path):
    d = tmp_path / "Caméra 1 – 入口"
    d.mkdir()
    assert validate_scan_root(str(d)).name == "Caméra 1 – 入口"
