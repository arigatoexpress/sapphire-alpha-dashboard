---
title: Sapphire Security Digest — 2026-07-29
description: >
  Weekly Sapphire security digest — 5 actively-exploited CVEs (all CISA KEV,
  average CVSS 9.7). Two past CISA remediation deadline. Sourced from CISA KEV
  and NVD; informational only.
date: 2026-07-29
tags: [security, cve, threat-intel, kev]
publish: true
---

## Executive Summary

5 of 24 prioritized CVEs surfaced this cycle. All 5 are actively exploited (CISA KEV). Average CVSS 9.7. 2 past CISA remediation deadline.

_Threat pack is 0.3 day old._

## Top Priority CVEs

### CVE-2026-16812 — Arista VeloCloud Orchestrator — On-Prem OS Command Injection Vulnerability
_CVSS 10.0 · CISA KEV · priority 12.52_

VeloCloud Orchestrator (VCO) on-prem has a security issue where this issue may allow a remote attacker to access privileged internal functionality and impact the VCO host. Successful exploitation may compromise the confidentiality, integrity, and availability of the orchestrator and data managed by the orchestrator. This functionality was intended to be for internal use only and is not intended to be remotely accessible. Hosted and Dedicated versions of VCO have already been patched in advance of this notice going out. This issue was discovered externally and is known to be actively exploited.

_latest evidence 2026-07-27T22:17:03Z · via cisa-kev, nvd._

### CVE-2026-63030 — WordPress Core — Interpretation Conflict Vulnerability
_CVSS 9.8 · CISA KEV · priority 11.69_

WordPress Core contains an interpretation conflict vulnerability that could allow an attacker to perform SQL Injection and achieve Remote Code Execution. This vulnerability can be chained with CVE-2026-60137. CISA remediation due date: 2026-07-24. Known ransomware campaign use: Unknown.

_CISA remediation due **2026-07-24** · latest evidence 2026-07-21T06:00:00Z · via cisa-kev, nvd._

### CVE-2026-0770 — Langflow Langflow: Langflow Inclusion of Functionality from Untrusted Control Sphere Vulnerability
_CVSS 9.8 · CISA KEV · priority 11.69_

Langflow exec_globals Inclusion of Functionality from Untrusted Control Sphere Remote Code Execution Vulnerability. This vulnerability allows remote attackers to execute arbitrary code on affected installations of Langflow. Authentication is not required to exploit this vulnerability. The specific flaw exists within the handling of the exec_globals parameter provided to the validate endpoint. The issue results from the inclusion of a resource from an untrusted control sphere. An attacker can leverage this vulnerability to execute code in the context of root. Was ZDI-CAN-27325.

_latest evidence 2026-07-21T06:00:00Z · via cisa-kev, nvd._

### CVE-2026-50522 — Microsoft SharePoint — Deserialization of Untrusted Data Vulnerability
_CVSS 9.8 · CISA KEV · priority 10.52_

Microsoft SharePoint contains a deserialization of untrusted data vulnerability which could allow an unauthorized attacker to execute code over a network. CISA remediation due date: 2026-07-25. Known ransomware campaign use: Unknown.

_CISA remediation due **2026-07-25** · latest evidence 2026-07-22T06:00:00Z · via cisa-kev, nvd._

### CVE-2026-16232 — Check Point SmartConsole — Improper Authentication Vulnerability
_CVSS 9.1 · CISA KEV · priority 10.37_

An authentication bypass vulnerability in the Check Point SmartConsole login process allows an unauthenticated remote attacker to obtain an application login token and use it to authenticate with full administrative privileges. Successful exploitation allows the attacker to modify security policies and security configurations. Remote exploitation requires internet access to the Management Server IP address and a configuration that does not restrict Trusted Clients. Check Point is aware that this vulnerability is being exploited and has affected a very small number of customers.

_latest evidence 2026-07-22T20:17:15Z · via cisa-kev, nvd._

## Mitigation Priorities

1. Confirm each KEV-listed CVE against your asset inventory before the CISA deadline; missed deadlines are the fingerprint most commonly cited in incident reviews.
2. Where multiple CVEs share a vendor, treat them as one patch window — do not ship staged partial fixes that leave a known-exploited variant live.
3. For network-edge devices (Fortinet, SonicWall, F5, Ivanti), verify management interfaces are not internet-exposed even after patching; edge-device compromise is still the top public-sector initial-access vector.
