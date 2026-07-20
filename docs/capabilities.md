# Live, functional, and simulated capabilities

“Live” is ambiguous in a healthcare demo. This matrix separates three facts:

- **Internal behavior**: whether Ambrosia must create/query durable domain records and enforce real workflow transitions.
- **External edge**: whether the demo talks to a real healthcare/financial network or an explicit deterministic adapter.
- **Production equivalence**: whether the component is suitable for live patients. Nothing in this repository is production-approved; see [`production-readiness.md`](./production-readiness.md).

The browser consumes a role-scoped workspace from the FastAPI domain plane through the observable shared API client. Patient facts, clinical images, counts, dates, identity, recommendations, queues, and metrics come from the configured database. Approval and note-edit controls call domain mutation endpoints, refresh that read model, and are covered by component, API-contract, workflow, and browser tests. Static UI labels and test-only fixtures remain code; runtime clinical and operational state does not.

## Product and domain capabilities

| Capability | Demo internal behavior | Demo external edge | Required evidence |
|---|---|---|---|
| Authentication and role policy | Functional signed demo session; Modal authorization and role-scoped bootstrap/read models | Pre-seeded synthetic personas; no production IdP | role matrix, bootstrap field-scope and cross-tenant API tests; direct Modal rejection |
| Demo persona switching | Functional API-only signed delegation, separate from the owner role, protected and demo-mode-only | Synthetic personas | owner-without-code rejection; delegated actor continuity; absence from clinician navigation |
| Patient record and timeline | Durable normalized records | Synthetic seed | create/read/update across restart; tenant isolation |
| Patient initiation and scheduling | Functional questions, triage flags, slot selection and booking | Local availability rules | Sarah booking persists and appears on staff schedule |
| Structured intake | Functional normalized allergies, medications, problems, contacts, coverage, consents and images | Synthetic responses/assets | database/API assertions; not one opaque display blob |
| Eligibility | Functional request/result/benefit records and estimate input | **Deterministic payer simulator** | retry idempotency; request/response provenance |
| Patient estimate | Functional calculated, versioned estimate | Uses simulated benefits/fee assumptions | line totals and patient amount reconcile |
| Command center read model | Functional backend queries consumed by Today and Practice through the authenticated workspace endpoint | None | seeded queue counts equal source records; component/browser contracts render endpoint values |
| AI pre-visit summary | Functional run/output/proposal/provenance | Authenticated OpenAI GPT-5.6 Luna with low reasoning when schema/semantics/provenance pass; deterministic fallback otherwise | hosted provider/model/reasoning attestation, timeout/invalid-output fallback test, honest run label and source attribution |
| Encounter state and ambient transcript | Durable encounter/transcript linkage and state | Transcript may be seeded; live speech engine not required | state transition and restart test |
| Structured note drafting | Versioned draft and AI proposal | Authenticated OpenAI GPT-5.6 Luna with low reasoning when validated; deterministic local/remote fallback otherwise | schema/semantic validation, fallback labeling, edit trail, approval visibility |
| Signed notes and amendments | Immutable signed snapshot; append-only amendment | None | mutation fails; original/hash/version chronology preserved |
| Body map and lesion timeline | Persistent lesion, coded body site, observations and comparisons | Synthetic image assets | same lesion spans encounters; ordered observation history |
| Biopsy review-and-complete | Atomic approved bundle creates note/procedure/specimen/order/claim/tasks/message/audit/provenance | Pathology transmission simulated | transaction rollback and command idempotency tests |
| Patient aftercare and messaging | Durable conversation, drafts, sent messages and delivery state; the focused chart reads current conversation evidence | **Deterministic SMS/delivery simulator** | approved message grounding and uncertain-question routing |
| Pathology result workflow | Durable result chain, review, task, notification and closure | **Deterministic lab/pathology simulator** | duplicate result idempotency; overdue result remains queued |
| ePrescribing | Internal proposal/order contract where present | **Deterministic eRx simulator permitted** | must never imply a real prescription was transmitted |
| Claim construction and validation | Structured claim/lines/events from performed care | None until submission | diagnosis/procedure evidence and balanced totals |
| Clearinghouse lifecycle | Durable Draft → Validated → Submitted → Accepted events | **Deterministic clearinghouse simulator** | every transition sourced/timestamped; duplicate response safe |
| Adjudication/remittance | Durable response, adjustments, payments and balances | **Deterministic remittance simulator** | allocations reconcile to claim/line/balance |
| Denial and appeal | Durable classification, evidence, recommendation, work task, appeal/resubmission/recovery | **Deterministic payer/clearinghouse simulator** | original denial retained; recovered revenue traceable |
| Payment settlement | Durable payment/allocation/settlement states | **Deterministic payment simulator** | UI says simulated; ledger remains balanced |
| MSO analytics | Backend metrics calculated from committed source records and rendered by Practice with their source labels | None | metric formulas, source-record counts, and browser rendering without runtime display constants |
| Tasks, notifications and workflows | Postgres-backed reminders/tasks/workflow records; current poller delivers due reminders and escalates overdue tasks | Five-minute Modal schedule; deterministic messaging adapter | current poller test; generalized leasing/retry/dead-letter engine remains a pilot gate; no authoritative Modal Queue |
| Audit and provenance | Append-only actor/action/source/derivation records | None | critical-flow completeness and ordinary-user immutability |
| Learning event substrate | Transactional append-only domain events, consumer checkpoints, longitudinal episode links and point-in-time observation/decision/action/outcome records; initial capture covers intake, AI, encounter completion, pathology and denial correction seams | No external stream required; Neon is the scale-to-zero outbox | mutation/event atomicity, idempotency/hash conflict, aggregate ordering, append-only and two-tenant tests |
| Synthetic healthcare-operations environment | Presenter-gated isolated run from intake review through encounter, pathology, patient notification, claim submission, simulated denial recovery and closure; server-owned transitions and vector rewards | Deterministic versioned patient/payer/care-team simulators | reset isolation, sequential/idempotent steps, invalid-action hard violation, terminal path, simulator provenance and query budgets |
| Internal learning console | Separate presenter-gated `/internal/learning` surface for aggregate capture health, bounded trajectories, governed dataset manifests, and synthetic model-run inspection; model actions, provenance, rewards and hard violations are visible | Same validated OpenAI/fallback policy boundary as the environment API; no live chart or dataset-content browser | access denial matrix, PHI-safe response contract, idempotent model step, terminal run, component interaction tests and production build |
| Governed dataset manifests | Versioned purpose/legal-basis/cohort/cutoff/schema/terminology/de-identification/split/lineage/retention metadata and normalized release membership | Current API exposes one synthetic draft manifest only; no raw export endpoint | PHI-safe manifest shape, no storage/member disclosure, tenant isolation; approval/export worker remains a pilot gate |
| Demo reset and time advance | Tenant/scenario-scoped, deterministic, idempotent | Synthetic only | refusal outside synthetic guard; canonical checksum after reset |
| File metadata and canonical assets | Functional owned metadata, checksum/reference validation and clinical linkage | Bundled public canonical synthetic assets; private upload/read pipeline **not implemented** | wrong file/hash/cross-record link rejected; Vercel Blob authorization is a production gate |
| FHIR import/export | Adapter contract only | **Not connected** | version/profile selection and conformance suite are backlog |

