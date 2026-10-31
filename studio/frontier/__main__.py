import argparse
import os

from .store import Store


def main():
    p = argparse.ArgumentParser(description="Local Frontier PostgreSQL foundation")
    p.add_argument("command", choices=["init", "serve", "mcp", "seed"])
    p.add_argument("--namespace", required=True)
    p.add_argument("--schema", default="public")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    # Credentials stay in the environment/process, never in CLI arguments or logs.
    store = Store(os.environ["FRONTIER_DSN"], args.namespace, args.schema)
    if args.command == "init":
        store.initialize()
    elif args.command == "serve":
        from .http import make_server
        make_server(store, args.port).serve_forever()
    elif args.command == "mcp":
        from .mcp import make_mcp
        make_mcp(store).run(transport="stdio")
    elif args.command == "seed":
        from .seed import seed
        result = seed(store, os.environ["FRONTIER_TOKEN"], os.environ["FRONTIER_ACTOR"])
        print(f"Seeded {len(result)} attributed proposed records")


if __name__ == "__main__":
    main()
