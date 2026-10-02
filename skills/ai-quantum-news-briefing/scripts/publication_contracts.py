"""One version policy for generation, local verification and remote delivery.

Evidence versions are independent of the publication protocol. Historical
completed releases retain their original validation meaning; new releases and
first uploads must use the exact protocol/coverage pair.
"""
from __future__ import annotations


def coverage_contract_for_protocol(protocol: int) -> int:
    if type(protocol) is not int or protocol not in (1, 2, 3, 4):
        raise ValueError("unsupported publication protocol")
    return {1: 1, 2: 2, 3: 2, 4: 3}[protocol]


def coverage_contract_for_manifest(manifest: dict, *, for_upload: bool = False) -> int:
    if not isinstance(manifest, dict):
        raise ValueError("publication manifest must be an object")
    protocol = manifest.get("pipeline_version", 1)
    expected = coverage_contract_for_protocol(protocol)
    declared = manifest.get("coverage_evidence_contract_version")
    if for_upload:
        if protocol < 3 or type(declared) is not int or declared != expected:
            raise ValueError("First upload or correction requires content-bound daily coverage "
                             "evidence matching the publication protocol")
        return expected
    # Only known historical completed protocols may use legacy evidence. A v4
    # manifest cannot acquire legacy privileges merely by saying 'complete'.
    if protocol <= 3 and manifest.get("status") == "complete" and declared in (None, 1):
        if declared is not None and type(declared) is not int:
            raise ValueError("invalid coverage evidence contract")
        return 1
    if protocol == 1 and declared is None:
        return 1
    if declared is None:
        raise ValueError("new release lacks the current daily coverage evidence contract")
    if type(declared) is not int or declared != expected:
        raise ValueError("coverage evidence contract does not match the publication protocol")
    return expected
