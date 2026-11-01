import pytest

from scripts.repository_activity import combine, normalize_commits, timestamp

START, END = "2026-10-31T07:00:00Z", "2026-11-01T06:00:00Z"


def commit(sha="a" * 40, date=START, parents=1, author="contributor"):
    return {"sha": sha, "parents": [{}] * parents, "author": {"login": author} if author else None,
            "commit": {"committer": {"date": date, "email": "omit@example.invalid"}, "message": "omit message"}}


def test_window_uses_actual_committer_date_and_omits_private_fields():
    rows = normalize_commits([commit(), commit(), commit("b" * 40, "2026-10-31T06:59:59Z"),
                              commit("c" * 40, END, 2, None)], START, END)
    assert len(rows) == 2 and rows[1]["parent_count"] == 2
    assert rows[1]["author_login"] is None
    assert "email" not in str(rows) and "message" not in str(rows)


def test_shared_history_is_counted_once_and_merges_remain_separate():
    a = normalize_commits([commit(), commit("b" * 40, parents=2)], START, END)
    b = normalize_commits([commit(), commit("c" * 40, author=None)], START, END)
    report = combine([{"repository": "a/one", "commits": a}, {"repository": "b/two", "commits": b}], START, END)
    assert report["sum_of_repository_commit_counts"] == 4
    assert report["deduplicated_counts"] == {"commit_objects": 3, "merge_commits": 1, "non_merge_commits": 2,
                                              "distinct_linked_author_accounts": 1, "commits_without_linked_author": 1}
    assert report["shared_commit_membership"] == {"a" * 40: ["a/one", "b/two"]}


def test_unknown_timezones_conflicting_records_and_repeated_repos_refused():
    with pytest.raises(ValueError, match="timezone"):
        timestamp("2026-10-31T07:00:00")
    with pytest.raises(ValueError, match="Conflicting"):
        normalize_commits([commit(), commit(parents=2)], START, END)
    with pytest.raises(ValueError, match="Duplicate"):
        combine([{"repository": "a/one", "commits": []}] * 2, START, END)
