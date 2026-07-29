---
title: Sapphire Security Digest — 2026-07-29
description: >
  Weekly Sapphire security digest — 5 actively exploited CVEs from CISA KEV.
  As of 2026-07-29, four of five were past their CISA remediation dates.
  Authoritative CISA and NVD records are linked; informational only.
date: 2026-07-29
tags: [security, cve, threat-intel, kev]
publish: true
sources:
  - label: CISA Known Exploited Vulnerabilities catalog
    url: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
  - label: NIST National Vulnerability Database
    url: https://nvd.nist.gov/vuln/
provenance:
  as_of: "2026-07-29"
  retrieved_at: "2026-07-29T16:10:52Z"
  cisa_kev_catalog_version: "2026.07.27"
  cisa_kev_feed_sha256: "e0326281b91c4f9a5be6bc01b0d0edbbfa933643bc96e5382cd1081b16d8170a"
  records:
    - cve: CVE-2026-16812
      due_date: "2026-07-30"
    - cve: CVE-2026-63030
      due_date: "2026-07-24"
    - cve: CVE-2026-0770
      due_date: "2026-07-24"
    - cve: CVE-2026-50522
      due_date: "2026-07-25"
    - cve: CVE-2026-16232
      due_date: "2026-07-25"
---

## Executive Summary

This digest covers five CVEs. All five appear in CISA's Known Exploited Vulnerabilities catalog. As of 2026-07-29, **4 of 5 were past their CISA remediation dates**.

## Source and Retrieval

The five records and every due date below were retrieved at **2026-07-29T16:10:52Z** from the [CISA Known Exploited Vulnerabilities JSON feed](https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json), catalog version `2026.07.27`, feed SHA-256 `e0326281b91c4f9a5be6bc01b0d0edbbfa933643bc96e5382cd1081b16d8170a`. The overdue count treats a due date strictly earlier than the report date, 2026-07-29, as past. CVE descriptions and scoring context link to the [NIST National Vulnerability Database](https://nvd.nist.gov/vuln/).

## Top Priority CVEs

### [CVE-2026-16812](https://nvd.nist.gov/vuln/detail/CVE-2026-16812) — Arista VeloCloud Orchestrator — On-Prem OS Command Injection Vulnerability
_CVSS 10.0 · CISA KEV · priority 12.52_

VeloCloud Orchestrator (VCO) on-prem has a security issue where this issue may allow a remote attacker to access privileged internal functionality and impact the VCO host. Successful exploitation may compromise the confidentiality, integrity, and availability of the orchestrator and data managed by the orchestrator. This functionality was intended to be for internal use only and is not intended to be remotely accessible. Hosted and Dedicated versions of VCO have already been patched in advance of this notice going out. This issue was discovered externally and is known to be actively exploited.

_CISA remediation due **2026-07-30** · CISA date added 2026-07-27 · [CISA KEV record](https://www.cisa.gov/known-exploited-vulnerabilities-catalog?field_cve=CVE-2026-16812) · [NVD record](https://nvd.nist.gov/vuln/detail/CVE-2026-16812)._

### [CVE-2026-63030](https://nvd.nist.gov/vuln/detail/CVE-2026-63030) — WordPress Core — Interpretation Conflict Vulnerability
_CVSS 9.8 · CISA KEV · priority 11.69_

WordPress Core contains an interpretation conflict vulnerability that could allow an attacker to perform SQL Injection and achieve Remote Code Execution. This vulnerability can be chained with CVE-2026-60137. CISA remediation due date: 2026-07-24. Known ransomware campaign use: Unknown.

_CISA remediation due **2026-07-24** · CISA date added 2026-07-21 · [CISA KEV record](https://www.cisa.gov/known-exploited-vulnerabilities-catalog?field_cve=CVE-2026-63030) · [NVD record](https://nvd.nist.gov/vuln/detail/CVE-2026-63030)._

### [CVE-2026-0770](https://nvd.nist.gov/vuln/detail/CVE-2026-0770) — Langflow Langflow: Langflow Inclusion of Functionality from Untrusted Control Sphere Vulnerability
_CVSS 9.8 · CISA KEV · priority 11.69_

Langflow exec_globals Inclusion of Functionality from Untrusted Control Sphere Remote Code Execution Vulnerability. This vulnerability allows remote attackers to execute arbitrary code on affected installations of Langflow. Authentication is not required to exploit this vulnerability. The specific flaw exists within the handling of the exec_globals parameter provided to the validate endpoint. The issue results from the inclusion of a resource from an untrusted control sphere. An attacker can leverage this vulnerability to execute code in the context of root. Was ZDI-CAN-27325.

_CISA remediation due **2026-07-24** · CISA date added 2026-07-21 · [CISA KEV record](https://www.cisa.gov/known-exploited-vulnerabilities-catalog?field_cve=CVE-2026-0770) · [NVD record](https://nvd.nist.gov/vuln/detail/CVE-2026-0770)._

### [CVE-2026-50522](https://nvd.nist.gov/vuln/detail/CVE-2026-50522) — Microsoft SharePoint — Deserialization of Untrusted Data Vulnerability
_CVSS 9.8 · CISA KEV · priority 10.52_

Microsoft SharePoint contains a deserialization of untrusted data vulnerability which could allow an unauthorized attacker to execute code over a network. CISA remediation due date: 2026-07-25. Known ransomware campaign use: Unknown.

_CISA remediation due **2026-07-25** · CISA date added 2026-07-22 · [CISA KEV record](https://www.cisa.gov/known-exploited-vulnerabilities-catalog?field_cve=CVE-2026-50522) · [NVD record](https://nvd.nist.gov/vuln/detail/CVE-2026-50522)._

### [CVE-2026-16232](https://nvd.nist.gov/vuln/detail/CVE-2026-16232) — Check Point SmartConsole — Improper Authentication Vulnerability
_CVSS 9.1 · CISA KEV · priority 10.37_

An authentication bypass vulnerability in the Check Point SmartConsole login process allows an unauthenticated remote attacker to obtain an application login token and use it to authenticate with full administrative privileges. Successful exploitation allows the attacker to modify security policies and security configurations. Remote exploitation requires internet access to the Management Server IP address and a configuration that does not restrict Trusted Clients. Check Point is aware that this vulnerability is being exploited and has affected a very small number of customers.

_CISA remediation due **2026-07-25** · CISA date added 2026-07-22 · [CISA KEV record](https://www.cisa.gov/known-exploited-vulnerabilities-catalog?field_cve=CVE-2026-16232) · [NVD record](https://nvd.nist.gov/vuln/detail/CVE-2026-16232)._

## Mitigation Priorities

1. Confirm each KEV-listed CVE against your asset inventory before its CISA due date. For entries already past due, prioritize validation and remediation according to applicable policy and asset exposure.
2. Where multiple CVEs share a vendor, treat them as one patch window — do not ship staged partial fixes that leave a known-exploited variant live.
3. For internet-facing infrastructure, verify management interfaces are not exposed unnecessarily, including after patching.
