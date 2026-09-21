from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List
import hashlib
import json

ALLOWED_STATUSES = {"TEST_ONLY", "PRODUCTION_APPROVED", "BLOCKED", "REVOKED"}
ALLOWED_LICENSE_STATES = {"VERIFIED", "UNVERIFIED", "RESTRICTED"}

@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    name: str
    version: str
    asset_type: str
    renderer: str
    path: str
    sha256: str
    status: str
    license_state: str
    license_name: str
    license_note: str
    instruments: tuple[str, ...]
    articulations: tuple[str, ...]
    source: str

class AssetRegistry:
    """
    LAISE T010 — Production Instrument Asset Registry v0.1

    Responsibilities:
    - load immutable asset metadata;
    - verify file presence and SHA-256;
    - expose instrument/articulation capabilities;
    - block production/commercial release when an asset is not approved.
    """

    def __init__(self, project_root: Path, manifest_path: Path):
        self.project_root = Path(project_root).resolve()
        self.manifest_path = Path(manifest_path).resolve()
        raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.schema_version = raw["schema_version"]
        self._records: Dict[str, AssetRecord] = {}

        for item in raw["assets"]:
            status = item["status"]
            license_state = item["license_state"]
            if status not in ALLOWED_STATUSES:
                raise ValueError(f"Invalid asset status: {status}")
            if license_state not in ALLOWED_LICENSE_STATES:
                raise ValueError(f"Invalid license_state: {license_state}")

            rec = AssetRecord(
                asset_id=item["asset_id"],
                name=item["name"],
                version=item["version"],
                asset_type=item["asset_type"],
                renderer=item["renderer"],
                path=item["path"],
                sha256=item["sha256"].lower(),
                status=status,
                license_state=license_state,
                license_name=item.get("license_name", ""),
                license_note=item.get("license_note", ""),
                instruments=tuple(item.get("instruments", [])),
                articulations=tuple(item.get("articulations", [])),
                source=item.get("source", ""),
            )
            if rec.asset_id in self._records:
                raise ValueError(f"Duplicate asset_id: {rec.asset_id}")
            self._records[rec.asset_id] = rec

    def get(self, asset_id: str) -> AssetRecord:
        if asset_id not in self._records:
            raise KeyError(f"Unknown asset_id: {asset_id}")
        return self._records[asset_id]

    def all(self) -> List[AssetRecord]:
        return list(self._records.values())

    def resolved_path(self, asset_id: str) -> Path:
        rec = self.get(asset_id)
        p = Path(rec.path)
        return p if p.is_absolute() else (self.project_root / p).resolve()

    @staticmethod
    def sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()

    def verify(self, asset_id: str) -> dict:
        rec = self.get(asset_id)
        path = self.resolved_path(asset_id)
        exists = path.is_file()
        actual = self.sha256_file(path) if exists else None
        hash_match = bool(exists and actual == rec.sha256)
        return {
            "asset_id": asset_id,
            "path": str(path),
            "exists": exists,
            "expected_sha256": rec.sha256,
            "actual_sha256": actual,
            "hash_match": hash_match,
            "status": rec.status,
            "license_state": rec.license_state,
        }

    def development_allowed(self, asset_id: str) -> bool:
        rec = self.get(asset_id)
        v = self.verify(asset_id)
        return v["hash_match"] and rec.status in {"TEST_ONLY", "PRODUCTION_APPROVED"}

    def production_allowed(self, asset_id: str) -> bool:
        rec = self.get(asset_id)
        v = self.verify(asset_id)
        return (
            v["hash_match"]
            and rec.status == "PRODUCTION_APPROVED"
            and rec.license_state == "VERIFIED"
        )

    def assert_release_allowed(self, asset_ids: Iterable[str], mode: str = "development"):
        asset_ids = list(dict.fromkeys(asset_ids))
        if mode not in {"development", "production"}:
            raise ValueError("mode must be 'development' or 'production'")

        denied = []
        for asset_id in asset_ids:
            allowed = (
                self.development_allowed(asset_id)
                if mode == "development"
                else self.production_allowed(asset_id)
            )
            if not allowed:
                denied.append(asset_id)

        if denied:
            raise PermissionError(
                f"LAISE asset gate blocked {mode} render/release for: {', '.join(denied)}"
            )

    def provenance_snapshot(self, asset_ids: Iterable[str]) -> list[dict]:
        snapshot = []
        for asset_id in dict.fromkeys(asset_ids):
            rec = self.get(asset_id)
            v = self.verify(asset_id)
            snapshot.append({
                "asset_id": rec.asset_id,
                "name": rec.name,
                "version": rec.version,
                "renderer": rec.renderer,
                "status": rec.status,
                "license_state": rec.license_state,
                "license_name": rec.license_name,
                "license_note": rec.license_note,
                "source": rec.source,
                "path": v["path"],
                "sha256": v["actual_sha256"] or rec.sha256,
                "hash_verified": v["hash_match"],
            })
        return snapshot
