import pytest

from frontier_compute.backup_service_check import check


def test_nested_check_refuses_before_resources(monkeypatch, tmp_path):
    monkeypatch.setenv('FRONTIER_RECOVERY_CHECK_RUNNING', '1')
    with pytest.raises(ValueError, match='Nested'):
        check(tmp_path, tmp_path / 'new', 'a' * 40, 'b' * 64, 'c' * 64)
    assert not (tmp_path / 'new').exists()


def test_requires_exact_hashes_before_resources(monkeypatch, tmp_path):
    monkeypatch.setenv('FRONTIER_RECOVERY_CHECK_RUNNING', '')
    with pytest.raises(ValueError, match='Exact source'):
        check(tmp_path, tmp_path / 'new', '--config=anything', 'b' * 64, 'c' * 64)
    assert not (tmp_path / 'new').exists()


def test_never_reuses_existing_check_root(monkeypatch, tmp_path):
    monkeypatch.setenv('FRONTIER_RECOVERY_CHECK_RUNNING', '')
    marker = tmp_path / 'precious'
    marker.write_text('existing state')
    with pytest.raises(ValueError, match='New short'):
        check(tmp_path, tmp_path, 'a' * 40, 'b' * 64, 'c' * 64)
    assert marker.read_text() == 'existing state'
