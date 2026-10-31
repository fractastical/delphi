import argparse
import json
import os
import sys

from .store import FrontierError, Store


def _startup_error(message: str) -> "NoReturn":
    # Fixed texts only: never an exception's own text, which can carry connection details.
    print("frontier mcp: " + message, file=sys.stderr)
    sys.exit(2)


def _mcp_server(store: Store, allow_write: bool):
    from .mcp import make_mcp
    if not allow_write:
        return make_mcp(store)
    token = os.environ.get("FRONTIER_TOKEN")
    if not token:
        _startup_error("--allow-write needs the process credential in the FRONTIER_TOKEN environment variable (never an argument)")
    try:
        return make_mcp(store, allow_write=True, token=token)
    except FrontierError as e:
        _startup_error(f"the configured credential was refused by the node ({e.code}); write tools not enabled")
    except ValueError:
        _startup_error("the configured principal cannot write this namespace as a contributor; write tools not enabled")
    except Exception:       # noqa: BLE001
        _startup_error("cannot reach the store to verify the credential; write tools not enabled")


def _smoke(args) -> int:
    """Read-only client round trip with the official MCP SDK against `python -m frontier mcp`. Writes nothing."""
    import asyncio

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    env = {"FRONTIER_DSN": os.environ["FRONTIER_DSN"], "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    if os.environ.get("PYTHONPATH"):
        env["PYTHONPATH"] = os.environ["PYTHONPATH"]
    cmd = ["-m", "frontier", "mcp", "--namespace", args.namespace, "--schema", args.schema]
    if args.allow_write:
        cmd.append("--allow-write")
        env["FRONTIER_TOKEN"] = os.environ.get("FRONTIER_TOKEN", "")

    async def run():
        params = StdioServerParameters(command=sys.executable, args=cmd, env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                caps = json.loads((await session.call_tool("frontier_capabilities", {})).content[0].text)
                found = await session.call_tool("frontier_search", {"limit": 1})
                resources = [str(r.uri) for r in (await session.list_resources()).resources]
                return {"ok": True, "namespace": args.namespace, "mode": caps["mode"], "principal": caps["principal"],
                        "tools": [{"name": t.name, "readOnly": bool(t.annotations and t.annotations.readOnlyHint)} for t in tools],
                        "resources": resources, "search_ok": not found.isError, "not_available": caps["not_available"]}

    out = asyncio.run(asyncio.wait_for(run(), timeout=args.timeout))
    expected = "write_enabled" if args.allow_write else "read_only"
    if out["mode"] != expected or not out["search_ok"]:
        print(json.dumps({"ok": False, "expected_mode": expected, "mode": out["mode"]}))
        return 1
    text = json.dumps(out, indent=1)
    token = os.environ.get("FRONTIER_TOKEN")
    if token and token in text:
        print(json.dumps({"ok": False, "error": "credential would have been printed; output suppressed"}))
        return 1
    print(text)
    return 0


def main():
    p = argparse.ArgumentParser(description="Local Frontier PostgreSQL foundation")
    p.add_argument("command", choices=["init", "serve", "mcp", "mcp-smoke", "seed"])
    p.add_argument("--namespace", required=True)
    p.add_argument("--schema", default="public")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--allow-write", action="store_true",
                   help="mcp / mcp-smoke: register the proposal, lease and transition tools, acting as the principal in FRONTIER_TOKEN. Default: read-only.")
    p.add_argument("--timeout", type=int, default=30, help="mcp-smoke: seconds before giving up")
    args = p.parse_args()
    # Credentials stay in the environment/process, never in CLI arguments or logs.
    store = Store(os.environ["FRONTIER_DSN"], args.namespace, args.schema)
    if args.command == "init":
        store.initialize()
    elif args.command == "serve":
        from .http import make_server
        make_server(store, args.port).serve_forever()
    elif args.command == "mcp":
        _mcp_server(store, args.allow_write).run(transport="stdio")
    elif args.command == "mcp-smoke":
        sys.exit(_smoke(args))
    elif args.command == "seed":
        from .seed import seed
        result = seed(store, os.environ["FRONTIER_TOKEN"], os.environ["FRONTIER_ACTOR"])
        print(f"Seeded {len(result)} attributed proposed records")


if __name__ == "__main__":
    main()
