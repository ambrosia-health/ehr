# Data safety, security, and clinical integrity

## Safety boundary

This repository is a synthetic-data demonstration. It is **not authorized for real patient data, clinical care, claims transmission, payment collection, or production messaging**. A polished demo, encryption by a cloud vendor, or passing tests does not establish HIPAA compliance, a BAA, clinical validation, or production readiness. The release gates in [`production-readiness.md`](./production-readiness.md) must be closed before any live-data use.

That warning applies equally to the live managed site, its Vercel `Production` alias, the Neon `main` branch, and the Modal `main` environment. Those labels describe a synthetic-demo delivery topology; they are not compliance, privacy, clinical-safety, or real-data approvals.

All canonical people, photographs, coverage, pathology, claims, messages, and financial events must be generated or explicitly licensed synthetic fixtures. Do not paste real patient content into the UI, seed, logs, issue tracker, model provider, screenshots, or support channels.

## Trust boundaries and principal threats

| Boundary | Primary threats | Required controls |
|---|---|---|
| Browser ↔ Vercel | session theft, CSRF, XSS, cached clinical data, role tampering | secure HttpOnly SameSite cookies, CSRF/origin defense, CSP, output encoding, private/no-store responses, no secrets/local-storage tokens |
| Vercel ↔ Modal | direct endpoint bypass, forged identity/tenant, replay, request smuggling | Current demo: Modal validates signed session and membership, emits request IDs/no-store headers, and uses TLS. Production gate: replace or constrain the rewrite with explicit header forwarding, body/time limits, replay controls, and optional service authentication. |
| Modal ↔ Neon | leaked credentials, cross-tenant queries, excessive privileges, injection | scoped/rotated TLS credentials, parameterized SQL/ORM, tenant-required repositories, constraints, least privilege, audit, separate migration role |
| Files | public patient image, malicious upload, orphaned object, metadata leakage | private objects, authorization before signed URL, MIME/signature/size checks, checksum, malware pipeline before live use, lifecycle reconciliation |
| AI/model | prompt injection, hallucinated facts/codes, over-broad context, data retention | minimum necessary context, allowlisted retrieval, structured schemas, policy validation, proposal-only actions, human review, timeout/fallback, vendor governance |
| Provider/webhooks | forged result/remit, duplicates, out-of-order events | signature/mTLS as supported, replay window, external event uniqueness, reconciliation, quarantine, append-only attempt history |
| Demo controls | reset of wrong tenant, unauthorized persona switch, fake time escaping demo | synthetic-environment guard, presenter authorization, tenant-scoped reset, confirmation/idempotency, audit, controls absent in normal mode |
| Operators/CI | exposed secrets, unsafe preview, dependency compromise | Current demo: managed Vercel/Modal/Neon resources, native Git previews without a repository Vercel token, named GitHub environments, platform secret stores, frozen migration checks, exact model/lockfile/tool versions, and post-deploy API/model attestation. Production gate: enforce reviewers and branch controls, pin Actions by reviewed commit SHA, add secret/dependency/IaC scanning and signed provenance, and independently audit platform configuration. |

## Authorization model

Authorization is evaluated by Modal on the current user, active membership, organization, role/capability, target resource organization, record state, and requested action. Frontend visibility is usability—not a control.

| Capability | Patient | Clinical staff | Provider | Biller | MSO owner | Presenter-only |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Read own portal chart/messages/balance | ✓ | — | — | — | — | — |
| Read assigned/authorized patient records | — | ✓ | ✓ | limited minimum | aggregate/authorized | — |
| Edit intake/draft demographics | own | ✓ | ✓ | limited coverage | — | — |
| Draft encounter content | — | scoped | ✓ | — | — | — |
| Sign/amend clinical note | — | policy-specific | ✓ | — | — | — |
| Review pathology / approve patient result message | — | routed tasks | ✓ | — | — | — |
| Validate/submit/correct claims | — | — | supporting facts | ✓ | oversight | — |
| View cross-practice analytics | — | limited | limited | financial scope | ✓ | — |
| Switch persona / reset / advance time / trigger simulator | — | — | — | — | — | ✓ |