## AI capability modes

Each named capability uses the same interface and validated output schema in both modes.

Managed staging and production call OpenAI `gpt-5.6-luna` directly from the Modal domain API through the Responses API with `reasoning.effort=low` and `store=false`. There is no GPU or separate model endpoint. Deployment attestation rejects a different provider, model, reasoning effort, or prompt identity. A live response records provider `openai`, model `gpt-5.6-luna`, the prompt hash, and `fallback_used=false` only after JSON-schema plus capability-specific semantic validation.

The model has no authority merely because it executed. Coding proposals cannot introduce codes absent from the conservative evidence set; pathology urgency cannot contradict the source result; patient drafts cannot cite unapproved instructions; uncertain messages must route to staff. Any timeout, provider exception, malformed JSON, schema violation, semantic violation, missing attestation, or model/reasoning mismatch returns the matching `ambrosia-fixture-2026.1` output, records `openai_deterministic_fallback`/`fallback_used=true`, and retains the same review requirement. Local zero-credential development uses this deterministic mode directly.

| Capability | Validated OpenAI path | Deterministic resilience path | Human gate |
|---|---|---|---|
| `chart_summary` | minimum-necessary chart context → structured summary; deployment-attested capability | Sarah/fixture-keyed structured summary | clinician verifies before clinical reliance |
| `ambient_note` | transcript context → structured draft | transcript fixture → same schema | clinician edits and signs an exact version |
| `coding_suggestions` | chart evidence → allowlisted coded proposals | deterministic evidence-linked codes | provider confirms facts; biller approves claim use |
| `patient_message` | approved facts → grounded audience-appropriate draft | grounded template with uncertainty routing | staff/provider approval or narrow approved policy |
| `pathology_summary` | source result → clinician/patient drafts with invariant urgency | deterministic result fixture | clinician reviews original and approves release |
| `denial_recommendation` | denial and claim evidence → proposed correction/appeal | deterministic denial fixture | biller validates payer facts and approves submission |
| `document_extraction` | bounded document context → schema-validated proposed facts | deterministic fixture extraction | reconciliation for consequential facts |
| `environment_action` | current synthetic observation + server-owned action allowlist → one typed action | deterministic outstanding-work policy → same schema | synthetic environment validator owns transition and reward; never a live-care command |

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

## Demo disclosure

Use this exact framing: “Patient, clinical, operational and financial workflows are functional against Ambrosia’s domain model. External payer, clearinghouse, remittance, messaging, prescribing, pathology transmission and settlement networks are deterministic simulations. The learning environment is isolated, deterministic and synthetic; it is an evaluation substrate, not evidence of autonomous clinical performance. AI uses OpenAI GPT-5.6 Luna with low reasoning when its output and provenance validate, with a visibly labeled deterministic fallback. Every person and record shown is synthetic.”

Do not say a claim was sent, a text was delivered, a prescription was transmitted, a lab posted a result, money moved, or an AI model was live unless the UI’s adapter/run evidence proves that specific fact. Say “simulated submission,” “simulated delivery,” or “fallback-generated” as applicable.
