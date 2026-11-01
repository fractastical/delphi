"""Prepare only Frontier source refs, working changes, scoped transcripts and service metadata."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

from frontier_compute.backup import exclusion


def command(argv, *, cwd=None, destination=None, timeout=180):
    if destination:
        with Path(destination).open('wb') as stream:
            subprocess.run(argv, cwd=cwd, stdout=stream, stderr=subprocess.PIPE, check=True, timeout=timeout)
        return None
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=True, timeout=timeout).stdout


def prepare(repo, staging, recipients):
    repo, staging = Path(repo).resolve(), Path(staging).resolve()
    metadata = staging / 'metadata'
    metadata.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.umask(0o077)
    blocks = command(['git', 'worktree', 'list', '--porcelain'], cwd=repo).strip().split('\n\n')
    trees, files = [], []
    reachable = set(command(['git', 'rev-list', '--all'], cwd=repo).splitlines())
    for block in blocks:
        values = dict(line.split(' ', 1) for line in block.splitlines() if ' ' in line)
        path = Path(values['worktree'])
        if not path.is_dir() or not str(path).startswith('/data/worktrees/delphi-frontier/'):
            continue
        name = path.name
        values['head_reachable_from_refs'] = values['HEAD'] in reachable
        if not values['head_reachable_from_refs']:
            raise ValueError('A worktree HEAD is not reachable from bundled refs')
        status = command(['git', 'status', '--porcelain=v1', '-z', '--untracked-files=all'], cwd=path)
        (metadata / f'worktree-{name}-status.json').write_text(json.dumps(status.split('\0')))
        command(['git', 'diff', '--binary', 'HEAD'], cwd=path, destination=metadata / f'worktree-{name}.patch')
        selected = set(command(['git', 'ls-files', '--modified', '--others', '--exclude-standard', '-z'], cwd=path).split('\0'))
        selected.update(command(['git', 'diff', '--name-only', '--cached', '-z'], cwd=path).split('\0'))
        for rel in sorted(x for x in selected if x):
            logical = f'worktrees/{name}/{rel}'
            if not exclusion(logical):
                files.append({'path': str(path / rel), 'logical': logical})
        trees.append(values)
    (metadata / 'worktrees.json').write_text(json.dumps(trees, indent=2)+'\n')
    command(['git', 'show-ref'], cwd=repo, destination=metadata / 'source-refs.txt')
    command(['git', 'bundle', 'create', str(metadata / 'frontier-all-refs.bundle'), '--all'], cwd=repo, timeout=600)
    command(['git', 'bundle', 'verify', str(metadata / 'frontier-all-refs.bundle')], cwd=repo, destination=metadata / 'git-bundle-verification.txt')
    transcript_roots = [Path.home()/'.codex/sessions', Path.home()/'.claude/projects/-home-ubuntu-git-morphoswarm']
    selected_transcripts = []
    markers = (b'/data/worktrees/delphi-frontier/', b'frontier.morphoswarm.ai', b'/data/artifacts/delphi-evolve-rethink')
    since = datetime(2026,10,30,tzinfo=timezone.utc).timestamp()
    for folder in transcript_roots:
        if not folder.exists():
            continue
        for path in folder.rglob('*.jsonl'):
            if path.is_symlink() or path.stat().st_mtime < since:
                continue
            matched = False
            with path.open('rb') as stream:
                carry = b''
                while block := stream.read(1 << 20):
                    chunk = carry + block
                    if any(marker in chunk for marker in markers):
                        matched = True
                        break
                    carry = chunk[-128:]
            if matched:
                label = 'codex' if '.codex' in str(folder) else 'claude'
                logical = f'transcripts/{label}/{path.relative_to(folder).as_posix()}'
                files.append({'path': str(path), 'logical': logical})
                selected_transcripts.append({'path': str(path), 'bytes_at_inventory': path.stat().st_size})
    (metadata/'transcript-selection.json').write_text(json.dumps({'since_utc':'2026-10-30T00:00:00Z','selection':'JSONL modified in hackathon window containing exact Frontier URL/worktree/artifact markers; unrelated sessions omitted.','files':selected_transcripts},indent=2)+'\n')
    command(['journalctl','--user','-u','delphi-frontier-*','-u','frontier-infra*','-u','frontier-cfd-collector','-u','frontier-betse-collector','--since','2026-10-30','--no-pager','-o','short-iso'],destination=metadata/'frontier-services.log')
    for unit in ['delphi-frontier-postgres.service','delphi-frontier-web.service','delphi-frontier-mcp.service']:
        result = subprocess.run(['systemctl','--user','cat',unit],capture_output=True,text=True)
        lines=[]
        for line in result.stdout.splitlines():
            if line.startswith('Environment='):
                line='Environment= # omitted; recreate runtime configuration without old credentials'
            lines.append(line)
        (metadata/unit).write_text('\n'.join(lines)+'\n')
    command(['/usr/lib/postgresql/16/bin/pg_dump','--version'],destination=metadata/'postgres-version.txt')
    command(['age','--version'],destination=metadata/'age-version.txt')
    config={'recipients':str(Path(recipients).resolve()),'max_total_bytes':30_000_000_000,'max_file_bytes':5_000_000_000,
            'roots':[{'label':'metadata','path':str(metadata)},
                     {'label':'database','path':str(staging/'database-v2')},
                     {'label':'artifacts','path':'/data/artifacts/delphi-evolve-rethink'}],
            'files':files}
    (staging/'snapshot-config.json').write_text(json.dumps(config,indent=2)+'\n')
    result={'worktrees':len(trees),'selected_worktree_files_and_transcripts':len(files),'transcripts':len(selected_transcripts),'config':str(staging/'snapshot-config.json')}
    (metadata/'inventory-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',required=True)
    p.add_argument('--staging',required=True)
    p.add_argument('--recipients',required=True)
    a=p.parse_args()
    print(json.dumps(prepare(a.repo,a.staging,a.recipients)))
