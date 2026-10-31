"""Operator tooling for the persistent node. Idempotent bootstrap, credential provisioning into mode-600 files, read-only status.

* No credential is ever an argument, printed, or logged. `provision` generates a new random credential and writes it ONLY to the file you name
  (created with O_EXCL, mode 0600, inside a private directory that is not in a git work tree); stdout carries identities and the file path.
* Re-running `provision` for an existing file is a no-op when the file's credential already matches the requested principal, and an error otherwise.
  It never overwrites a credential file.
* Independent review stays independent: one principal cannot hold both reviewer and contributor/coordinator roles, and an operator id cannot span
  the two sides. (The store separately refuses a reviewer whose operator submitted the record.)
* Nothing here seeds records, accepts anything, or opens a write path: seeded scientific records stay `proposed` until an independent reviewer acts.
"""
import argparse
import json
import os
import secrets
import sys
from pathlib import Path

from .store import FrontierError, Store

ROLES = {"contributor", "reviewer", "coordinator"}
WRITER_ROLES = {"contributor", "coordinator"}


class AdminError(Exception):
    pass


def status(store: Store) -> dict:
    with store.connection() as c:
        total = c.execute("SELECT count(*) AS n FROM record_versions").fetchone()["n"]
        by = c.execute("SELECT v.kind, s.status, count(*) AS n FROM record_versions v JOIN local_states s USING(version) GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
        who = c.execute("SELECT actor, operator, roles, namespaces, daily_write_limit FROM principals ORDER BY actor, operator").fetchall()
    return {"namespace": store.namespace, "schema": store.schema, "records": total,
            "by_kind_and_local_status": [{"kind": r["kind"], "local_status": r["status"], "count": r["n"]} for r in by],
            "principals": [{"actor": p["actor"], "operator": p["operator"], "roles": p["roles"], "namespaces": p["namespaces"],
                            "daily_write_limit": p["daily_write_limit"]} for p in who]}


def bootstrap(store: Store) -> dict:
    store.initialize()          # CREATE ... IF NOT EXISTS; refuses a store that already belongs to another namespace
    return {"initialized": True, **status(store)}


def _private_dir(path: Path):
    parent = path.parent
    if not parent.is_dir():
        raise AdminError("credential directory does not exist")
    if parent.stat().st_mode & 0o077:
        raise AdminError("credential directory must not be accessible to group or others (chmod 700)")
    for anc in [parent, *parent.resolve().parents]:
        g = anc / ".git"
        if g.is_file() or (g.is_dir() and (g / "HEAD").exists()):        # a real work tree or linked worktree, not a stray empty ".git" directory
            raise AdminError("credential files must live outside any git work tree")


def provision(store: Store, *, actor: str, operator: str, roles: set, namespaces: list, daily_limit: int, credential_file: Path) -> dict:
    roles = set(roles)
    if not roles or not roles <= ROLES:
        raise AdminError("roles must be a non-empty subset of contributor, reviewer, coordinator")
    if "reviewer" in roles and roles & WRITER_ROLES:
        raise AdminError("reviewer authority stays separate: a principal cannot be both reviewer and contributor/coordinator")
    credential_file = Path(credential_file).absolute()
    _private_dir(credential_file)
    with store.connection() as c:
        peers = c.execute("SELECT roles FROM principals WHERE operator = %s", (operator,)).fetchall()
    for p in peers:
        have = set(p["roles"])
        if ("reviewer" in roles and have & WRITER_ROLES) or (roles & WRITER_ROLES and "reviewer" in have):
            raise AdminError("operator id already stands on the other side of the review boundary; use a different operator id")
    wanted = {"actor": actor, "operator": operator, "roles": sorted(roles), "namespaces": sorted(namespaces or [store.namespace])}
    if credential_file.exists():
        if credential_file.stat().st_mode & 0o077:
            raise AdminError("existing credential file is accessible to others; refusing to use it")
        try:
            have = store.principal(credential_file.read_text().strip())
        except FrontierError:
            raise AdminError("credential file exists but its credential is not recognised by this node; refusing to overwrite") from None
        if {k: (sorted(have[k]) if isinstance(have[k], list) else have[k]) for k in wanted} != wanted:
            raise AdminError("credential file belongs to a different principal; refusing to overwrite")
        return {"status": "already_provisioned", **wanted, "credential_file": str(credential_file)}
    token = "frontier-" + secrets.token_urlsafe(48)
    fd = os.open(credential_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(token + "\n")
        store.provision(token, actor, operator, sorted(roles), wanted["namespaces"], daily_limit)
    except BaseException:
        credential_file.unlink(missing_ok=True)
        raise
    return {"status": "provisioned", **wanted, "daily_write_limit": daily_limit, "credential_file": str(credential_file)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Frontier node operator tooling (credentials never printed)")
    p.add_argument("command", choices=["bootstrap", "provision", "status"])
    p.add_argument("--namespace", required=True)
    p.add_argument("--schema", default="public")
    p.add_argument("--actor")
    p.add_argument("--operator")
    p.add_argument("--roles", default="")
    p.add_argument("--namespaces", default="")
    p.add_argument("--daily-limit", type=int, default=100)
    p.add_argument("--credential-file", type=Path)
    a = p.parse_args(argv)
    store = Store(os.environ["FRONTIER_DSN"], a.namespace, a.schema)
    try:
        if a.command == "bootstrap":
            out = bootstrap(store)
        elif a.command == "status":
            out = status(store)
        else:
            if not (a.actor and a.operator and a.roles and a.credential_file):
                raise AdminError("provision needs --actor --operator --roles --credential-file")
            out = provision(store, actor=a.actor, operator=a.operator, roles=set(a.roles.split(",")),
                            namespaces=[x for x in a.namespaces.split(",") if x], daily_limit=a.daily_limit, credential_file=a.credential_file)
    except AdminError as e:
        print(json.dumps({"refused": str(e)}), file=sys.stderr)
        return 2
    except (FrontierError, ValueError) as e:
        print(json.dumps({"refused": type(e).__name__}), file=sys.stderr)       # never the exception text: it can echo arguments
        return 2
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
