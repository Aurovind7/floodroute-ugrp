# Scenario input format

Use `scenario_template.json` as the complete copy-and-edit template. Files are UTF-8 JSON with `schema_version: 2`. Times are minutes and all IDs are nonempty strings. The programmatic validator `validate` is authoritative for cross-reference and history checks; `scenario.schema.json` describes the JSON shape. Unknown metadata fields are preserved but do not affect routing.

## Network and service inputs

| Field | Meaning |
| --- | --- |
| `directed` | Required boolean. False expands each road into both directions; true preserves its orientation. |
| `nodes` | Records with unique `id`, required booleans `transit_safe` and `wait_safe`; optional finite `x,y` coordinates for the schematic. A junction needs no stop record. |
| `roads` | Unique `id`, `from`, `to`, finite nonnegative `normal_time`, and explicit `current_time` (nonnegative number or null). Optional booleans: `closed=false`, `safe=true`, `escape_verified=false`. Either a closure, unsafe road, or null current time disables the edge. Parallel road IDs are allowed. Undirected attributes apply both ways; use two directed roads for asymmetric conditions. |
| `stops` | Unique `id`, node mapping `node`, nonnegative `demand`, `priority`, `dwell`, booleans `accessible` and `candidate`. Defaults: demand 0, priority 1, dwell 0, accessible true, candidate true. Multiple stops can share a road node only if their demand groups are disjoint. |
| `original_route` | Ordered array of distinct known stop IDs. It is used for comparison, corridor construction and disruption flags; it does not constrain remaining service order. Its last stop must map to the terminal. |
| `terminal` | Original terminal **node ID**, not necessarily its stop ID. Arrival there ends the trip under the absorbing-terminal policy. |
| `endpoints` | Distinct node IDs approved for ending. A nominated endpoint must also have transit_safe and wait_safe true. Safe waiting at the current node is added automatically. A terminal with boarding closed may still permit safe vehicle arrival if these inputs say so; to prohibit ending there, remove endpoint eligibility or set wait_safe false. |
| `theta` | >=1; default 1.5. Ratio flags and closure diagnostics only. Never controls whether the safe graph is used. |
| `candidate_filter` | Optional object, default `{}`. `allowed_stop_ids` can be null or an explicit stop-ID array; an empty array allows no service. `max_normal_minutes_from_original` can be null or nonnegative minutes. This is a directed normal-network-time corridor from any original stop, not kilometres or a geographic buffer. |

I is constructed from the supplied universe of original stops and alternative records with candidate=true, minus served stops, then the explicit list/corridor, accessibility, node safety, current reachability and safe-finish reachability tests. `exclusions` gives every applicable reason. The user is responsible for supplying useful alternative stops and disjoint demand; there is no inference of new stop locations or catchment overlap.

## Parameters

`parameters` requires all seven fields:

* `T_ref`, `T_soft`, `T_max`: fixed whole-trip thresholds with 0 <= T_ref <= T_soft <= T_max. Enter the original normal all-stop reference explicitly; it is not automatically recalculated from a skipped/replanned route.
* `lambda_ref`, `lambda_soft`, `lambda_max`: nonnegative **additional cumulative hinge** rates, points/minute. For total marginal rates 2,6,14 enter 2,4,8.
* `kappa`: nonnegative points charged once if no safe arrival at the original terminal.

For elapsed E and remaining R, full time is E+R. Do not subtract E from the thresholds. Three excess times and all four penalties are exported separately.

## Operational state and completed history

`state` requires `origin`, `current`, `elapsed`, `history`. With no executed events, origin=current and elapsed=0. A bus between stops needs its actual road-state position represented by a node and the remaining permissible road connections; do not snap it back to the previous stop. The prototype does not split an actively traversed edge or partially completed dwell automatically.

Every historical event includes a nonnegative realized `minutes`. A verified emergency departure from an unusable current terminal additionally records `terminal_escape: true`; that historical marker permits escape without treating an unsafe starting terminal as completed safe arrival. Imported historical markers are supplied operational facts, like other realized safety assumptions.

Example event objects:

```json
{"kind":"move", "road":"main1", "from":"depot", "to":"school", "minutes":2}
{"kind":"service", "stop":"school_stop", "node":"school", "minutes":1, "demand":12, "score":12}
{"kind":"wait", "node":"school", "minutes":3}
```

These are three separate event objects within the history array, not one JSON file. History must connect from origin to current, obey physical road direction, sum to elapsed, and never repeat a service ID. Historical closures/safety are not reassessed against today's snapshot. Keep the road/stop IDs used in history in the topology. Realized demand/score/dwell remain fixed even if current inputs change. Initial histories are supplied operational facts, not evidence validated by this prototype.

`advance(scenario, result, event_count)` commits only the first event_count planned events after independently rechecking the plan and matching the entire scenario fingerprint. It returns a new scenario. The old scenario object and history remain untouched. A result becomes stale after any input change. Advancing to a stop before its service event does not collect demand or charge dwell yet. Re-solving after advancing never rewards completed services again. Direct edits to history represent a different initial scenario and are not part of snapshot updates.

## Output and status

`solver_status` is separate from `plan.operational_outcome`:

| Solver status | Meaning |
| --- | --- |
| `optimal` | Complete exact subset search under this model and its candidate set, floating arithmetic. |
| `feasible_time_limit` / `feasible_state_limit` | Audited feasible incumbent; no proof of optimum. Bound gaps are conservative, based on all possible remaining reward. |
| `physical_infeasible` | No certified path to a permitted safe endpoint, including no permissible safe waiting option. |
| `invalid_input` | Schema/domain/history inconsistency; not physical infeasibility. |
| `verification_failed` | The independent road audit rejected a proposed plan. No plan is returned. |
| `solver_failure` | An unexpected internal search failure; no plan is returned. |

Physical outcomes include reaches_terminal, terminates_elsewhere_safely, stays_safely_by_choice, cannot_move_from_safe_location, intervention_required and no_verified_safe_action. A lack of a usable outgoing road and a preference to stay are distinct. No verified safe completion does not prove that an unrepresented emergency action is impossible.

`served_demand_proxy` is newly served unweighted stop demand; `weighted_service_score` is sum w*D for those services. Historical totals are separate. `objective` excludes historical reward but includes full-trip penalties. Service events, road IDs and oriented moves permit independent reconstruction. Runtime includes preprocessing and final audit. A gap of zero accompanies completed search; a limited search can have a loose nonzero gap even with a good incumbent. No external MILP statistics are claimed.

## Baselines

`original_order_all_remaining_service` resumes after the furthest previously served original stop, requires the remaining original services, and allows current shortest safe road detours. If an original service is inaccessible, unreachable or filtered out, that baseline is infeasible. `fixed_normal_road_reference` preserves the normal shortest road paths between the same remaining original stops and marks closures infeasible. These are computed reference paths, not a supplied scheduled road shape. `shortest_terminal` and `shortest_safe_endpoint` add no service; the latter may be safe zero-movement waiting. All preserve actual completed history. Missing baselines have reasons, never invented travel times.
