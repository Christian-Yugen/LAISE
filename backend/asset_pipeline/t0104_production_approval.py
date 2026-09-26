from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class ApprovalResult:
    passed: bool
    checks: dict[str, bool]
    registry_path: str
    lipp_path: str
    release_record_path: str


class T0104ProductionApproval:
    """
    LAISE T010.4 — Production Approval Registry + Final LIPP Manifest.

    This stage does NOT re-render audio.
    It consumes the already validated MUSIC-010 evidence and performs a
    governance-only promotion when BOTH are true:

      1. T010.3 objective governance gate = PASS / PRODUCTION_CANDIDATE
      2. Human perceptual review = PASS

    Result:
      - eligible assets are registered as PRODUCTION_APPROVED
      - MUSIC-010 is recorded internally as PRODUCTION_READY
      - a final LIPP-style provenance manifest is frozen

    Important:
      PRODUCTION_APPROVED is an internal LAISE governance status.
      It is not, by itself, a legal opinion or warranty of third-party rights.
    """

    def __init__(self, project_root: Path):
        self.root = Path(project_root).resolve()
        self.music_dir = self.root / "evidence" / "MUSIC-010"
        self.governance_dir = self.root / "governance"

        self.snapshot_path = (
            self.music_dir / "production_governance_snapshot.json"
        )
        self.generation_manifest_path = (
            self.music_dir / "generation_manifest.json"
        )
        self.attribution_path = (
            self.music_dir / "ATTRIBUTION.txt"
        )
        self.review_path = (
            self.governance_dir / "music010_perceptual_review.json"
        )
        self.license_policy_path = (
            self.governance_dir / "t0103_license_policy.json"
        )

        self.registry_path = (
            self.governance_dir / "production_asset_registry.json"
        )
        self.lipp_path = (
            self.music_dir / "LAISE_LIPP_FINAL_MANIFEST.json"
        )
        self.release_record_path = (
            self.music_dir / "PRODUCTION_RELEASE_RECORD.json"
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()

    @staticmethod
    def _canonical_json_hash(value: Any) -> str:
        raw = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _now_utc() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _required_files_exist(self) -> bool:
        return all(
            p.is_file()
            for p in (
                self.snapshot_path,
                self.generation_manifest_path,
                self.attribution_path,
                self.review_path,
                self.license_policy_path,
            )
        )

    def _validate(
        self,
        snapshot: dict,
        generation_manifest: dict,
        review: dict,
    ) -> dict[str, bool]:
        mix_path = Path(snapshot["mix"]["path"])
        if not mix_path.is_absolute():
            mix_path = self.root / mix_path

        promotions = snapshot.get("promotion_decisions", [])
        gov_checks = snapshot.get("checks", {})

        checks = {
            "required_evidence_files_exist":
                self._required_files_exist(),

            "t0103_release_is_production_candidate":
                snapshot.get("release_status") == "PRODUCTION_CANDIDATE",

            "t0103_all_objective_checks_pass":
                bool(gov_checks)
                and all(bool(v) for v in gov_checks.values()),

            "generation_manifest_objective_pass":
                generation_manifest.get("objective_result") == "PASS",

            "generation_manifest_release_candidate":
                generation_manifest.get("release_status")
                == "PRODUCTION_CANDIDATE",

            "human_perceptual_review_pass":
                review.get("overall_result") == "PASS"
                and review.get("t0103_result") == "PASS"
                and review.get("music010_result") == "PASS",

            "all_asset_promotions_eligible":
                bool(promotions)
                and all(
                    p.get("eligible") is True
                    and p.get("promoted_status") == "PRODUCTION_APPROVED"
                    for p in promotions
                ),

            "mix_exists":
                mix_path.is_file(),

            "mix_hash_matches_governance":
                mix_path.is_file()
                and self._sha256_file(mix_path)
                == snapshot["mix"]["sha256"],

            "attribution_exists":
                self.attribution_path.is_file(),

            "license_policy_exists":
                self.license_policy_path.is_file(),
        }
        return checks

    @staticmethod
    def _asset_bundle_digest(asset: dict) -> str:
        """
        Stable digest over the asset's frozen dependency closure.
        """
        deps = asset.get("dependencies", [])
        material = []
        for dep in sorted(
            deps,
            key=lambda x: x.get("path", "").lower()
        ):
            material.append(
                {
                    "path": dep.get("path"),
                    "sha256": dep.get("sha256"),
                    "size_bytes": dep.get("size_bytes"),
                }
            )

        if asset.get("code"):
            material.append(
                {
                    "path": asset["code"].get("path"),
                    "sha256": asset["code"].get("sha256"),
                    "size_bytes": asset["code"].get("size_bytes"),
                }
            )

        raw = json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _load_existing_registry(self) -> dict:
        if not self.registry_path.is_file():
            return {
                "schema_version": "LAISE-PRODUCTION-ASSET-REGISTRY-1.0",
                "registry_status": "ACTIVE",
                "assets": {},
                "history": [],
            }

        data = self._read_json(self.registry_path)
        data.setdefault("schema_version", "LAISE-PRODUCTION-ASSET-REGISTRY-1.0")
        data.setdefault("registry_status", "ACTIVE")
        data.setdefault("assets", {})
        data.setdefault("history", [])
        return data

    def _promote_assets(
        self,
        snapshot: dict,
        approval_time: str,
    ) -> dict:
        registry = self._load_existing_registry()

        decisions = {
            d["asset_id"]: d
            for d in snapshot["promotion_decisions"]
        }

        promoted_ids = []

        for asset in snapshot["assets"]:
            asset_id = asset["asset_id"]
            decision = decisions[asset_id]

            if not decision["eligible"]:
                raise RuntimeError(
                    f"Asset unexpectedly not eligible: {asset_id}"
                )

            policy = asset["policy"]

            record = {
                "asset_id": asset_id,
                "status": "PRODUCTION_APPROVED",
                "approved_at_utc": approval_time,
                "approval_basis": "T010.3_OBJECTIVE_PASS_PLUS_HUMAN_PERCEPTUAL_PASS",
                "asset_type": asset.get("asset_type"),
                "entrypoint": asset.get("entrypoint"),
                "role": asset.get("role"),
                "seed": asset.get("seed"),
                "license": {
                    "license_id": policy.get("license_id"),
                    "license_state": policy.get("license_state"),
                    "source_url": policy.get("source_url"),
                    "attribution_required":
                        policy.get("attribution_required"),
                    "notice": policy.get("notice"),
                },
                "dependency_closure_complete":
                    asset.get("dependency_closure_complete"),
                "bundle_sha256":
                    self._asset_bundle_digest(asset),
                "source_governance_work_id":
                    snapshot.get("work_id"),
            }

            registry["assets"][asset_id] = record
            promoted_ids.append(asset_id)

        registry["last_updated_utc"] = approval_time
        registry["history"].append(
            {
                "event": "PRODUCTION_APPROVAL",
                "work_id": snapshot.get("work_id"),
                "timestamp_utc": approval_time,
                "promoted_assets": promoted_ids,
                "source_snapshot":
                    str(self.snapshot_path),
            }
        )

        self.registry_path.write_text(
            json.dumps(
                registry,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return registry

    def finalize(self) -> ApprovalResult:
        self.governance_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self._required_files_exist():
            missing = [
                str(p)
                for p in (
                    self.snapshot_path,
                    self.generation_manifest_path,
                    self.attribution_path,
                    self.review_path,
                    self.license_policy_path,
                )
                if not p.is_file()
            ]
            raise FileNotFoundError(
                "Required T010.4 evidence missing:\n"
                + "\n".join(missing)
            )

        snapshot = self._read_json(self.snapshot_path)
        generation_manifest = self._read_json(
            self.generation_manifest_path
        )
        review = self._read_json(self.review_path)
        license_policy = self._read_json(
            self.license_policy_path
        )

        checks = self._validate(
            snapshot,
            generation_manifest,
            review,
        )

        if not all(checks.values()):
            return ApprovalResult(
                passed=False,
                checks=checks,
                registry_path=str(self.registry_path),
                lipp_path=str(self.lipp_path),
                release_record_path=str(self.release_record_path),
            )

        approval_time = self._now_utc()

        registry = self._promote_assets(
            snapshot,
            approval_time,
        )

        final_audio_path = Path(snapshot["mix"]["path"])
        if not final_audio_path.is_absolute():
            final_audio_path = self.root / final_audio_path

        evidence_hashes = {
            "final_audio": {
                "path": str(final_audio_path),
                "sha256": self._sha256_file(final_audio_path),
            },
            "production_governance_snapshot": {
                "path": str(self.snapshot_path),
                "sha256": self._sha256_file(self.snapshot_path),
            },
            "generation_manifest": {
                "path": str(self.generation_manifest_path),
                "sha256": self._sha256_file(
                    self.generation_manifest_path
                ),
            },
            "attribution": {
                "path": str(self.attribution_path),
                "sha256": self._sha256_file(self.attribution_path),
            },
            "license_policy": {
                "path": str(self.license_policy_path),
                "sha256": self._sha256_file(
                    self.license_policy_path
                ),
            },
            "perceptual_review": {
                "path": str(self.review_path),
                "sha256": self._sha256_file(self.review_path),
            },
            "production_asset_registry": {
                "path": str(self.registry_path),
                "sha256": self._sha256_file(self.registry_path),
            },
        }

        lipp = {
            "schema_version": "LAISE-LIPP-1.0",
            "work_id": "LAISE-MUSIC-010",
            "title": "LAISE Production Candidate 001",
            "lifecycle_state": "PRODUCTION_READY",
            "approval_time_utc": approval_time,

            "validation": {
                "t0103_objective": "PASS",
                "t0103_perceptual": "PASS",
                "music010_objective": "PASS",
                "music010_perceptual": "PASS",
                "production_approval": "PASS",
            },

            "creation_lineage": {
                "T006": "Musical Intelligence / Phrase Engine",
                "T007": "Harmonic & Emotional Narrative Engine",
                "T008": "Cinematic Orchestration & Mix Intelligence",
                "T009": "Instrument Realism & Articulation Intelligence",
                "T010": "Production Instrument Asset Pipeline",
                "T010.1": "SFZ Renderer + Asset Onboarding",
                "T010.2": "Full Orchestral Asset Migration",
                "T010.3": "Production Governance Closure",
                "T010.4": "Production Approval + Final LIPP",
            },

            "final_audio":
                evidence_hashes["final_audio"],

            "asset_registry": {
                "path": str(self.registry_path),
                "sha256":
                    evidence_hashes[
                        "production_asset_registry"
                    ]["sha256"],
                "approved_asset_ids":
                    sorted(registry["assets"].keys()),
            },

            "runtime_snapshot":
                snapshot.get("runtime_snapshot"),

            "engine_snapshot":
                snapshot.get("engine_snapshot"),

            "licenses":
                license_policy,

            "attribution":
                evidence_hashes["attribution"],

            "human_review":
                review,

            "evidence_hashes":
                evidence_hashes,

            "governance_snapshot_sha256":
                evidence_hashes[
                    "production_governance_snapshot"
                ]["sha256"],

            "provenance_chain_sha256":
                self._canonical_json_hash(
                    {
                        "final_audio":
                            evidence_hashes["final_audio"]["sha256"],
                        "snapshot":
                            evidence_hashes[
                                "production_governance_snapshot"
                            ]["sha256"],
                        "generation_manifest":
                            evidence_hashes[
                                "generation_manifest"
                            ]["sha256"],
                        "review":
                            evidence_hashes[
                                "perceptual_review"
                            ]["sha256"],
                        "registry":
                            evidence_hashes[
                                "production_asset_registry"
                            ]["sha256"],
                    }
                ),

            "governance_note": (
                "PRODUCTION_READY and PRODUCTION_APPROVED are internal "
                "LAISE governance states backed by the frozen evidence "
                "listed in this manifest. They do not replace legal review "
                "or constitute a warranty regarding third-party rights."
            ),
        }

        self.lipp_path.write_text(
            json.dumps(
                lipp,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        release_record = {
            "schema_version": "LAISE-RELEASE-RECORD-1.0",
            "work_id": "LAISE-MUSIC-010",
            "release_status": "PRODUCTION_READY",
            "approval_result": "PASS",
            "approved_at_utc": approval_time,
            "final_audio": {
                "path": str(final_audio_path),
                "sha256": evidence_hashes[
                    "final_audio"
                ]["sha256"],
            },
            "lipp_manifest": {
                "path": str(self.lipp_path),
                "sha256": self._sha256_file(self.lipp_path),
            },
            "production_asset_registry": {
                "path": str(self.registry_path),
                "sha256": self._sha256_file(self.registry_path),
            },
            "attribution": {
                "path": str(self.attribution_path),
                "sha256": self._sha256_file(self.attribution_path),
            },
            "checks": checks,
            "note": (
                "This record confirms successful completion of LAISE "
                "technical and perceptual production gates."
            ),
        }

        self.release_record_path.write_text(
            json.dumps(
                release_record,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return ApprovalResult(
            passed=True,
            checks=checks,
            registry_path=str(self.registry_path),
            lipp_path=str(self.lipp_path),
            release_record_path=str(self.release_record_path),
        )