The table is policy intent and requires executable authorization tests. “MSO owner” is not an automatic right to open every clinical note: use minimum necessary access and audited break-glass where business/legal policy permits. Patient proxy/delegate access needs its own explicit relationship and scope. The aggregate `/api/demo/bootstrap` response is subject to the same server-side role and patient scope; a convenient read model must not disclose every module to every persona.

Presenter capability is an orthogonal, temporary delegation—not the `mso_owner` role. A normal Alex Morgan owner login receives ordinary owner permissions and no reset, time-travel, trigger, health, or persona-switch authority. Supplying the presenter code causes Modal to issue a signed session containing a same-tenant presenter actor. Switching the viewed persona changes the session subject while retaining that accountable actor; each request revalidates that the actor remains active, same-tenant, and presenter-capable. Frontend state alone cannot activate presenter authority.

## Record integrity

- Draft edits create traceable versions. Signing binds one immutable version to signer, role, timestamp, and content hash.
- Signed content cannot be updated in place. Corrections create an append-only amendment with reason and signature; the original remains reconstructable.
- AI output is visibly proposed. Approval targets an exact proposal and chart version; stale approvals fail.
- Pathology review, patient notification, orders, procedures, claim submission, appeals, and outbound clinical messages write actor/time/source/state events.
- Audit events record access and change metadata without duplicating sensitive bodies. Application users cannot alter or delete them.
- Any administrative correction uses a narrow, reasoned, audited workflow; database-console editing is not an operating procedure.

## AI safety policy

| AI capability | Allowed output | Required before effect |
|---|---|---|
| `chart_summary` | attributed draft summary | clinician verifies against chart before clinical reliance |
| `ambient_note` | structured draft sections | clinician edits/reviews and signs exact version |
| `coding_suggestions` | diagnosis/procedure suggestions with evidence | provider confirms clinical facts; biller validates claim rules |
| `patient_message` | draft grounded in approved content | staff/provider approval unless narrowly approved low-risk template policy |
| `pathology_summary` | draft clinician/patient summaries | clinician reviews original result and approves communication/follow-up |
| `denial_recommendation` | classified rationale and draft appeal | biller validates payer facts, evidence, and submission |
| `document_extraction` | structured proposed facts with source locations | schema/rule checks and human reconciliation for consequential data |

Models never diagnose autonomously, silently change signed records, place/send orders, transmit prescriptions, release pathology, submit claims/appeals, or contact a patient solely because generated text appears plausible. UI must show source links, uncertainty/fallback, edits, approval state, and responsible human.

Prompt injection defenses treat all patient messages, documents, payer responses, and result text as untrusted data. Retrieval cannot grant tools or broaden tenant scope. Tool calls are allowlisted typed commands re-authorized after generation. System prompts and secrets never enter model-visible chart context.

## Session and web controls

- Use a high-entropy session secret per environment; rotate with an overlap strategy. Cookies are `HttpOnly`, `Secure` outside localhost, `SameSite=Lax` or stricter, narrowly scoped, and short-lived with server-side revocation where production requires it.
- Protect mutations against cross-site requests with same-origin checks and/or CSRF tokens. Restrict CORS to exact trusted origins; wildcard origin with credentials is forbidden.
- Set CSP, HSTS in hosted environments, `frame-ancestors`, `nosniff`, restrictive referrer policy, and permissions policy. Avoid inline script exemptions.
- Do not put patient identifiers/content in URLs, analytics events, browser storage, error trackers, React Query persistence, or cache keys visible to third parties.
- API response caching defaults to `Cache-Control: private, no-store`; Next.js patient/financial fetches opt out of static/shared caching explicitly.
- Rate-limit authentication, search, uploads, AI generation, messages, and presenter triggers by user/tenant/source with auditable failures.

## Database and tenant controls

- Each tenant-owned query receives `organization_id` from verified session context and applies it before resource ID. Tests create identical-looking IDs/data across two tenants and assert non-disclosure for list, get, mutation, search, export, file, AI and background paths.
- Use separate least-privilege application, migration, and read-only analytics roles. Do not give the web deployment a Neon credential.
- Require TLS to Neon. Keep pooled application and direct migration URLs distinct and only in server/secret stores.
- Backups, branches, logs, support exports, and preview databases inherit the same classification. Preview must never use production data.
- Durable workers lock/lease jobs in Postgres, bound retries, preserve attempt history, and make side effects idempotent.
- Before live use, evaluate database row-level security as defense in depth, backup/PITR restore, regional/residency requirements, retention/legal hold, encryption key governance, and audited privileged access.

