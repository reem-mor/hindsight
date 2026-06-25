# SEV1 — Brute-force SSH intrusion against bastion

| Field | Value |
|---|---|
| Classification | intrusion |
| Department | Identity-Sec |
| Sensitivity | confidential |
| Routing tag | escalate |
| CVSS | 7.2 |
| CVEs | n/a |

## Summary
SIEM detected 412 failed SSH logins then a successful auth from a new ASN on the bastion host.

## Action items
P0: Block source ASN + enforce MFA (SecOps)
