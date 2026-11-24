# Flood aware remaining journey formulation

Version 2, 24 November 2026. This is a synthetic research prototype for one bus and one static road snapshot. It implements the 26 October written revision and the user's latest supervisor discussion. It is separate from the Wang paper replication. Safety inputs are supplied, never inferred from demand or penalty values.

## 1 Scope and explicit choices

Choose intentional stop services, their order, the connecting safe road paths, and one eligible safe endpoint from the actual current position. Intermediate services are optional. Original stop order is a baseline, not a hard restriction in this generalized version. Completed operations are fixed. Road nodes may repeat; a stop's service opportunity may be used only once per trip. Reaching the original terminal ends the remaining trip: the terminal is absorbing, including when it is encountered inside a road path. Thus terminal arrival and ending there have exactly the same meaning. This policy avoids penalizing a bus which physically reached the terminal and then unnecessarily left it.

Stop accessibility `accessible`, road-node transit safety `transit_safe`, endpoint eligibility `endpoints`, and safe waiting suitability `wait_safe` are distinct inputs. Finishing requires both transit safety and safe waiting suitability. An inaccessible stop can have a safe passing road and even a safe vehicle stopping area, if the supplied data explicitly say so. Closing a terminal as an endpoint therefore means changing its waiting suitability or endpoint eligibility, not merely its boarding accessibility.

A bus at an unsafe current node may take only a supplied usable outgoing road explicitly marked `escape_verified`, with a transit-safe destination. It may not newly serve at that unsafe node or end there. Other unsafe nodes cannot be entered. The graph is a certification boundary: these binary inputs are assumptions, not a hydrodynamic safety assessment. No reachable safe endpoint means no verified safe action to completion under this model; an unsafe bus then requires intervention. The prototype does not recommend a partial escape ending at a location unapproved for waiting.

An initially unusable terminal is an emergency location rather than a completed safe trip: the root may depart it under the same transit/escape rules, recording `terminal_escape=true` on that first executed move. It earns no terminal arrival credit merely for initially being there. No terminal service candidate is allowed when the terminal is not an eligible safe finish. Subsequent arrival is absorbing. This exception preserves emergency escape without permitting normal trips to continue after terminal completion.

## 2 Sets and construction

* Physical nodes V and roads E have arbitrary nonempty string IDs. A directed road is one ordered arc; an undirected road expands to both directions with the same attributes. Parallel roads retain unique road IDs. Intersections need not be stops.
* S is the input original ordered list of stop IDs. U is the supplied stop universe, including original and alternative stops. Multiple distinct stops may share a physical node; their demand groups must still be disjoint.
* B is the set of stops already served in the immutable event history. Each service event records its realized dwell and demand/score at execution; later input edits do not rewrite that record.
* I consists of stops in U minus B which pass **all** enabled eligibility rules: original member or `candidate=true`; optional explicit allowed-stop list; optional maximum **normal network travel minutes from any original stop** (not geographic distance); current stop accessibility; node transit safety; reachability from current position using certified movements; and ability to reach at least one eligible safe endpoint. Every exclusion is reported. No default corridor or count truncation is applied. A user restriction can exclude useful routes; optimality is conditional on this I. Original start and terminal may have demand if supplied; examples set it to zero. Candidate nodes are service opportunities, never newly constructed stops.
* F is the eligible endpoint node set: supplied endpoints plus the current node if safe for waiting, intersected with transit-safe and wait-safe nodes. The current safe waiting option is explicitly added, even if it is not a nominated regular endpoint. Reachability is reported separately. Waiting at the origin has zero physical movement.
* Event graph N has root a, one service event for each i in I, and a distinct finishing event b_e for every e in F. Even when events share a physical node they remain distinct, with zero travel between them. A root or service event can connect to a distinct service event or a finishing event when the certified shortest road path exists. No arcs enter a or leave a finishing event. The terminal cannot be an internal node of a connection; a service event at the terminal can connect only to a finishing event at that same node. Call this arc set A. Empty road paths are valid for colocated events.

Repeated single-source Dijkstra on nonnegative static road times gives directed costs c_pq and retains exact road IDs and orientations. Unreachable pairs are absent from A, not assigned enormous costs. An unsafe root has a root-only escape search; subsequent sources cannot reuse that permission. Normal searches do not use disrupted restrictions.

## 3 Inputs and units

Road normal/disrupted times, service dwell s_i, realized elapsed time E0, and thresholds T_ref, T_soft, T_max are minutes. Current road time null, `closed=true`, or `safe=false` removes a road. D_i is a nonnegative disjoint stop-access service proxy per trip; w_i is a nonnegative dimensionless priority. Benefits w_i D_i are access points. The three nonnegative rates lambda_ref, lambda_soft, lambda_max are points/minute; kappa is points for terminal non-arrival. theta >= 1 is dimensionless. Require 0 <= T_ref <= T_soft <= T_max in this version for an unambiguous ordered marginal-rate explanation. All thresholds are **full-trip** fixed inputs; they are not recomputed after skipping stops or replanning. T_ref should be a justified normal all-stop reference; the old example uses 34.5. Every numeric input must be finite and nonnegative. No hard T_max remains.

