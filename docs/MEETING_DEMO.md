# Meeting demonstration for Dr Anmol Pahwa

Allow about eight minutes. Start the app with `./launch.command`, or use `./.venv/bin/python -m streamlit run app.py` from this folder. All examples are synthetic. The CLI alternative is `python3 demo_replanning.py` followed by `python3 verify.py`.

## 1 Explain the revised decision

“We now choose optional stop services, actual safe road connections and one safe finish from the bus's real position. Important stops have higher priorities. We charge for exceeding the duration targets and missing the original terminal. Safety is still a hard rule. The old Wang replication and the earlier hard-constraint notebook remain unchanged.”

Open Model notes → FORMULATION. Explain u as service, x as connection, r as endpoint, terminal arrival as the terminal's endpoint indicator, and the three nonnegative excess times. The independent solver uses subsets to solve the same elementary service-path problem without an external optimization package.

## 2 Check one decision by hand

Load `12_hand_check`, then select Run routing model in the sidebar. Its normal clinic connection is 1.5+1.5 road minutes plus 1 dwell, giving the fixed normal all-stop reference of 4. The disrupted clinic roads each take 4 minutes:

* Direct to finish: 4 running minutes, no service, no lateness penalty, objective 0.
* Visit clinic then finish: 4+4 running plus 1 dwell = 9 minutes; reward 5; time charge 2*(9-4)=10; objective -5.
* Stay safely: no new reward and terminal charge 6; objective -6.

The optimum is direct finish, score 0. Load `13_priority_change`: clinic priority 3 gives reward 15; the same 10-point time charge gives score 5, so the clinic is now served. Load `14_penalty_change`: original reward 5 and rate 0.5 gives penalty 2.5 and score 2.5, also serving the clinic. Save each result for comparison. Kappa=0 would make safe waiting score 0; the shorter-time secondary objective chooses it. A finite priority is a trade-off, not guaranteed service.

## 3 Show the supervisor feedback cases

Load `03_detour`: main2 is closed; the selected journey uses school–junction–hospital. The fixed normal-road baseline is infeasible, while the rerouted original-service baseline and shortest terminal path exist.

Load `04_unsafe_priority`: hospital boarding is unsafe even at priority 100; it is excluded from service, while the bus can legally pass its node. The result explains the hard exclusion.

Load `05_terminal_alternative`: terminal node is unsafe; the bus safely finishes at layby and pays kappa once. Load `06_overtime`: the 8-minute trip exceeds the 4-minute T_max target but remains feasible and reports all three penalties.

Load `08_safe_stranded` and `09_unsafe_no_escape`: the first has audited safe waiting; the second has no safe plan and requires intervention. Load `11_unsafe_verified_escape` to show that a supplied certified escape can change that outcome. Solver status and operational outcome are different fields.

## 4 Execute and replan twice

Load `01_normal`, run, and open Journey history. Execute events through school_stop service. The school service is now fixed, elapsed is 3 minutes and its 12 proxy units cannot be collected again.

In Edit inputs close main2, apply and run. The prefix stays purple; only the remaining journey changes to the junction detour. Execute through hospital_stop service. Close main3 and set hospital wait_safe=false, leaving hospital transit_safe=true and layby eligible. Apply and run again: the bus goes to layby. Previously served proxy is 22 and newly served proxy is zero. Export the input and result. The prepackaged `07_midtrip` provides a shorter locked-history demonstration; `demo_replanning.py` saves the full three-stage sequence and checks it automatically.

## 5 State the evidence and limits

Open results/VERIFICATION.md. The packaged scenarios, exhaustive tiny-route oracle, seeded directed/undirected networks, independent road reconstruction, history preservation, input rejection, and interface tests are reproducible. The old eight-stop written example still scores 181 at 39 minutes.

“We have verified the mathematics and implementation on synthetic data. We still need operational data and agreement on safe endpoints, service order, demand interpretation and penalty calibration. This is event-boundary snapshot replanning, not a prediction model or a real-world validated control system.”
