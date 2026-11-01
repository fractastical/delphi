"""BioModels connector: bounded search, metadata, retrieval, SBML inspection and replay.

Discovered, accessible, retrieved, replayed and validated are separate states (SPEC-005,
Connector row). Each function here advances at most one of them and returns the evidence for it.
"""

from .client import BioModelsClient, ConnectorError, LICENCE
from .replay import replay_collier1996
from .sbml import UnsupportedSBML, inspect_sbml

__all__ = ["BioModelsClient", "ConnectorError", "LICENCE", "UnsupportedSBML", "inspect_sbml", "replay_collier1996"]
