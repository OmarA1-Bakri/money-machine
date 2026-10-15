"""Artifact storage. Simulation only; no network client."""

from money_machine.integrations.storage.interface import StoredObject
from money_machine.integrations.storage.local import LocalAssetStore
from money_machine.integrations.storage.s3 import SimS3AssetStore

__all__ = ["LocalAssetStore", "SimS3AssetStore", "StoredObject"]
