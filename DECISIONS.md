# Decisions

A running log of decisions made while building CaddieTalk, with the reasoning behind them.
Append new entries at the bottom. Never edit history — if a decision is reversed, add a new
entry that supersedes the old one and mark the old one accordingly.

Format: `D-NNN — Title` · date · status (`accepted` / `superseded by D-NNN`).

---

## D-001 — One container image with two Lambda functions, not a separate engine service

**Date:** 2026-09-24 · **Status:** accepted

The original architecture had a Caddie Lambda synchronously invoking a separate Engine
Lambda for tool calls. That means two cold starts, two billed durations, and a
cross-function hop inside a ~4 second latency budget.

Because the engine is a pure Python library with no AWS dependencies, the caddie can simply
import and call it in-process. We ship **one container image** deployed as **two Lambda
functions**: a high-memory `engine` function serving `/engine/*` to the mobile app, and a
`caddie` function that runs the engine library in-process for tool calls.

**Trade-off accepted:** the caddie function carries NumPy/Shapely in its image even when a
turn needs no simulation. At personal scale this costs pennies, and the two functions can
still be memory-tuned independently.

---

## D-002 — CDK in Python rather than TypeScript

**Date:** 2026-09-24 · **Status:** accepted

The architecture originally specified CDK in TypeScript, which would have meant three
toolchains (app TS, backend Python, infra TS). Writing CDK in Python drops that to two: one
virtualenv, one linter, one test runner for everything server-side.

The CDK API is nearly identical across languages, so little is lost. The counterargument —
that TypeScript CDK is more common in industry and therefore has more résumé value — was
considered and judged not worth the extra toolchain for a solo project.

The mobile app remains TypeScript, so TS exposure is retained either way.

---

## D-003 — No cloud speech-to-text in P0

**Date:** 2026-09-24 · **Status:** accepted

Amazon Transcribe was specified as a streaming fallback for devices where on-device speech
recognition performs poorly. Cut from P0.

Building it means a second audio pipeline — WebSocket streaming, chunked upload, separate
auth — for a case that may never fire, and the learning payoff is low since it amounts to
another managed API call. On-device recognition is free, fast, and available on both iOS
and Android.

**Revisit if:** field testing shows on-device recognition is genuinely inadequate on the
course (wind noise being the most likely cause).

---

## D-004 — Deliberate AWS service boundaries

**Date:** 2026-09-24 · **Status:** accepted

A stated goal of this project is hands-on AWS experience, which creates a standing
temptation to reach for more services than the problem needs. The line we drew: **use a
service where it solves a real problem here, and where we can explain the choice.**

Kept: CDK, Lambda, API Gateway (HTTP API), DynamoDB on-demand, S3, Bedrock, Cognito,
CloudWatch, Polly. Fargate deferred to P2 only.

Explicitly rejected, with reasons, in section 12 of `docs/architecture.md`: Amazon Location
Service, Amplify, X-Ray, Secrets Manager/SSM, Step Functions, OpenSearch, RDS/Aurora, and
single-table DynamoDB design.

EventBridge/SQS is earmarked as the one deliberate event-driven exercise at M9 (round
finish → model recompute → AI summary), to be built synchronously first and refactored as a
conscious learning exercise.

---

## D-005 — Cost guardrails live in the CDK, not in anyone's memory

**Date:** 2026-09-24 · **Status:** accepted

The project runs on a ~$100 CAD AWS signup credit. Guardrails that depend on remembering to
do something are not guardrails, so they are encoded in infrastructure: 14-day log
retention, `PAY_PER_REQUEST` DynamoDB, S3 lifecycle expiry on generated audio, 30-second
Lambda timeouts, low reserved concurrency, and no Lambda inside a VPC (a NAT Gateway alone
would be roughly a third of the budget per month).

Budgets alerts at $10/$25/$50 are step zero of M4, before any deploy. The caddie eval set
runs manually and never in CI, since automated Bedrock calls on every push are the single
most likely accidental burn.

---

## D-006 — The strokes-gained baseline is an approximation, not a blocker

**Date:** 2026-09-24 · **Status:** accepted

Sourcing an authoritative amateur strokes-to-hole-out baseline is an open problem
(published research is not freely redistributable, and tour baselines are miscalibrated for
amateurs). Treating it as a prerequisite would stall M2 indefinitely.

Decision: start with a reasonable parameterized curve per lie, stored as CSV in
`data/baselines/` with a header noting it is a tunable approximation. The engine's relative
comparisons between aim points are far less sensitive to baseline accuracy than its
absolute expected-score outputs, so an approximate table still produces useful
recommendations.

Refine later against real logged rounds. The rule that stays: baseline numbers live in data
files with sourcing notes, never hard-coded in engine code.

---

## D-007 — The live call is the primary voice experience, not push-to-talk

**Date:** 2026-09-25 · **Status:** accepted · supersedes the P2 placement of F-17

Push-to-talk was P0 and real-time speech-to-speech (F-17) was a P2 stretch goal. That is
backwards relative to what this product is trying to be.

Push-to-talk is a walkie-talkie: hold, speak, release, wait several seconds, listen. It is
a device you operate. A live call — headphones in, both parties talking, interruption
allowed — is a person walking beside you. The second is the actual pitch of the product,
and the difference is not incremental.

F-17 moves to P0 and becomes the M7 deliverable. F-09 push-to-talk stays, demoted to the
fallback path: no headphones, poor signal, or playing partners who would rather you didn't
hold a conversation with your phone. It also costs almost nothing to keep, since it reuses
the text caddie's request/response path.

Added alongside it: **F-25, the caddie avatar** — a minimal capped silhouette that listens,
speaks, and turns to look at what it is discussing. Deliberately not a face and not
photoreal.

**Cost consequence, accepted knowingly:** a live call needs a connection held open for
minutes, which Lambda cannot do. That means a container service that bills while idle
(~$25–30/month with a load balancer) against a ~$100 credit. How to handle that is settled
at M4 — see D-008.

---

## D-008 — Build the whole thing on localhost before touching AWS

**Date:** 2026-09-25 · **Status:** accepted · reorders the build plan

The original plan built the AWS backend (M4) before the mobile app (M5), so that the app
would have something to call. Reordered: **M5 → M6 → M7 → M4.**

The app, the text caddie, and the live voice caddie are all built against a Python dev
server running on the builder's laptop, reached over wifi. Nothing is throwaway — the same
FastAPI application gets wrapped for Lambda at M4, and a local server is worth having
permanently anyway, since deploying to test a change is miserable.

**Why the reorder:**

- Infrastructure built before the product has settled gets built twice. The live voice
  service in particular has an unknown shape right now.
- It keeps spend at $0 through three more milestones.
- M4 then opens with a **cost and architecture review against a system that actually
  exists**, rather than a guess about one that doesn't — which is the only way to answer
  the Fargate question from D-007 honestly.

**What this requires of the code:** the app points at a single configurable base URL, and
server code stays free of assumptions about running locally. Both are cheap to hold to and
expensive to retrofit.
