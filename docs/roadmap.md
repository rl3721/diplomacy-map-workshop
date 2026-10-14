[Home](../README.md) | [Documentation index](README.md)

# Development roadmap

This document records future work. Unchecked items and suggested scoring weights
are proposals, not implemented behavior or proven balance rules.

## Pending: Map reviews and Cloudflare hosting

Status: pending work. Assessment and setup guides are available; the review
feature is not implemented and no Cloudflare resources have been provisioned.

- [ ] Add a review option after map generation with a required 1–5 rating and
  an optional comment, explaining what is uploaded when the user submits.
- [ ] Capture the exact displayed map, resolved settings, actual stage seeds,
  generator version and diagnostics so each review can be reproduced.
- [ ] Implement the Cloudflare Worker submission API, D1 review/metric storage
  and private R2 map snapshots, with validation and abuse controls.
- [ ] Handle duplicate submissions, network failures and retries without losing
  the review draft or associating it with a different map after a rerun.
- [ ] Set up separate Cloudflare development hosting and storage from
  `develop-main`, keeping production feedback separate from development data.
- [ ] Add private exports for analysis, retention/deletion rules and focused
  verification of submission, storage and access controls.
- [ ] Use feedback to investigate generation quality and balance hypotheses;
  distinguish perceived quality from balance established through playtesting.

Details: [review proposal](map-reviews.md) and
[Cloudflare implementation guide](cloudflare.md).

## Current baseline

- [x] Symmetric mode uses regional powers only: three owned home SCs per power,
  with victory at `floor(total SCs / 2) + 1`.
- [x] Every power must have at least one coastal starting SC.
- [x] From each starting SC, one unit type (army or fleet) must be able to reach
  both other starting SCs in at most two moves. Centers need not touch. The unit
  type may differ between origins; routes ignore occupancy and exclude convoys.
- [x] Search 160 candidate assignments, preferring separation, compact starts,
  and comparable neutral access. Neutral access currently uses the combined,
  untyped movement graph; this is a placement heuristic, not gameplay balance.
- [x] Export power ownership, home cores, coastal starting centers and witness
  routes; provide a Powers SVG and power-only reruns with fresh stage seeds.
- [x] Asymmetric checkbox increases province capacity by 1.5 before division.
  SC budgeting includes this increase through the final province-count ratio,
  exactly once. Terrain and hex resolution remain unchanged.
- [x] Asymmetric power assignment currently reports "To be implemented".

## Priority 1: Better balance evaluation

### Legal movement and opening opportunities

- [ ] Replace untyped expansion distances with separate legal army and fleet
  movement distances. Model split coasts consistently with DiplomacyGM.
- [ ] Preserve wrap, sphere, impassable and named high-ocean-slot connections.
  A merged ocean must not become a single unlimited-capacity movement location.
- [ ] Design starting army/fleet allocation. Evaluate positions with feasible
  starting units rather than assuming every center can deploy either type.
- [ ] Estimate reachable neutral SCs over the first few movement seasons,
  accounting for unit availability, autumn ownership and build timing.
- [ ] Treat convoy access separately: a geographical sea route does not imply
  that the required fleets exist or that convoy orders will succeed.
- [ ] Compare competing arrival times. Distinguish relatively safe, contested
  and difficult expansion; do not credit the same neutral fully to every power.

### Security, reinforcement and diplomacy

- [ ] Evaluate starting-center exposure, mutual support and useful retreat routes.
- [ ] Measure reinforcement time and usable build locations, including fleet
  access. Coastal access alone does not guarantee a useful naval position.
- [ ] Measure the number and strength of nearby opponents, encirclement risk,
  and access to alternative diplomatic partners.
- [ ] Detect isolated expansion areas, severe bottlenecks and positions with
  very limited opportunities to interact with other powers.
- [ ] Assess both the weakest position and disparity across all powers; a good
  average must not hide one power with an unviable opening.

### Scoring and assignment search

- [ ] Keep hard starting rules separate from soft balance preferences. No soft
  score may compensate for violating a hard rule.
- [ ] Prototype a separate power-balance score, distinct from structural map and
  SC-placement scores. Initial weights to evaluate, not fixed requirements:

  | Component | Trial weight |
  |---|---:|
  | Early expansion opportunities | 30% |
  | Starting security | 25% |
  | Reinforcement and build access | 20% |
  | Diplomatic opportunities | 15% |
  | Setup quality and compactness | 10% |

- [ ] Normalize metrics across player counts, map sizes and terrain styles.
- [ ] Improve complete assignments through swaps/local search; reduce bias from
  selecting powers sequentially and test sensitivity to assignment order.
