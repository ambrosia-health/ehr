# Dermatologist workspace demo

Target: 6–8 minutes. The audience should leave with one idea: the dermatologist practices medicine while Ambrosia operates the administrative system around every care journey.

Every person, image, message, result, claim, and dollar is synthetic. Say once at the start: "This product prototype uses explicit synthetic presentation fixtures. The repository's domain API, database workflows, authorization, audit, and AI proposal contracts are tested separately; external healthcare and payment networks remain deterministic simulations."

## Preflight

For local development:

```bash
make dev
# In a second terminal
make e2e
```

Open [http://localhost:3000](http://localhost:3000). The product opens directly at `/`; there is no login or persona-selection step. Keep browser zoom at 100%.

For the managed hosted demo, open [ambrosia-ehr.vercel.app](https://ambrosia-ehr.vercel.app). Vercel-to-Modal-to-Neon bindings, synthetic data, and model configuration are platform-managed.

## Walkthrough

1. Today: approve Sarah's plan inline and watch Jordan's pathology decision become the only next question. Routine work keeps moving; consequential clinical decisions stop with the dermatologist.
2. Patients: use the compact worklist to show every active journey's concern, operating state, last automated activity, and one next action. Search or filter without leaving the page, then open Sarah Mitchell.
3. Sarah's focused view: read the patient context, biopsy question, recommended plan, confidence, deadline, paired clinical images, and ruled evidence table as one decision brief. Modify or approve the plan without opening another queue.
4. Practice: close on the calm operating view. Show patient journeys moving, external dependencies being monitored, automation health, and the receipts for administrative work completed without creating another queue for the dermatologist.

## Claims to make precisely

- The browser product is dermatologist-only. Old login, command-center alias, patient portal, presenter console, encounter demo, Schedule, Inbox, Results, Revenue, Operations, and claim-detail routes do not exist.
- The product views are synthetic fixtures today; do not imply that clicking a prototype control writes the domain database.
- The backend implements and tests tenant-scoped records, signed-note immutability, pathology closure, messaging, claims, denials, durable workflows, audit, AI provenance, and human approval.
- AI creates schema-validated proposals with provenance. It does not silently sign clinical records, release consequential messages, or make unsupported financial changes.
- Deterministic fallbacks and provider simulators are reliability and disclosure mechanisms, not compatibility code.

## Verification

`make e2e` verifies the canonical workspace routes, clinician interactions, removal of legacy URLs, same-origin API routing, signed session behavior, request correlation, and `Server-Timing`. Backend workflow tests remain the acceptance evidence for persistence and domain state transitions. Protected demo-control endpoints remain API-only operational infrastructure for seed/reset and release attestation; they are not part of the clinician product.

## Final line

"Ambrosia does not give the dermatologist a better administrative queue. It removes the queue, keeps the care journey moving, and returns only the decisions that require medical judgment."
