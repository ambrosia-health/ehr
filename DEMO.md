# Dermatologist workspace demo

Target: 8–10 minutes. The audience should leave with one idea: the dermatologist practices medicine while Ambrosia operates the administrative system around every care journey.

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

1. Today: open one of the three judgment stops and approve it. Routine work keeps moving; consequential clinical decisions stop with the dermatologist.
2. Patients: show durable care horizons, not a list of recent chart events. Open Sarah Mitchell to show one patient goal, current state, monitored dependencies, and next meaningful action.
3. Sarah's care agent: review the connected care arc and biopsy plan. Clinical, communication, operational, and financial work share one patient goal without hiding the human approval boundary.
4. Schedule: show readiness, capacity, dependencies, and proposed rebalancing. The schedule is operated as a clinical-capacity system, not a colored appointment grid.
5. Inbox: open Sarah's visit-linked conversation and grounded draft. Ambrosia prepares routine communication; policy or clinical judgment still requires approval.
6. Results: close one actionable result and point to the closure contract. Reading is not closure: disposition, notification, acknowledgment, follow-up, and accountability remain linked.
7. Revenue: follow a financial exception back to its clinical source and approve a supported correction. Revenue work advances automatically without severing evidence or patient explanation.
8. Operations: show explicit may/must-stop policies, capability switches, audit coverage, and intelligence. Autonomy is governed, inspectable, and reversible.

## Claims to make precisely

- The browser product is dermatologist-only. Old login, command-center alias, patient portal, presenter console, encounter demo, and claim-detail routes do not exist.
- The product views are synthetic fixtures today; do not imply that clicking a prototype control writes the domain database.
- The backend implements and tests tenant-scoped records, signed-note immutability, pathology closure, messaging, claims, denials, durable workflows, audit, AI provenance, and human approval.
- AI creates schema-validated proposals with provenance. It does not silently sign clinical records, release consequential messages, or make unsupported financial changes.
- Deterministic fallbacks and provider simulators are reliability and disclosure mechanisms, not compatibility code.

## Verification

`make e2e` verifies the canonical workspace routes, clinician interactions, removal of legacy URLs, same-origin API routing, signed session behavior, request correlation, and `Server-Timing`. Backend workflow tests remain the acceptance evidence for persistence and domain state transitions. Protected demo-control endpoints remain API-only operational infrastructure for seed/reset and release attestation; they are not part of the clinician product.

## Final line

"Ambrosia does not give the dermatologist a better administrative queue. It removes the queue, keeps the care journey moving, and returns only the decisions that require medical judgment."