- [ ] Define minimum acceptable balance and weakest-power thresholds. Distinguish
  "no legal assignment" from "legal but below the requested balance threshold".
- [ ] Report per-power measurements, component scores and reasons for rejection.
  Keep internal scoring weights out of ordinary user controls.
- [ ] Preserve upstream stages when assignment fails. Offer an explicit SC or
  province rerun rather than silently changing the map to improve the score.

## Priority 2: Asymmetric power setup

### Configuration and budgets

- [ ] Allow regional powers with different starting SC counts.
- [ ] Allow optional colonial powers with independently varying home-cluster
  size, colony count and total starting SC count.
- [ ] Define simple controls for the colonial-power share and permitted starting
  sizes. Validate the combined budget and reserve a meaningful neutral SC pool.
- [ ] Retain the pre-division 1.5 capacity factor, including at non-default size
  ratios. Explicit province counts are already final and must not be multiplied
  again; SC generation must not double-count the factor either.
- [ ] Decide which feasibility requirements belong before province division and
  which can be checked after SC placement, without silently rerunning terrain.

### Placement, cores and units

- [ ] Give each regional power a local starting group and each colonial power
  a smaller home group plus geographically separated colonies.
- [ ] Specify how the two-move rule generalizes to groups larger than three.
  Decide whether it applies to colonial home groups only; distant colonies
  should not accidentally be subjected to a regional-cluster rule.
- [ ] Preserve the no-landlocked-power requirement; decide whether colonial
  powers must also have a coastal home center, rather than only coastal colonies.
- [ ] Distinguish owned uncored outposts from owned cored colonial build bases.
  Evaluate their different reinforcement and expansion advantages.
- [ ] Support optional neutral precores: initially neutral SCs with a full core
  assigned to a power. Keep owner, full core and temporary half-core distinct.
- [ ] Balance precore counts and acquisition difficulty, not merely their number.
- [ ] Assign starting units consistent with ownership, terrain and the intended
  regional/colonial role. Avoid giving every colony an unrealistic free choice
  of recruitment or reinforcement.

### Per-power victory conditions

- [ ] Assign different fixed victory SC targets after evaluating each power's
  starting size and position. Targets must not change during play.
- [ ] Use local variant configurations as reference data. Planiglobii currently
  includes `iscc/vscc` pairs 3/20, 4/22, 5/24 and 6/25; these are examples,
  not a formula that can be copied to every generated map.
- [ ] Calibrate starting resources and additional conquests separately. A trial
  model is `target = starting_SCs + round(base_conquests * capability_factor)`.
  Scale base conquests with map size; constrain and validate the adjustment.
- [ ] Separate opening survival from victory difficulty. A lower victory target
  must not be used to excuse an indefensible starting position.
- [ ] Reject targets already met at the start, targets above total SC count,
  and targets reachable solely through an excessive safe neutral allocation.
- [ ] Decide when victory is evaluated and how simultaneous qualification is
  resolved: shared victory or a clearly specified sole-winner tie rule.
- [ ] Verify DiplomacyGM's `vscc` integration, including `iscc`, normalized
  progress, scoreboard display and actual end-of-game handling. Existing
  progress calculation alone does not establish automatic winner resolution.

## Priority 3: Presentation, export and validation

- [ ] Show home centers, colonies, colonial bases and neutral precores distinctly
  in SVGs, with a legend and per-power starting/victory counts.
- [ ] Export per-power roles, ownership, cores, units, victory targets and balance
  diagnostics in a versioned format compatible with the eventual adjudicator import.
- [ ] Add a readable balance panel showing the weakest position, disputed neutral
  opportunities and known limitations instead of presenting a score as proof.
- [ ] Verify power-only reruns preserve terrain, provinces and SC locations;
  saved actual stage seeds must reproduce the complete assignment.
- [ ] Add focused regression cases for split coasts, island groups, unavailable
  convoys, blocked routes, insufficient coastal SCs and overlapping claims.
- [ ] Test asymmetric budgets, colonies, precores, victory thresholds and tie
  handling, including small maps and insufficient-budget failures.
- [ ] Run a bounded seed/parameter study to measure assignment success rate,
  power disparities and runtime before selecting default balance thresholds.
- [ ] Calibrate with playtests and outcomes from actual games. Geography scores
  and automated openings cannot fully model negotiation or player behavior.

Suggested order: improve legal movement and contested expansion evaluation,
then starting units and symmetric balance reporting, then asymmetric placement
and victory-target calibration.
