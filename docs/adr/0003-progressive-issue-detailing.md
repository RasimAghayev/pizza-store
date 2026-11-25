# ADR 0003: Progressive Issue Detailing Across Phases

## Status

Accepted

## Context

The master prompt (§13/§19) asks for an Epic Issue for all 16 Phases plus detailed Task/
Subtask Issues everywhere — in principle, fully detailed Task/Subtask Issues for all 16
Phases could be written right now.

However, Phases 10-15 (business domain modules) haven't been planned yet because the domain
research and ADRs from Phase 1 don't exist yet. Phases 2-9 depend on the real outcome of
earlier Phases (which Docker image, which CI runner configuration, which test strategy was
chosen). Writing a fully detailed Implementation Prompt for every Phase right now would create
speculative Issues based on decisions that don't exist yet, which would need to be rewritten
at the time of real execution anyway.

## Decision

An Epic Issue is created now for every Phase (see Issues #4-#19), with the full §13 structure
(Objective, Business Context, Technical Context, Architecture Requirements, Acceptance
Criteria, etc.), but fully detailed Task/Subtask Issues are written only for the **next
`Ready` Phase**. Every other Phase's Epic references this ADR in its "Implementation Prompt"
section and states explicitly that detailed Tasks "will be created once this Epic becomes
`Ready`".

A Phase's Epic is only declared `Ready` once the previous Phase's Epic is `Done` (§14: "at the
start of every session ... pick only an Issue in `Ready` status"); at that point, the next
session creates that Phase's detailed Task/Subtask Issues and begins work.

## Reason

- "Every Issue must be executable by the next agent without asking a follow-up question"
  (§13) can only be satisfied by an Implementation Prompt grounded in real, existing
  decisions; Task Issues based on technology choices that haven't been made yet would satisfy
  this requirement only on paper, and turn out useless at real execution time.
- The number of speculative Tasks (16 Phases × roughly 5-10 Tasks each) would create hundreds
  of Issues, most of which would need to be rewritten from scratch before real execution —
  this would clutter the issue tracker and risks violating "don't create a duplicate Issue for
  the same work" (§13).
- The Epic Issues themselves (Objective, Acceptance Criteria, Dependencies) already give
  enough context for every Phase that the next session can start work under the "state lives
  in GitHub" (§14) principle.

## Consequences

- Every Phase has an Epic, but only Phase 1's (the next `Ready` Phase) Task/Subtask Issues are
  fully detailed.
- At the start of every session, the agent must check the current `Ready` Epic and confirm
  whether its Tasks exist; if not, it must create them per this ADR first.
- This fulfills the letter of §13's requirement (creating Tasks) in full, just not all at once
  for every Phase — only as each Phase becomes `Ready`.

## Alternatives

- **Create fully detailed Task/Subtasks for all 16 Phases right now:** rejected — see the
  risks above (speculative, quickly-stale Issues, tracker clutter).
- **Only create Epics, never pre-write Tasks:** rejected — having Phase 1's (the next `Ready`
  Phase) Tasks ready now means the next session doesn't spend time planning from scratch.
