# Standards crosswalk

How the session's levels, findings and scenarios map to frameworks a security team already uses.

> **Maps to, not compliant with.** Nothing here is certified. The mapping is the author's judgement; every ID was checked against its source on 2026-09-26. ATT&CK v19 (Apr 28, 2026) split Defense Evasion into Stealth (TA0005) and Defense Impairment (TA0112) and revoked T1562 Impair Defenses into T1685 Disable or Modify Tools; older material citing T1562.001 means T1685. NIST's AI-agent work (CAISI, NCCoE, COSAiS overlays) is in progress and cited as direction, not requirements.

Edit `crosswalk.yaml`, then `python3 standards/render.py`.

## Quarantine Mode as NIST SP 800-61 Rev. 3 (CSF 2.0 Respond)

| Level | CSF 2.0 subcategories | MITRE D3FEND | Why |
|---|---|---|---|
| **Q0 Normal** | **PR.PS-01** Configuration management practices are established and applied<br>**PR.AA-05** Access permissions, entitlements, and authorizations are defined in a policy, managed, enforced, and reviewed, and incorporate the principles of least privilege and separation of duties | Harden: Platform Hardening (D3-PH) | The guardrails themselves: policy-as-code admission, least-privilege identities. |
| **Q1 Freeze** | **RS.MA-02** Incident reports are triaged and validated<br>**RS.MA-04** Incidents are escalated or elevated as needed<br>**PR.PS-01** Configuration management practices are established and applied | — | Change freeze: no new exceptions, and no changes by agent identities (enforced at admission), while the alert is triaged. D3FEND has no direct analog; it models countermeasures against the attacker, not a freeze on your own automation. |
| **Q2 Constrain** | **RS.AN-07** Incident data and metadata are collected, and their integrity and provenance are preserved<br>**RS.MI-01** Incidents are contained<br>**RS.MA-04** Incidents are escalated or elevated as needed | Isolate: Network Isolation (D3-NI)<br>Isolate: DNS Allowlisting (D3-DNSAL; partial: DNS-only egress, tunnelling over DNS still open at Q2)<br>Isolate: Executable Allowlisting (D3-EAL)<br>Harden: Credential Rotation (D3-CRO) | Evidence first (RS.AN-07), then contain (RS.MI-01): suspect DNS-only and out of Service rotation; approved images only. |
| **Q3 Isolate** | **RS.MI-01** Incidents are contained<br>**RS.MA-04** Incidents are escalated or elevated as needed<br>**PR.AA-05** Access permissions, entitlements, and authorizations are defined in a policy, managed, enforced, and reviewed, and incorporate the principles of least privilege and separation of duties | Isolate: Network Isolation (D3-NI)<br>Evict: Credential Revocation (D3-CR) | Deliberately isolate, not evict: Process Termination (D3-PT) would destroy the evidence. Override needs the IC's identity (PR.AA-05). |
| **exit Staged descent** | **RS.MA-05** The criteria for initiating incident recovery are applied<br>**RS.AN-06** Actions performed during an investigation are recorded, and the records' integrity and provenance are preserved | Restore | Exit criteria per level; every declaration and lift recorded (RS.AN-06). |

## The four lab findings

