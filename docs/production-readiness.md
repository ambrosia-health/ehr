# Production-readiness backlog

The current release is synthetic-only. The managed Vercel site, Neon `main` branch, Modal `production` environment, and live pinned demo model do **not** close a real-world production gate. “P0” items are hard gates before any real patient, clinical, billing, or payment data enters the system. Completion requires linked evidence—contract, test report, runbook, configuration export, restore exercise—not a checkbox based on code review alone.

## P0 — before real data or a live integration

| ID | Owner | Outcome / acceptance evidence |
|---|---|---|
| P0-01 | Executive, legal, security | Approve data-flow inventory and vendors; execute required BAAs/DPAs with Vercel, Modal, Neon and every live subprocessor; document service/configuration eligibility for regulated data. |
| P0-02 | Privacy, product | Complete HIPAA/security risk analysis, data classification, minimum-necessary policy, retention/deletion/legal-hold schedule, patient rights workflows and jurisdiction review. |
| P0-03 | Security, platform | Perform threat model and independent penetration test covering tenant isolation, direct Modal access, sessions/CSRF/XSS, SSRF, uploads, webhooks, presenter endpoints and supply chain; close critical/high findings. |
| P0-04 | Identity/backend | Replace demo personas with production IdP/MFA, lifecycle provisioning/deprovisioning, short sessions/revocation, scoped proxy access and audited break-glass; exhaustive policy tests pass. |
| P0-05 | Backend/database | Prove tenant isolation across all CRUD/search/export/file/AI/worker paths with two-tenant tests; use least-privilege DB roles and decide/implement Postgres RLS defense in depth. |
| P0-06 | Platform | Create or formally re-provision isolated **real-data-approved** Vercel/Modal/Neon/Blob environments and accounts under the approved threat model/contracts; do not promote the current synthetic-demo resources by renaming them. Prove no production credentials/data can reach previews; enforce protected deployments, branch review, secret scanning and credential rotation. |
| P0-07 | Database | Validate migrations on a production-scale clone, pooled/direct connection strategy, constraints and zero/controlled-downtime expand-contract deployment; document forward recovery. |
| P0-08 | Reliability/database | Configure encrypted backups/PITR and run a timed restore into isolation; prove RPO/RTO, integrity checks, ownership and quarterly exercise schedule. |
| P0-09 | Clinical/backend | Independently validate signed-note immutability, signature meaning, amendment/cosign workflows, author/time provenance and complete audit reconstruction with clinical/legal stakeholders. |
| P0-10 | Safety/AI | Establish model/vendor data-use terms, no-training/retention controls, clinical risk analysis, capability-specific evaluation sets, thresholds, human gates, monitoring, rollback and change control. |
| P0-11 | Security/files | Private object storage only for patient uploads; authorize every read, strip metadata, validate type/size/signature, malware scan/quarantine, reconcile orphan objects and test governed deletion. |
| P0-12 | Platform/observability | Deploy PHI-safe logs/metrics/traces with tested redaction, access control, retention and alerts; no request bodies/prompts/tokens; audit access is distinct and tamper-resistant. |
| P0-13 | Security/operations | Approve incident response and breach assessment/notification playbooks, on-call tree, evidence preservation and vendor escalation; complete tabletop exercise. |
| P0-14 | Product/QA | Remove or cryptographically/operationally disable presenter switching, reset, time travel and deterministic networks in normal production; negative tests prove endpoints are unreachable. |
| P0-15 | Integrations | For each live network, complete sandbox/certification, authenticated webhook/replay defense, idempotency, reconciliation, outage/backfill runbook, SLAs and clear UI source/status disclosure. |
| P0-16 | Clinical governance | Establish clinical safety owner, hazard log, change approval, content/coding review, result escalation/loss-to-follow-up policy and human accountability. |
| P0-17 | Finance/compliance | Validate estimates, coding, claim, denial, payment allocation, refund/credit-balance and financial reporting rules with qualified owners; preserve submitted/adjudicated history. |
| P0-18 | Release/QA | Full E2E, accessibility, performance, security and failure-injection suites pass in a production-like environment; release checklist and rollback/forward-recovery rehearsal complete. |

## P1 — before a controlled pilot

