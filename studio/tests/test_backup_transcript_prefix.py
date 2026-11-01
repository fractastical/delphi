import pytest

from frontier_compute import backup_inventory as inventory


def test_complete_line_cutoff_keeps_partial_tail_explicit(tmp_path):
    source = tmp_path / 'live.jsonl'
    source.write_bytes(b'{"first":1}\n{"partial":')
    target = tmp_path / 'staged.jsonl'
    result = inventory.snapshot_jsonl_prefix(source, target)
    assert target.read_bytes() == b'{"first":1}\n'
    assert result['captured_complete_line_prefix_bytes'] == 12
    assert result['source_bytes_at_start'] == 23


@pytest.mark.parametrize('change,accepted', [('append', True), ('rewrite', False), ('truncate', False)])
def test_live_changes_are_verified_without_claiming_later_messages(tmp_path, monkeypatch, change, accepted):
    source = tmp_path / 'live.jsonl'
    original = b'{"first":1}\n{"second":2}\n'
    source.write_bytes(original)
    target = tmp_path / 'staged.jsonl'
    real_hash = inventory.hash_prefix
    calls = 0

    def mutate_before_second_read(stream, length):
        nonlocal calls
        calls += 1
        if calls == 2:
            if change == 'append':
                with source.open('ab') as out:
                    out.write(b'{"later":3}\n')
            elif change == 'rewrite':
                source.write_bytes(original.replace(b'first', b'other'))
            else:
                source.write_bytes(b'{"first":1}\n')
        return real_hash(stream, length)

    monkeypatch.setattr(inventory, 'hash_prefix', mutate_before_second_read)
    if accepted:
        result = inventory.snapshot_jsonl_prefix(source, target)
        assert target.read_bytes() == original
        assert result['source_bytes_at_end'] > result['captured_complete_line_prefix_bytes']
    else:
        with pytest.raises(ValueError, match='changed|truncated'):
            inventory.snapshot_jsonl_prefix(source, target)


def test_symlink_source_is_never_followed(tmp_path):
    source = tmp_path / 'original'
    source.write_text('{}\n')
    link = tmp_path / 'link'
    link.symlink_to(source)
    with pytest.raises(OSError):
        inventory.snapshot_jsonl_prefix(link, tmp_path / 'out')
