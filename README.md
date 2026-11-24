# FloodRoute UGRP routing lab

An interactive flood-aware bus rerouting prototype for the UGRP project with Dr Anmol Pahwa. All packaged networks, demand and safety inputs are **synthetic**.

## Run locally

Use Python 3.13 and install the interface dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

The routing solver and command-line examples use only Python's standard library:

```sh
python3 run_scenario.py examples/03_detour.json
python3 -m unittest discover -s tests -v
.venv/bin/python -m unittest discover -s tests_ui -v
```

## Deploy on Streamlit Community Cloud

Select this repository, branch `main`, main file `app.py`, and Python 3.13 in Advanced settings. `requirements.txt` and `.streamlit/config.toml` are included. No secrets or external datasets are required. Only the application, synthetic examples, documentation and tests are included here.

## Use the app

Choose an example in the sidebar and select **Run routing model**. The Route overview shows the road journey and recommended operational outcome. Edit demand, priorities, dwell, road times/closures and independent stop/node safety in **Edit inputs**, then **Apply inputs**. Results include time accounting, separate penalties, baselines, decision variables and scenario comparisons. **Journey history** commits an executed event prefix and preserves it through repeated disruption updates. Inputs, results and comparisons can be exported.

Old result formats are cleared safely after an app update; completed journey history remains fixed. A cloud browser refresh or disconnected session can reset session state, so export a scenario to save a journey between sessions. Uploads are processed within the viewer's app session and are not written to this repository by the application.

The interactive app accepts up to 50 stops, 1,000 nodes and 5,000 roads, with a 60-second search limit and up to 500,000 generated states. The subset search is exponential; larger candidate sets may return only a verified feasible incumbent. The programmatic solver has configurable limits. The time limit is checked between state expansions after preprocessing, not a strict kill deadline.

## Model and verification

The model chooses optional stop services, certified road connections and one safe endpoint from the actual bus position. Important stops use priorities; trip-time targets and terminal non-arrival are penalized. Safety remains hard. Explicit service alone earns demand, and already served demand is never collected again. Original service order is relaxed; physical nodes may repeat; safe terminal arrival ends the trip. Unsafe-origin departure requires supplied verified escape movements.

[Full formulation](docs/FORMULATION.md) · [Input schema and history](docs/INPUT_FORMAT.md) · [Assumptions and limits](docs/LIMITATIONS.md) · [Meeting walkthrough](docs/MEETING_DEMO.md)

Verification includes independent road-event auditing, exhaustive tiny-network service enumeration, 15 saved scenarios, 60 seeded directed/undirected networks, two successive history-preserving updates, invalid-input rejection, resource limits and a UI regression reproducing the stale `decisions` result error.

Demand served is a **stop-access service proxy**, not passengers carried. No capacity, passenger destinations, flood prediction, real-world safety certification or empirical validation is claimed. This is snapshot replanning at executed-event boundaries.
