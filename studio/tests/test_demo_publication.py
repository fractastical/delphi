"""A demo cut is all-or-nothing: changed captions must not accompany a pinned film."""
import hashlib
import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("demo_builder", Path(__file__).parents[1] / "scripts/build_site.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_demo_requires_complete_pinned_media_and_refuses_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    directory = tmp_path / "artifacts/demo-video"
    directory.mkdir(parents=True)
    files = {}
    for role, name, data in (("video", "tour.mp4", b"media fixture"), ("poster", "poster.png", b"image fixture"),
                             ("captions", "tour.vtt", b"WEBVTT\n\n"), ("transcript", "tour.txt", b"Narration.")):
        (directory / name).write_bytes(data)
        files[role] = {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    manifest = {"status": "complete", "cuts": [{"id": "frontier-60s", "title": "One-minute tour", "duration_s": 60, "files": files}]}
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest))
    outputs = {}
    result = builder.demo_videos(builder.Inputs(), outputs)
    assert len(result["cuts"]) == 1 and not result["refused"] and len(outputs) == 5
    (directory / "tour.vtt").write_bytes(b"changed caption bytes")
    outputs = {}
    result = builder.demo_videos(builder.Inputs(), outputs)
    assert result["refused"] and not result["cuts"] and not outputs
    (directory / "tour.vtt").write_bytes(b"WEBVTT\n\n")
    files["video"]["path"] = "../outside.mp4"
    (directory.parent / "outside.mp4").write_bytes(b"media fixture")
    path.write_text(json.dumps(manifest))
    assert builder.demo_videos(builder.Inputs(), {})["refused"]
    files["video"]["path"] = "tour.mp4"
    manifest["status"] = "rendering"
    path.write_text(json.dumps(manifest))
    outputs = {}
    assert builder.demo_videos(builder.Inputs(), outputs)["cuts"] == [] and not outputs


def test_new_cut_is_additive_and_partial_export_cannot_hide_old_cut(tmp_path, monkeypatch):
    monkeypatch.setattr(builder, 'ROOT', tmp_path)
    for dirname, seconds in (('demo-video', 60), ('demo-video-90', 90)):
        d = tmp_path / 'artifacts' / dirname
        d.mkdir(parents=True)
        pins = {}
        for role, name, data in [('video', 'tour.mp4', b'fixture'), ('poster', 'poster.png', b'poster'),
                                 ('captions', 'tour.vtt', b'WEBVTT\n\n'), ('transcript', 'tour.txt', b'script')]:
            (d / name).write_bytes(data)
            pins[role] = {'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        (d / 'manifest.json').write_text(json.dumps({'status': 'complete', 'cuts': [{'id': f'frontier-{seconds}s', 'duration_s': seconds, 'title': f'{seconds}s', 'files': pins}]}))
    out = {}
    result = builder.demo_videos(builder.Inputs(), out)
    assert [c['id'] for c in result['cuts']] == ['frontier-60s', 'frontier-90s']
    assert len(out) == 10
    (tmp_path / 'artifacts/demo-video-90/tour.mp4').write_bytes(b'unfinished export')
    out = {}
    result = builder.demo_videos(builder.Inputs(), out)
    assert [c['id'] for c in result['cuts']] == ['frontier-60s']
    assert result['refused'][0]['id'] == 'frontier-90s'
    assert all('demo-video-90' not in p for p in out)
