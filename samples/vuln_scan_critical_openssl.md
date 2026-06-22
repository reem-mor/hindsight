# Vulnerability Scan Report — Critical RCE in payments estate

**Scan date:** 2026-06-18
**Status:** Ongoing (remediation in progress)
**Scanner:** Tenable Nessus (authenticated scan)
**Author:** SecOps vulnerability management

## Summary
An authenticated Nessus scan of the production payments estate flagged a critical remote
code execution vulnerability (CVE-2026-21841) in the TLS termination library used by the
payments gateway and wallet hosts. The flaw allows unauthenticated remote code execution
via a crafted handshake. 23 internet-exposed hosts are affected. No exploitation has been
observed, but the affected hosts process cardholder and customer funds data.

## Impact
- Affected services: payments gateway, wallet
- Affected jurisdictions: UKGC, NJ-DGE, MGM
- CVSS base score: 9.8 (Critical)
- CVE: CVE-2026-21841
- 23 internet-facing hosts vulnerable; PCI-scoped segment in scope

## Finding detail
- Vector: network, attack complexity low, no privileges required, no user interaction.
- The vulnerable library is statically linked into the gateway image, so an OS package
  update is insufficient — the gateway image must be rebuilt and redeployed.
- Detection: authenticated Nessus plugin 9xxxxx matched the linked library version.

## Action items
- [ ] Rebuild payments-gateway and wallet images against the patched library — owner: Payments-SRE — priority: P0
- [ ] Apply WAF virtual-patch / handshake filtering as interim mitigation — owner: SecOps — priority: P0
- [ ] Confirm no exploitation in SIEM handshake logs for the exposure window — owner: SecOps — priority: P1

## Notes
Reported to the compliance team given PCI and multi-jurisdiction exposure. Treat as
confidential until remediated. CVSS 9.8 — this should be triaged as a critical, paging event.