State supplies journey origin, immutable ordered move/service/wait events, actual current node and elapsed minutes. Sum of recorded event durations must equal E0, the reconstructed history must end at current, and no service ID may repeat. Events contain realized times so today's closures do not invalidate yesterday's completed movements. Historical roads, stops and endpoints remain in the topology; only snapshot attributes may change. At the current stop, completed dwell is already in E0; an unserved stop can be served now only by explicitly selecting its full dwell. Partial dwell and passengers in boarding are not modeled; replan at event boundaries or supply an explicit remaining-service representation outside this schema.

## 4 Decision variables

* x_pq in {0,1}: selected event-graph connection (p,q) in A.
* u_i in {0,1}: intentionally service candidate stop i, earning its proxy once.
* r_e in {0,1}: end at eligible physical node e via its finishing event.
* r_terminal in {0,1}: actual original-terminal arrival; exactly r_t if terminal t is in F, otherwise zero.
* q_i: service-event order, continuous in [1,n] where n=|I| (unused variables can take any value in that range). For n=0 omit these variables and constraints.
* T,R,L_ref,L_soft,L_max >= 0: full trip time, remaining duration and the three excess times.

## 5 Objective and every constraint

Maximize

$$
\Phi=\sum_{i\in I}w_iD_i u_i-\lambda_{ref}L_{ref}-\lambda_{soft}L_{soft}-\lambda_{max}L_{max}-\kappa(1-r_{terminal}).
$$

Already earned score is fixed and excluded from the new optimization. The reported objective is remaining service reward minus **full-trip** penalties. The state limit counts distinct generated DP states across all layers, and the wall-clock limit is checked between state expansions after preprocessing and initial feasible-ending construction; it is not a strict process kill deadline. Comparing objectives across different elapsed states needs this convention; across snapshots at the same state it is direct. Equal primary scores prefer smaller remaining time, then a deterministic service-ID and endpoint order. This is an explicit secondary objective, not a tiny arbitrary epsilon.

1. Root departure: sum_{q:(a,q) in A} x_aq = 1. This is an event connection, not a requirement to move on a road: a -> b_current is the safe zero-movement option, and a -> current-stop-service can also have empty road path.
2. Finishing choice: sum_{e in F} r_e = 1; sum_{p:(p,b_e) in A} x_p,b_e = r_e for every e. Exactly one safe endpoint is reached.
3. Service linkage: sum_{p:(p,i) in A} x_pi = u_i = sum_{q:(i,q) in A} x_iq for every i in I. No reward can be collected at an unvisited or merely passed stop. Service at the final node is optional; the separate finishing event does not force boarding.
4. Cycle elimination: q_j >= q_i + 1 - (n+1)(1-x_ij) for service-service arcs. With bounds [1,n] the derived constant n+1 is sufficient, not an arbitrary large operational penalty. Selected arcs strictly increase order, eliminating disconnected cycles. Combined with the unique root, balance, and sink equations, every selected service lies on the one root-to-finish path.
5. Hard safety is encoded by I, F and A. Equivalently u_i <= accessible_i and u_i <= transit_safe_node(i); r_e <= wait_safe_e and transit_safe_e. No preference variable can enable an excluded road, service or unsafe finish.
6. Remaining duration R = sum_(p,q in A) c_pq x_pq + sum_(i in I) s_i u_i. Full-trip duration T = E0 + R. All history terms are constants. No cap T <= T_max is imposed.
7. L_k >= T-T_k and L_k >= 0 for k in {ref,soft,max}. Positive rates tighten their hinges at optimum. At zero rates auxiliaries need not be tight, so reporting always recomputes L_k=max(0,T-T_k) from reconstructed T.
8. r_terminal = r_t if t in F, else r_terminal=0. Terminal absorption in preprocessing ensures this indicates physical arrival, including zero movement when already at a safe terminal. No individual selected arc substitutes for this linkage.
9. Binary and continuous domains as above complete the formulation. History is not a decision variable; previously served IDs are excluded from I and its records are append-only in the advancement API.

The full linear system can also be read together below. Let \(\delta^-(v)\) and \(\delta^+(v)\) be the incoming/outgoing event arcs, and \(K=\{ref,soft,max\}\). Empty sums are zero. Safety and completed-service exclusion are enforced by constructing I, F and A before any variables exist.