## File and photograph controls

1. Client requests upload authorization for an authorized patient/encounter/lesion and declared content constraints.
2. Server creates a pending `file_record`; provider/object key is opaque and tenant-bound.
3. Upload uses short-lived limited authorization. Completion verifies size, content signature/MIME, checksum and ownership.
4. File remains quarantined until required scanning/validation completes. Demo fixtures may be trusted only by recorded seed provenance.
5. Reads re-authorize the current user and return a short-lived URL/stream with private/no-store headers.
6. Deletion is a governed lifecycle with database/object reconciliation; audit and clinical provenance remain even when retention policy removes bytes.

Strip unnecessary EXIF/GPS/device metadata. Never use scraped dermatology photographs. Consent and use restrictions travel with the image record and downstream AI/export jobs.

## Logging, audit, and observability

Allowed operational fields include timestamp, environment, service, route template, status, latency, request ID, tenant/user pseudonymous IDs, job type/status, and bounded error code. Default-deny request/response bodies, query strings, cookies, authorization headers, note/message/result text, filenames, object URLs, model prompts/context/output, payer payloads, and SQL parameters.

Structured redaction occurs before logs leave the process. Error trackers disable sensitive replay and scrub breadcrumbs. Traces carry opaque resource IDs only when access is controlled. Production access to logs is role-limited, time-bounded, reviewed, and auditable.

Audit answers: who, in which tenant/role, did what, to which resource, when, from which request/source, with what outcome/reason. Audit is not the same as debug logging and must survive ordinary record lifecycle operations.

## Secrets and environment separation

- `.env` is local only. GitHub Actions environment secrets authenticate Modal deployment/migration; versioned host rules configure the Vercel server-side rewrite without runtime variables; Modal Secrets hold runtime database/model/provider credentials. Native Vercel Git previews do not require `VERCEL_TOKEN` in GitHub.
- The current synthetic demo separates Neon branches, Modal environments, Vercel environments, session keys, and model-provider credentials. A real-data deployment must establish the stronger account/project/database/role isolation selected by the approved threat model and vendor agreements.
- Keep `AUTH_SESSION_SECRET` (user-session signatures), `DEMO_PRESENTER_SECRET` (demo delegation), and `OPENAI_API_KEY` (model-provider access) distinct; compromise or rotation of one must not silently grant the others.
- Do not expose server secrets under `NEXT_PUBLIC_*`. `AMBROSIA_API_ORIGIN` is a server-only local/operator override, not a managed Vercel variable.
- Rotate any credential printed to a terminal, pasted into chat/issues, committed, embedded in an artifact, or exposed to an untrusted preview. Purge history/artifacts after rotation as applicable.
- Preview environments are synthetic-only, expire when practical, and cannot reach production providers.

[`../scripts/provision-managed-infra.sh`](../scripts/provision-managed-infra.sh) is the controlled reconciliation path. It intentionally rotates session and presenter credentials while synchronizing the OpenAI key from protected operator input into GitHub and Modal secret stores, then fails unless both Modal environments prove API/database health and the exact OpenAI model contract. Do not copy its resolved credentials into tickets, logs, local `.env` files, or browser configuration.

## Verification checklist

Before every demo release:

- Scan seed/assets and Git history for possible real identifiers or images; confirm synthetic provenance.
- Run cross-tenant authorization, signed-note immutability, stale approval, idempotency, reset guard, file authorization, cache-header and provider-replay tests.
- Confirm persona switching and timeline triggers require presenter mode and are audited.
- Inspect browser network/storage and Vercel/Modal logs for leaked data or secrets.
- Verify direct calls to the Modal URL fail without a valid session and unauthorized roles receive indistinguishable not-found/forbidden behavior per policy.
- Confirm AI outage/timeout selects a labeled deterministic fallback and cannot bypass review.
- Confirm open pathology and failed delivery/claim events remain in accountable queues.

If any real patient data is suspected: stop the affected service/workflow, preserve minimal evidence, revoke exposed credentials/links, notify the designated security/privacy owner, scope systems and recipients, and follow the approved incident/breach procedure. Do not investigate by copying the data into new tools.
