"""Connectors to public biological data sources and model services.

Each module here retrieves public data or runs a public model and returns a
record carrying enough provenance to replay it: identifier, version, license,
checksum and a retrieval receipt. Per SPEC-005, *discovered*, *accessible*,
*retrieved*, *replayed* and *validated* are different states, and a connector
reports which one it reached rather than collapsing them into success.

No credential is read, printed or accepted as a function argument in this
package. Everything here is anonymous public access.
"""

from connectors.bioservices.receipts import RetrievalReceipt, sha256_bytes, sha256_file

__all__ = ["RetrievalReceipt", "sha256_bytes", "sha256_file"]