$$
\begin{aligned}
\max\quad & \sum_{i\in I}w_iD_iu_i-\sum_{k\in K}\lambda_k L_k-\kappa(1-r_{terminal}) \\
\text{s.t.}\quad & \sum_{(a,j)\in A}x_{aj}=1,\qquad \sum_{e\in F}r_e=1,\\
& \sum_{(p,b_e)\in A}x_{p,b_e}=r_e && e\in F,\\
& \sum_{(p,i)\in A}x_{pi}=u_i=\sum_{(i,q)\in A}x_{iq} && i\in I,\\
& 1\le q_i\le n && i\in I,\\
& q_j\ge q_i+1-(n+1)(1-x_{ij}) && (i,j)\in A,\ i,j\in I,\\
& R=\sum_{(p,q)\in A}c_{pq}x_{pq}+\sum_{i\in I}s_iu_i,\\
& T=E_0+R,\\
& L_k\ge T-T_k,\qquad L_k\ge0 && k\in K,\\
& r_{terminal}=\begin{cases}r_t,&t\in F,\\0,&t\notin F,\end{cases}\\
& x_{pq},u_i,r_e,r_{terminal}\in\{0,1\},\qquad R,T\ge0.
\end{aligned}
$$

When n=0 omit the service and order equations. Root-to-finish arcs still include a safe same-location option where permitted. `plan.decisions` exports every new-service u and endpoint r, the linked terminal binary, selected x connections (all others zero), and the selected service order. `plan.legs` retains every underlying directed road path; the independent checker verifies these against the execution events.

These are cumulative hinge penalties. Marginal charge per minute is 0 before T_ref, lambda_ref up to T_soft, lambda_ref+lambda_soft up to T_max, and the sum of all three thereafter. The soft and max coefficients are **additional** rates, not total band rates. If desired total band rates are 2,6,14, enter additional rates 2,4,8. This intentional cumulative charge preserves the latest written model; adding separate identical delay or missed-demand costs would double count.

## 6 Exact implementation and correctness argument

`prepare` validates, creates I/F and directed shortest paths. `solve` implements the event formulation through subset dynamic programming, rather than requiring an external MILP installation. A state (M,i) records the subset M already newly served and its last service i. Its reward is fixed by M, so retain only the least duration for that state. Any continuation has the same available services and endpoint options, while a greater duration cannot improve a nondecreasing time penalty. Induction on |M| gives the least duration for every possible served subset and final service. Evaluate all eligible endings at every state, plus no-service endings from root. This enumerates all feasible elementary service journeys implicitly; repeated physical nodes remain permitted. It also implements the secondary shorter-time rule. Complexity is O(2^n n^2 + 2^n n |F|) after shortest paths, with exponential memory in n. Use candidate filters and state/time limits; large-city scalability is unresolved.

For a resource/time limit, return only an independently verified feasible incumbent, labeled `feasible_time_limit` or `feasible_state_limit`. Bound: sum_(i in I) w_i D_i is a valid (possibly loose) upper bound because penalties are nonnegative. Absolute bound gap and a guarded relative gap are reported; no MILP gap is invented. Completed search reports optimum within floating arithmetic (time equality tolerance 1e-8 in audit, objective comparison tolerance 1e-9). Invalid input, physical lack of a reachable permitted endpoint, search failure, and limited search are separate statuses. A failure is never silently converted into a route.

One shortest path per connection suffices only because extra transit has no benefit, all service benefits require explicit service events, costs are static and additive, and repeated physical nodes are allowed. It is not valid for path-dependent flood exposure, turn restrictions missing from nodes, no-repeat-road policies, time windows or future changes. Expand road state for known turning restrictions. No unrestricted network optimality is claimed beyond these assumptions and the eligible stop universe.

## 7 Disruption flags and operational interpretation

For each original consecutive stop pair report c1/c0 where c0>0 and finite. If c0=0, use ratio 1 for c1=0 and an explicit `zero_normal_positive_current` flag otherwise; if current is unreachable, flag it directly without division. An unreachable normal pair has `normal_unreachable` and no numeric ratio. Also report closures on the **normal reference path**, even when a detour keeps the ratio below theta. These are descriptive diagnostics only: every solve uses the current safe graph, regardless of theta. Stop accessibility is reported separately.

Operational outcomes: `reaches_terminal`, `terminates_elsewhere_safely`, `stays_safely_by_choice`, `cannot_move_from_safe_location`, `intervention_required` for unsafe origin without a verified completion, and `no_verified_safe_action` for other locations without an approved reachable finish. No movement is based on the reconstructed road edge count; a same-location service can occur without movement. Report physical outgoing usability and terminal reachability separately from preference choice. Safety is only for the supplied snapshot.

## 8 Penalty calibration and limits

A priority of 2 means one demand unit contributes twice the access score, not guaranteed service. A rate of 4 means one extra minute must be justified by 4 additional points while that hinge is active. Kappa is the service score one is willing to lose to complete the terminal. Obtain these from operator trade-off discussions and test ranges; the supplied numbers are synthetic. An unsafe important stop remains unavailable for every finite priority. No capacity, passenger origin-destination completion, evacuation objective, fleet allocation, dispatch, depot, travel-time prediction, uncertainty or digital twin is implemented. This is repeatable snapshot replanning at executed-event boundaries, not a validated time-dependent optimization or real-world safety approval.
