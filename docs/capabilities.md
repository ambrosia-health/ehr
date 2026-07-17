# Live, functional, and simulated capabilities

“Live” is ambiguous in a healthcare demo. This matrix separates three facts:

- **Internal behavior**: whether Ambrosia must create/query durable domain records and enforce real workflow transitions.
- **External edge**: whether the demo talks to a real healthcare/financial network or an explicit deterministic adapter.
- **Production equivalence**: whether the component is suitable for live patients. Nothing in this repository is production-approved; see [`production-readiness.md`](./production-readiness.md).

The matrix is the acceptance contract, not proof by itself. A capability is demo-complete only after its evidence test passes in the integrated environment.

## Product and domain capabilities

| Capability | Demo internal behavior | Demo external edge | Required evidence |
|---|---|---|---|
| Authentication and role policy | Functional signed demo session; Modal authorization and role-scoped bootstrap/read models | Pre-seeded synthetic personas; no production IdP | role matrix, bootstrap field-scope and cross-tenant API tests; direct Modal rejection |
| Presenter persona switching | Functional signed delegation, separate from the owner role, protected and demo-mode-only | Synthetic personas | owner-without-code rejection; delegated actor continuity; normal-mode absence |
| Patient record and timeline | Durable normalized records | Synthetic seed | create/read/update across restart; tenant isolation |
| Patient initiation and scheduling | Functional questions, triage flags, slot selection and booking | Local availability rules | Sarah booking persists and appears on staff schedule |
| Structured intake | Functional normalized allergies, medications, problems, contacts, coverage, consents and images | Synthetic responses/assets | database/API assertions; not one opaque display blob |
| Eligibility | Functional request/result/benefit records and estimate input | **Deterministic payer simulator** | retry idempotency; request/response provenance |
| Patient estimate | Functional calculated, versioned estimate | Uses simulated benefits/fee assumptions | line totals and patient amount reconcile |
| Command center | Functional queries from current records | None | seeded queue counts equal source-record query results |
| AI pre-visit summary | Functional run/output/proposal/provenance | Authenticated pinned Qwen model on Modal when schema/semantics/provenance pass; deterministic fallback otherwise | hosted live-model attestation, timeout/invalid-output fallback test, honest run label and source attribution |
| Encounter state and ambient transcript | Durable encounter/transcript linkage and state | Transcript may be seeded; live speech engine not required | state transition and restart test |
| Structured note drafting | Versioned draft and AI proposal | Authenticated pinned Qwen model on Modal when validated; deterministic local/remote fallback otherwise | schema/semantic validation, fallback labeling, edit trail, approval visibility |
| Signed notes and amendments | Immutable signed snapshot; append-only amendment | None | mutation fails; original/hash/version chronology preserved |
| Body map and lesion timeline | Persistent lesion, coded body site, observations and comparisons | Synthetic image assets | same lesion spans encounters; ordered observation history |
| Biopsy review-and-complete | Atomic approved bundle creates note/procedure/specimen/order/claim/tasks/message/audit/provenance | Pathology transmission simulated | transaction rollback and command idempotency tests |
| Patient aftercare and messaging | Durable conversation, drafts, sent messages and delivery state | **Deterministic SMS/delivery simulator**; in-app UI functional | approved message grounding and uncertain-question routing |
| Pathology result workflow | Durable result chain, review, task, notification and closure | **Deterministic lab/pathology simulator** | duplicate result idempotency; overdue result remains queued |
| ePrescribing | Internal proposal/order contract where present | **Deterministic eRx simulator permitted** | must never imply a real prescription was transmitted |
| Claim construction and validation | Structured claim/lines/events from performed care | None until submission | diagnosis/procedure evidence and balanced totals |
| Clearinghouse lifecycle | Durable Draft → Validated → Submitted → Accepted events | **Deterministic clearinghouse simulator** | every transition sourced/timestamped; duplicate response safe |
| Adjudication/remittance | Durable response, adjustments, payments and balances | **Deterministic remittance simulator** | allocations reconcile to claim/line/balance |
| Denial and appeal | Durable classification, evidence, recommendation, work task, appeal/resubmission/recovery | **Deterministic payer/clearinghouse simulator** | original denial retained; recovered revenue traceable |
| Payment settlement | Durable payment/allocation/settlement states | **Deterministic payment simulator** | UI says simulated; ledger remains balanced |
| MSO analytics | Calculated from committed source records | None | metric formula fixtures and no hard-coded KPI values |
| Tasks, notifications and workflows | Postgres-backed reminders/tasks/workflow records; current poller delivers due reminders and escalates overdue tasks | Five-minute Modal schedule; deterministic messaging adapter | current poller test; generalized leasing/retry/dead-letter engine remains a pilot gate; no authoritative Modal Queue |
| Audit and provenance | Append-only actor/action/source/derivation records | None | critical-flow completeness and ordinary-user immutability |
| Demo reset and time advance | Tenant/scenario-scoped, deterministic, idempotent | Synthetic only | refusal outside synthetic guard; canonical checksum after reset |
| File metadata and canonical assets | Functional owned metadata, checksum/reference validation and clinical linkage | Bundled public canonical synthetic assets; private upload/read pipeline **not implemented** | wrong file/hash/cross-record link rejected; Vercel Blob authorization is a production gate |
| FHIR import/export | Adapter contract only | **Not connected** | version/profile selection and conformance suite are backlog |

