import pytest

from frontier_compute.backup_service_check import check
from frontier_compute.backup_service_probe import probe


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


def test_probe_refuses_host_python_before_database_or_server(tmp_path):
    with pytest.raises(ValueError, match='newly created application virtual environment'):
        probe(tmp_path, tmp_path, tmp_path, 'a' * 40)
    assert list(tmp_path.iterdir()) == []