| ID | Owner | Outcome / acceptance evidence |
|---|---|---|
| P1-01 | Reliability | Set SLOs and alerts for API availability/latency, worker lag, stuck workflows, open pathology age, delivery failures, claim reconciliation, model fallback/error and database saturation. |
| P1-02 | Backend/workflows | Load/failure test durable jobs, leases, retries, dead-letter/reconciliation queues, duplicate and out-of-order callbacks, and deployment during in-flight work. |
| P1-03 | Platform/Modal | Measure cold starts and long inference/transcription behavior; bound HTTP work below platform limits, move long work to durable asynchronous status, size warm capacity by risk. |
| P1-04 | Database/analytics | Benchmark tenant-scoped query plans and dashboard windows with representative volume; add bounded pagination, statement timeouts and reviewed indexes. |
| P1-05 | Clinical/pathology | Pilot result matching, critical/abnormal escalation, covering-provider routing, patient notification proof and no-loss-to-follow-up reports with daily reconciliation. |
| P1-06 | Patient experience | Validate identity proofing, proxy/delegate/minor workflows, accessibility, language/reading level, communication consent/opt-out and urgent-symptom escalation. |
| P1-07 | RCM | Reconcile eligibility, clearinghouse acknowledgements, remits and deposits daily; establish payer-specific rule ownership and manual exception queues. |
| P1-08 | Support/operations | Create support access workflow with time-bound approval, screen/data redaction, ticket classification and auditable customer troubleshooting. |
| P1-09 | Security | Automate SAST/dependency/container/IaC/license scanning, signed build provenance, dependency update SLA and critical-CVE release policy. |
| P1-10 | Data governance | Build export/amendment/restriction/deletion workflows and verify downstream provider/file/backup implications against approved retention policy. |
| P1-11 | Interoperability | Select FHIR release/IG/terminology packages; publish capability/mapping/known-loss matrix and pass partner fixtures if interoperability is in pilot scope. |
| P1-12 | Release engineering | Use immutable artifacts, migration compatibility gates, canary/preview verification, Vercel promotion, Modal prior-version redeploy and environment-specific smoke tests. |

## P2 — scale and general availability

| ID | Owner | Outcome / acceptance evidence |
|---|---|---|
| P2-01 | Platform | Capacity and cost budgets by tenant/workload; autoscaling, abuse controls, noisy-neighbor testing and regional strategy. |
| P2-02 | Reliability | Multi-region/vendor outage strategy and full disaster-recovery exercise, including reconciliation of external side effects after restore. |
| P2-03 | Analytics | Versioned metric semantic layer, late-arriving event correction, data-quality monitors, finance reconciliation and tenant-level audit of reported values. |
| P2-04 | AI governance | Drift/bias/subgroup monitoring, blinded clinical review cadence, prompt/model registry promotion, shadow/canary evaluation and fast capability kill switches. |
| P2-05 | Accessibility/product | Independent WCAG 2.2 AA audit across patient mobile and dense desktop workflows; remediate keyboard, focus, zoom, contrast and assistive-technology findings. |
| P2-06 | Security/privacy | Formal access recertification, vendor reviews, key rotation, audit sampling, vulnerability disclosure and annual independent assessments. |
| P2-07 | Operations | Customer onboarding/offboarding, tenant configuration change control, data migration validation, training, status communications and SLA reporting. |
| P2-08 | Clinical quality | Ongoing safety case with near-miss reporting, result/communication/medication audits and measured automation overrides. |

## Release evidence register

Track each gate in the delivery system with:

- accountable owner and approver;
- affected environment/version;
- acceptance artifact and immutable link;
- test/exercise date and expiry/retest cadence;
- residual risk and signed acceptance where applicable;
- rollback/kill-switch location.

Minimum go/no-go review: product, clinical safety, privacy, security, engineering, operations, revenue-cycle/integration owners, and executive risk owner. No single team can self-certify the platform for live healthcare use.

## Known demo-to-production substitutions

| Demo component | Production substitution/gate |
|---|---|
| Pre-seeded signed persona session | production IdP, MFA, identity proofing, provisioning, scoped role/delegate policy |
| Presenter role switch/reset/time advance | disabled/unroutable in production; controlled admin tooling built separately if needed |
| Deterministic AI fallback fixtures | retained only as test fixtures; production failure yields safe queue/manual workflow, never fabricated patient output |
| Pinned `Qwen/Qwen2.5-0.5B-Instruct` demo inference on Modal T4 with schema/semantic validation | capability-specific clinical evaluation and risk thresholds; approved model/vendor terms, retention/training controls, minimum-necessary transport, monitoring/drift/change control, human-factors validation, and a safe manual outage path; exact provider/model labels remain mandatory |
| Simulated eligibility/claims/remit/SMS/eRx/pathology/payment | certified live adapter plus authenticated callbacks, reconciliation, monitoring and contracts |
| Canonical public synthetic assets | private authorized patient file pipeline with scanning, consent, retention and deletion |
| SQLite/Docker local stores and current synthetic Neon `main`/`staging`/`preview` branches | real-data-approved Neon account/project with least privilege, pooling, PITR, tested restore, residency/retention controls and migration governance |
| Demo MSO assumptions | governed metric definitions reconciled to operational/financial source systems |