## AI capability modes

Each named capability uses the same interface and validated output schema in both modes.

Managed staging and production use authenticated `MODAL_AI_URL` endpoints backed by `Qwen/Qwen2.5-0.5B-Instruct` on a Modal T4. Model weights are pinned to revision `7ae557604adf67be50417f59c2c2f167def9a775`; the deployment attestation rejects any different or missing model identity. A live response records provider `modal_open_weights`, the exact model revision and prompt hash, and `fallback_used=false` only after JSON-schema plus capability-specific semantic validation.

The model has no authority merely because it executed. Coding proposals cannot introduce codes absent from the conservative evidence set; pathology urgency cannot contradict the source result; patient drafts cannot cite unapproved instructions; uncertain messages must route to staff. Any cold start, timeout, exception, malformed JSON, schema violation, semantic violation, missing attestation, or revision mismatch returns the matching `ambrosia-fixture-2026.1` output, records `modal_deterministic_fallback`/`fallback_used=true`, and retains the same review requirement. Local zero-credential development uses this deterministic mode directly.

| Capability | Validated Modal model path | Deterministic resilience path | Human gate |
|---|---|---|---|
| `chart_summary` | minimum-necessary chart context → structured summary; deployment-attested capability | Sarah/fixture-keyed structured summary | clinician verifies before clinical reliance |
| `ambient_note` | transcript context → structured draft | transcript fixture → same schema | clinician edits and signs an exact version |
| `coding_suggestions` | chart evidence → allowlisted coded proposals | deterministic evidence-linked codes | provider confirms facts; biller approves claim use |
| `patient_message` | approved facts → grounded audience-appropriate draft | grounded template with uncertainty routing | staff/provider approval or narrow approved policy |
| `pathology_summary` | source result → clinician/patient drafts with invariant urgency | deterministic result fixture | clinician reviews original and approves release |
| `denial_recommendation` | denial and claim evidence → proposed correction/appeal | deterministic denial fixture | biller validates payer facts and approves submission |
| `document_extraction` | bounded document context → schema-validated proposed facts | deterministic fixture extraction | reconciliation for consequential facts |

Fallback is a resilience mode, not hidden fakery: the UI/`ai_run` identifies it, preserves the capability/schema/prompt version, and follows the same proposal/approval/audit path. A live, cold, failed, or slow model therefore cannot break the demo or gain authority. This hosted model path is demo evidence, not clinical validation or approval for real patient data.

## External adapter contract

Every simulator implements the same boundary expected of a future live adapter:

1. receive a typed request and tenant-scoped idempotency key;
2. persist an integration attempt before the external effect;
3. return or ingest a schema-validated provider response with an external event ID;
4. translate that response into normal domain commands/records;
5. retain source, adapter mode, timestamps, status, retry, and bounded raw-payload reference;
6. create reconciliation work for invalid, ambiguous, late, or contradictory responses.

Replacing a simulator must not change clinical/RCM tables or let provider callbacks write them directly. Live adapters additionally require credentials, legal/vendor review, sandbox certification, webhook authentication, outage/reconciliation runbooks, monitoring, and end-to-end trading-partner testing.

## Presenter disclosure

Use this exact framing: “Patient, clinical, operational and financial workflows are functional against Ambrosia’s domain model. External payer, clearinghouse, remittance, messaging, prescribing, pathology transmission and settlement networks are deterministic simulations. AI runs on a pinned open-weights model on Modal when its output and provenance validate, with a visibly labeled deterministic fallback. Every person and record shown is synthetic.”

Do not say a claim was sent, a text was delivered, a prescription was transmitted, a lab posted a result, money moved, or an AI model was live unless the UI’s adapter/run evidence proves that specific fact. Say “simulated submission,” “simulated delivery,” or “fallback-generated” as applicable.