| Finding | MITRE ATT&CK v19 | MITRE D3FEND | CSF 2.0 | OWASP Agentic | Lesson |
|---|---|---|---|---|---|
| **Q3's deny-all left DNS open** | T1071.004 Application Layer Protocol: DNS | Isolate: Network Isolation (D3-NI)<br>Isolate: DNS Allowlisting (D3-DNSAL; partial: DNS-only egress, tunnelling over DNS still open at Q2) | RS.MI-01 | — | Containment you haven't tested as a union of policies isn't containment. |
| **Evicting suspects under Q3 deadlocks** | — | Evict vs Isolate: Process Termination (D3-PT) destroys evidence | RS.AN-07<br>RS.MI-01 | — | D3FEND lists Evict as a tactic; under a containment freeze it destroys evidence and can deadlock against the PDB. |
| **kubectl debug went around Q2** | T1609 Container Administration Command | Isolate: Executable Allowlisting (D3-EAL) | PR.PS-01 | — | An image allowlist must cover every API path that can start code, pods/ephemeralcontainers included. |
| **The agent's ServiceAccount could scale the policy engine to zero** | T1685 Disable or Modify Tools (Defense Impairment, TA0112; was T1562.001 before v19) | Harden: Platform Hardening (D3-PH) | PR.AA-05 | ASI03 Identity and Privilege Abuse | Who can scale your policy engine to zero is a least-privilege question (PR.AA-05) before it is a policy question. |
| **The agent's privilege policy missed host mounts** | T1610 Deploy Container<br>T1611 Escape to Host | Harden: Platform Hardening (D3-PH) | PR.PS-01 | — | hostPath and hostNetwork are in the Pod Security Standards Baseline; the tests passed because no fixture tried them. The July 2026 incident's missing control. |

## The three scenarios

| Scenario | MITRE ATT&CK v19 | OWASP Agentic Top 10 (2026) | MITRE ATLAS |
|---|---|---|---|
| **A · The quiet library** | T1195.001 Compromise Software Dependencies and Development Tools<br>T1610 Deploy Container (D2)<br>T1611 Escape to Host (D2) | — | — |
| **B · The obedient assistant** | T1528 Steal Application Access Token | ASI01 Agent Goal Hijack<br>ASI02 Tool Misuse and Exploitation | AML.T0051.001 LLM Prompt Injection: Indirect |
| **C · The helpful ops agent** | T1098 Account Manipulation<br>T1496 Resource Hijacking | ASI01 Agent Goal Hijack<br>ASI03 Identity and Privilege Abuse<br>ASI09 Human-Agent Trust Exploitation | — |

The July 2026 anchor incident (host-mounted Pod no admission policy refused): T1610 Deploy Container, T1611 Escape to Host.

## Sources

- [NIST SP 800-61 Rev. 3, Incident Response Recommendations and Considerations for Cybersecurity Risk Management: A CSF 2.0 Community Profile](https://csrc.nist.gov/pubs/sp/800/61/r3/final) (2025-04)
- [NIST Cybersecurity Framework (CSF) 2.0](https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf) (2024-02)
- [MITRE ATT&CK v19 (Enterprise, incl. the Containers matrix)](https://attack.mitre.org/resources/updates/updates-april-2026/) (2026-04-28)
- [MITRE D3FEND (tactics: Model, Harden, Detect, Isolate, Deceive, Evict, Restore)](https://d3fend.mitre.org/) (current)
- [MITRE ATLAS](https://atlas.mitre.org/) (current)
- [OWASP Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/) (2025-12-09)
- [NCCoE concept paper: Accelerating the Adoption of Software and AI Agent Identity and Authorization (comment period closed)](https://csrc.nist.gov/pubs/other/2026/02/05/accelerating-the-adoption-of-software-and-ai-agent/ipd) (2026-02-05)
- [NIST CAISI AI Agent Standards Initiative (via CSA research note); COSAiS SP 800-53 overlays for agent systems in development](https://labs.cloudsecurityalliance.org/research/csa-research-note-nist-ai-agent-standards-initiative-2026040/) (2026-02-17)
- [Kubernetes Pod Security Standards (Baseline, Restricted)](https://kubernetes.io/docs/concepts/security/pod-security-standards/) (current)
- [Kubernetes SIG Security: Admission Control Threat Model](https://github.com/kubernetes/sig-security/blob/main/sig-security-docs/papers/admission-control/kubernetes-admission-control-threat-model.md) (2022)
- [Kubernetes v1.36: manifest-based admission policies that can't be deleted through the API](https://kubernetes.io/blog/2026/05/04/kubernetes-v1-36-manifest-based-admission-control/) (2026-05-04)
