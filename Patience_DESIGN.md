### Your Project Design

**Author:** Patience Divine Aimee IZERE  
**Course:** CSC 59866  
**Selected project and option:** Modeling, Analysis, and Control of Data Center Power Electronics Under AI Workload Dynamics
**Current assignment:** 2  
**Friday commit deadline:** November 13, 2026, at 11:59 p.m. New York time  
**Monday presentation:** November 16, 2026, at 6:30 p.m. New York time  
**Last updated:** November 13, 2026  
**Document status:** Revised and Ready for Review  

---

#### Progress note
During Assignment 2, I expanded the design from problem formulation to formal system specification and architectural evaluation. Addressing feedback from Monday's presentation, I clarified that this software investigation models converter dynamic interactions without claiming physical hardware validation. I specified four functional requirements (F1–F4) covering stochastic workload generation, reduced-order converter simulation, terminal impedance derivation, and Middlebrook resonance detection, alongside an energy-conservation correctness invariant (C1) and a 5.0-second impedance calculation quality target (Q1). In Section 3, I contrasted our proposed dynamic state-space framework against a static ZIP load baseline and switched SPICE models across these requirements. The main unresolved issue is selecting the optimal state-space model order to capture fast DC-bus transients without numerical solver stiffness. My immediate next step is defining component interfaces and data structures for Assignment 3.

**Open question:** Under what workload burst frequencies do converter feedback loops resonate with grid sub-synchronous modes to induce voltage sags?

---

#### Contents
* [1 Problem research and scope](#1-problem-research-and-scope)
* [2 Requirements and system specification](#2-requirements-and-system-specification)
* [3 Alternatives and selected solution](#3-alternatives-and-selected-solution)
* [4 Architectural design](#4-architectural-design)
* [5 Component design and interfaces](#5-component-design-and-interfaces)
* [6 Data structure design](#6-data-structure-design)
* [7 Algorithm design and execution](#7-algorithm-design-and-execution)
* [8 Failures and security](#8-failures-and-security)
* [9 Implementation and feasibility](#9-implementation-and-feasibility)
* [10 Testing and verification](#10-testing-and-verification)
* [11 Operation maintenance and future work](#11-operation-maintenance-and-future-work)
* [12 Revision history and references](#12-revision-history-and-references)

---

#### 1 Problem research and scope

##### Problem and affected people
The rapid proliferation of artificial intelligence (AI) training clusters, hyperscale cloud facilities, and high-density compute infrastructure is driving unprecedented localized electricity demand spikes across electric power grids. While data centers represent some of the largest single-point electrical loads connected to transmission and distribution networks, regional transmission operators (RTOs) and independent system operators (ISOs) do not directly observe raw computing task activity. Instead, compute power demand ($\Delta P_{\text{compute}}$) is filtered, buffered, and reshaped by internal data center power conversion stages, including alternating current to direct current (AC/DC) rectifiers, intermediate direct current to direct current (DC-DC) converters, fast closed-loop feedback controllers, and local energy storage buffers (Uninterruptible Power Supplies (UPS) and battery/supercapacitor banks), before reaching the Point of Common Coupling (PCC) at the utility grid interface.

Traditional grid planning, dynamic security assessment, and interconnection tools rely almost exclusively on static or heavily simplified load representations, such as constant impedance ($Z$), constant current ($I$), and constant power ($P$) ZIP load models. These static models assume slow, smooth load variations and fail to capture rapid, workload-driven dynamic load swings, multi-stage power converter feedback loop interactions, and non-linear dynamic impedance characteristics. Consequently, unmodeled dynamic interactions between AI workload spikes and converter control loops create critical operational risks for four primary stakeholder groups:

##### Stakeholder impact analysis
The following table summarizes the primary challenges, operational failure risks, and research solutions provided by this investigation for each affected stakeholder group.

| Stakeholder Group | Primary Challenge / Risk | Operational Consequence of Unmodeled Dynamics | Research Solution & Reference Link |
| ------ | ------ | ------ | ------ |
| **Grid Operators (ISOs / RTOs)** | Lack of dynamic load models for hyperscale data centers. | Incorrect voltage/frequency stability margins, unexpected tripping of grid protection relays, and unpredicted transient oscillations. | Supplies dynamic state-space load models and impedance profiles $Z_{in}(f)$ for dynamic security assessment [[1](#1-middlebrook-r-d-1976)] |
| **Data Center Facility Engineers** | Uncharacterized interactions between compute bursts and internal power infrastructure. | Thermal stress on conversion stages, harmonic distortion, transient voltage sags across internal DC buses, and unexpected UPS trip events. | Identifies internal converter resonances and stress points to optimize UPS buffering and control tuning [[2](#2-pratt-a-kumar-p--aldridge-t-2007)] |
| **Electric Utilities & Regulators** | Uncertainty during interconnection feasibility and impact studies. | Conservative interconnect limits, delayed approval timelines for data center interconnections, or risk of load curtailment. | Provides standardized dynamic impact evaluation tools that streamline interconnection approvals [[3](#3-ieee-power--energy-society-pes-2022)] |
| **Computing & AI System Architects** | Ignorance of grid-side electrical constraints when designing job schedulers. | Job execution delays, curtailment of cluster peak power capability, or operational inefficiency. | Delivers power-aware feedback to workload schedulers, aligning GPU cluster bursts with grid limits [[4](#4-us-national-science-foundation-nsf-2026)] |

##### Current workflow
Under current operational protocols, data center power interactions proceed through a sequence of uncoupled stages:

1. **Workload Dispatch:** AI cluster workload schedulers dispatch massive parallelized jobs (such as synchronous GPU training steps or large language model inference bursts), causing compute power consumption to ramp up or down by tens of megawatts within milliseconds.
2. **Internal Power Electronics Filtering:** The power transient flows into the data center internal distribution system, where AC/DC front-end rectifiers and intermediate DC-DC buck/boost converters adjust switching duty cycles under fast closed-loop control to regulate server voltage. Local UPS battery buffers engage to suppress DC-bus voltage dips.
3. **PCC Grid Point Injection:** The reshaped active and reactive power currents flow across the transformer interface at the PCC into the utility transmission network.
4. **Utility Grid Model Evaluation:** Utility energy management systems evaluate grid stability using static ZIP load models, assuming constant power draw or static impedance.

**The Failure Point:** Because static ZIP models ignore converter closed-loop bandwidths and energy buffer dynamics, they treat the data center as a passive static load block. In reality, fast closed-loop voltage regulation causes the converter input impedance $Z_{in}(f)$ to exhibit negative incremental resistance characteristics at low frequencies. When AI workload burst frequencies align with converter control bandwidths or grid network resonance modes, the unmodeled dynamic impedance triggers severe voltage sags and electrical oscillations at the PCC that utility operators cannot predict or prevent.

##### Operational workflow diagram

![Workflow diagram linking AI workload scheduling transients through multi-stage power electronics to PCC grid interface stability](assets/ai_load_to_grid_workflow.png)

*Figure 1. Operational workflow linking AI cluster workload scheduling transients ($\Delta P_{\text{compute}}$), multi-stage converter regulation ($\Delta V, \Delta I, Z_{\text{in}}$), and utility Point of Common Coupling grid interface stability ($V_{\text{PCC}}, f_{\text{PCC}}$).*

##### Concrete scenario
A hyperscale data center hosting a 50,000-GPU cluster initiates a synchronous pipeline-parallel large language model training iteration. Within 5 milliseconds, compute power demand ramps by 20 megawatts. As server-side voltage drops, the fast closed-loop controllers of intermediate DC-DC converters increase current draw to maintain constant power delivered to the GPUs. Simultaneously, the central AC/DC rectifier draws a heavy step-current from the utility substation, while the facility's supercapacitor/battery buffer kicks in to stabilize the internal 48-volt direct current bus.

Because the regional grid operator's dynamic security software models the data center using a static ZIP model, it expects a smooth, linear power change. However, the interaction between the converter's negative incremental input impedance and the utility grid's line inductance excites a 15 Hz sub-synchronous voltage oscillation at the 138 kV PCC substation. The unpredicted voltage sag trips distance protection relays on an adjacent transmission line, isolating a nearby industrial feeder and forcing the utility to temporarily curtail the data center's power allocation by 40%, abruptly interrupting the AI training run.

##### Evidence and assumptions

**Grounding Evidence:** This problem formulation and research framework are directly supported by foundational literature and industry standards:
* *Power Distribution Topologies:* Pratt et al. (2007) document multi-stage data center power distribution architectures, establishing the role of switching converters and Uninterruptible Power Supply buffers in reshaping load draws [[2](#2-pratt-a-kumar-p--aldridge-t-2007)].
* *Impedance Interaction Criteria:* Middlebrook (1976) formulated foundational input filter impedance criteria, proving that switching regulator closed-loop feedback loops induce negative input resistance that causes sub-synchronous resonance when filter/grid impedance matches converter input impedance [[1](#1-middlebrook-r-d-1976)].
* *Grid Interconnection Standards:* IEEE Standard 1547 and IEEE 2800 specify dynamic voltage/frequency ride-through and impedance stability requirements for inverter-based resources connected to utility grids [[3](#3-ieee-power--energy-society-pes-2022)].
* *Federal Research Framework:* The National Science Foundation (NSF) Division of Electrical, Communications, and Computing Systems (ECCS) Energy, Power, Control, and Learning (EPCL) program (Solicitation NSF 26-514) explicitly prioritizes research into dynamic modeling, control, and stability of power-electronic-dominated energy systems [[4](#4-us-national-science-foundation-nsf-2026)].

**Explicitly Labeled Assumptions:**
* *Assumption 1 (Grid Interface Representation):* The utility grid interface is initially modeled as a Single-Machine Infinite-Bus system with fixed nominal frequency (60 Hertz) and known grid short-circuit impedance ($Z_{\text{grid}}$).
* *Assumption 2 (Workload Stochasticity):* AI workload power demand follows a Markov-modulated Poisson process combined with heavy-tailed distributions representing synchronous batch dispatch steps.
* *Assumption 3 (Converter Model Order Reduction):* High-frequency switching dynamics (>100 kilohertz) are averaged over control switching periods to yield computationally tractable state-space dynamic models.

##### Six-week contribution (Semester I scope)
During the 6-week deliverable execution path, I will investigate and demonstrate a reduced-order mathematical and computational model in Python. Specifically, I will build:

1. A stochastic AI workload profile generator using **SimPy** to simulate bursty GPU cluster power demand transients ($\Delta P_{\text{compute}}$).
2. A reduced-order dynamic state-space model in **NumPy/SciPy/Control** representing a 3-stage power conversion system (AC/DC rectifier, DC-DC converter, and Uninterruptible Power Supply energy storage buffer).
3. An analytical module that computes the dynamic, frequency-dependent terminal input impedance $Z_{\text{in}}(f)$ at the Point of Common Coupling under stochastic workload bursts, proving the mathematical divergence between dynamic impedance and static ZIP load models.

These three capabilities map to functional requirements F1–F4, correctness rule C1, and proposed quality target Q1 in Section 2, and they will be compared against the static ZIP baseline under the same workload inputs.

##### Semester II scope
In Semester II, the completed project will expand this foundation into a comprehensive grid-scale dynamic stability framework by:

1. Interconnecting the reduced-order data center converter model with a multi-bus power system benchmark (IEEE 9-bus grid model).
2. Implementing Lyapunov-based transient stability assessment tools to evaluate large-signal grid dynamic responses during extreme compute surges.
3. Synthesizing adaptive closed-loop impedance-matching controllers and power-aware workload feedback mechanisms that dynamically adjust converter control parameters and job dispatch rates to guarantee grid interface stability.

##### Explicit exclusions
To maintain feasibility within a single-student academic project, the scope deliberately excludes:

* Physical fabrication or hardware testing of silicon power semiconductor devices (MOSFETs/IGBTs).
* Thermal dynamics and computational fluid dynamics (CFD) modeling of server room cooling and HVAC infrastructure.
* Multi-year transmission expansion planning and regional energy policy modeling.

---

#### 2 Requirements and system specification

To transition from problem understanding to concrete software engineering, the system specification establishes precise behavioral obligations, physical invariants, and performance targets. The software framework models the multi-stage conversion path from compute task dispatch to terminal grid impedance. Requirements are assigned permanent identifiers: functional requirements (F1–F4), a correctness rule (C1), and a measurable quality target (Q1).

##### Requirements specification
The table below specifies the required behaviors, conditions, acceptance checks, and forward design references. All abbreviations are defined within the text to ensure complete readability.

| Requirement ID | Required Behavior and Operational Conditions | Concrete Acceptance Check | Design and Test Reference |
| ------ | ------ | ------ | ------ |
| **F1** | The software must generate synthetic time-series power demand profiles $\Delta P_{\text{compute}}(t)$ representing bursty artificial intelligence cluster execution, with configurable job arrival rates, step amplitudes (1 to 50 megawatts), and burst durations (1 to 600 seconds) following a Markov-modulated Poisson process. | Execute a 60-second simulation run in SimPy; verify that the output time-series array contains step transients exceeding 10 megawatts with millisecond rise times, and verify statistical correlation matching configured distribution parameters. | Design Section 4; Test Plan T1 |
| **F2** | The software must solve dynamic ordinary differential equations modeling a three-stage power electronics conversion topology (front-end AC/DC rectifier, intermediate DC-DC stage, and local battery energy storage buffer) to compute state-variable trajectories (bus voltages and inductor currents) under dynamic workload injection. | Inject a 20-megawatt step transient into the state-space solver; verify that internal direct current bus voltages settle to steady state within 50 milliseconds without numerical divergence or unbounded oscillation. | Design Section 5; Test Plan T1 |
| **F3** | The software must derive the frequency-dependent complex terminal input impedance $Z_{\text{in}}(f)$ across a spectrum from 0.1 Hertz to 10 kilohertz by small-signal linearization of the state-space converter model around dynamic operating points. | Execute the impedance calculation across 100 logarithmic frequency bins; verify that output complex impedance vectors demonstrate negative incremental resistance (real part $\text{Re}(Z_{\text{in}}) < 0$) in the low-frequency control bandwidth range (1 to 50 Hertz). | Design Section 5; Test Plan T2 |
| **F4** | The software must evaluate the Middlebrook stability criterion by computing the ratio of grid source impedance to converter input impedance ($Z_{\text{grid}}(f) / Z_{\text{in}}(f)$), detecting sub-synchronous or super-synchronous resonance points where the impedance ratio magnitude exceeds unity ($|Z_{\text{grid}}/Z_{\text{in}}| \ge 1$) with phase margin less than 30 degrees. | Run comparative evaluation against an inductive utility grid model ($L_{\text{grid}} = 5\text{ mH}$); verify that the stability module flags the 15 Hertz sub-synchronous resonance condition observed in the concrete scenario. | Design Section 5; Test Plan T3 |
| **C1** | Physical energy balance and voltage positivity invariant: Across every simulated time interval $\Delta t$, the total energy delivered by the utility grid plus net energy discharged by the battery storage buffer must equal the sum of energy consumed by the computing workload, internal conversion losses, and stored reactive field energy (inductors and capacitors), with all direct current bus voltages remaining strictly positive ($V_{\text{DC}}(t) > 0$). | For any simulation run, evaluate energy balance conservation $\left|\int P_{\text{in}}\,dt - (\int P_{\text{compute}}\,dt + \Delta E_{\text{stored}} + \int P_{\text{loss}}\,dt)\right| / \int P_{\text{in}}\,dt < 0.01$; assert that any violation or negative bus voltage halts execution with an assertion failure. | Design Section 7; Test Plan T2 |
| **Q1 (Proposed)** | The software shall compute the complete state trajectory and evaluate terminal input impedance $Z_{\text{in}}(f)$ across 100 frequency bins for a 1,000-time-step workload trace in under 5.0 seconds of elapsed wall-clock time on reference commodity hardware (single CPU core, 16 gigabytes RAM). | Benchmark 10 consecutive executions on the reference hardware using identical synthetic workload inputs; record elapsed wall-clock execution time and verify that the 95th percentile (p95) execution latency is less than or equal to 5.0 seconds. | Design Section 7; Test Plan T4 |

##### Inputs and outputs

**Ordinary Input/Output Example:**
* *Input:* A simulation configuration file specifying:
  * Workload parameters: Duration = 10.0 seconds, baseline load = 10 megawatts, peak step = 30 megawatts at $t = 2.0$ seconds, burst duration = 3.0 seconds.
  * Converter parameters: Nominal AC voltage = 13.8 kilovolts, DC bus reference = 48 volts, rectifier filter inductance = 2.5 millihenries, DC bus capacitance = 150 millifarads, closed-loop voltage controller proportional-integral gains ($K_p = 0.8$, $K_i = 120.0$).
  * Grid impedance: Grid inductance $L_{\text{grid}} = 5.0$ millihenries, grid resistance $R_{\text{grid}} = 0.2$ ohms.
* *Expected Output:* A structured output dictionary and time-series record containing:
  * Dynamic state arrays: $V_{\text{DC}}(t)$ showing a transient sag from 48.0 volts to 44.2 volts, recovering to 48.0 volts within 38 milliseconds.
  * Active/reactive power waveforms at the Point of Common Coupling: $P_{\text{PCC}}(t)$ ramping from 10.2 megawatts to 30.6 megawatts with a 4-millisecond slew rate.
  * Frequency-dependent impedance array: 100 complex values $Z_{\text{in}}(f)$ from 0.1 Hertz to 10 kilohertz, identifying a negative resistance region between 2 Hertz and 45 Hertz with minimum real impedance of $-1.8$ ohms at 15 Hertz.
  * Stability outcome: Status = `RESONANCE_DETECTED`, Resonance Frequency = 15.2 Hertz, Phase Margin = 12.4 degrees, Severity Flag = `HIGH_VOLTAGE_SAG_RISK`.

**Unsuccessful Execution Example:**
* *Input:* A malformed configuration containing physically invalid or unstable parameter values:
  * Workload parameters: Peak step = $-25$ megawatts (unphysical negative power draw for a compute cluster).
  * Converter parameters: DC bus capacitance $C = -10$ millifarads (negative capacitance), or converter controller gains yielding positive real eigenvalues ($\text{Re}(\lambda_i) > 0$).
* *Expected System Behavior:* The input validator intercepts the configuration before state-space initialization. Execution halts immediately with a descriptive validation error (`InvalidParameterException: Workload power must be strictly non-negative; converter passive component parameters must be strictly positive-definite`). No corrupted output files or indeterminate mathematical states are generated.

##### Assumptions and verification
* **Assumption 1 (Grid Sizing and Substation Interface):** The utility grid Point of Common Coupling behaves as a Single-Machine Infinite-Bus system where frequency is regulated to 60 Hertz under nominal conditions, and grid impedance is dominantly inductive ($X/R$ ratio $\ge 10$).  
  *How to check:* Inspect regional interconnection study datasheets and configure grid short-circuit mega-volt-ampere parameters to match standard utility substation ratings.
* **Assumption 2 (Cycle-Averaged Power Electronics Dynamics):** High-frequency semiconductor switching harmonics (typically 100 to 500 kilohertz) do not directly couple with electromechanical grid stability modes (0.1 to 60 Hertz), allowing average-value state-space modeling.  
  *How to check:* Verify that the highest control loop bandwidth in the model remains below one-tenth of the switching frequency ($f_{\text{bw}} \le f_{\text{switch}} / 10$).
* **Assumption 3 (Battery Storage Response Rate):** Local Uninterruptible Power Supply battery and supercapacitor storage units possess sufficient discharge slew rates to supply power within 2 milliseconds of a compute surge command.  
  *How to check:* Review manufacturer specifications for high-rate lithium-ion Uninterruptible Power Supply systems and enforce ramp-rate saturation limits in the simulation solver.

##### Constraints
* **Constraint 1 (Development and Runtime Environment):** All software components must execute entirely in Python 3.12 using open-source scientific packages (SimPy for discrete-event workload generation, NumPy and SciPy for numerical state-space integration, and Python-Control for frequency-domain impedance calculations). No proprietary tools (such as MATLAB/Simulink or PSCAD) are permitted.
* **Constraint 2 (Single-Student Resource Budget):** Investigation scope is strictly bounded to a single academic semester (14 weeks total, with a 6-week deliverable execution path), precluding real-world hardware testbed construction or physical facility sensor instrumentations.
* **Constraint 3 (Offline Air-Gapped Operation):** The simulation environment runs entirely offline without relying on external cloud application programming interfaces, live grid telemetry feeds, or commercial grid management licenses.

---

#### 3 Alternatives and selected solution

To achieve the requirements established in Section 2, multiple modeling and analytical approaches were evaluated. The core design challenge is balancing modeling fidelity—capturing the fast closed-loop control dynamics that produce negative incremental resistance—against computational tractability during long multi-step workload simulations.

##### Comparison of candidate approaches
The following table compares three architectural alternatives against the requirements defined in Section 2: a simple static baseline, a highly detailed switched circuit simulation, and the proposed reduced-order dynamic state-space framework.

| Approach and Source | Useful Behavior | Limitation | Evidence or Assumption | Comparison Against Requirements |
| ------ | ------ | ------ | ------ | ------ |
| **Approach 1: Static Polynomial Load Baseline (Static ZIP Model)**<br>*Source: Pratt et al. (2007) [[2](#2-pratt-a-kumar-p--aldridge-t-2007)]* | Extremely low computational overhead; instantaneous algebraic evaluation; natively supported by all legacy utility power flow software. | Treats data center as static algebraic load; completely ignores converter control loop bandwidths, battery buffer dynamics, and frequency-dependent impedance. | Supported by Pratt et al. (2007) documentation of traditional data center utility planning models. | **Fails F2, F3, F4, C1.** Cannot compute dynamic states, yields constant static impedance, fails to predict 15 Hz resonance. Satisfies Q1 (<0.01s). |
| **Approach 2: Switched Circuit Non-Linear Emulation (Detailed SPICE / Simscape)**<br>*Source: Middlebrook (1976) [[1](#1-middlebrook-r-d-1976)]* | Captures exact semiconductor switching transients, gate-drive non-linearities, and microsecond-level parasitics with maximum physical fidelity. | Massive computational penalty; stiff numerical integration requires nanosecond time steps, causing simulation runtimes of hours for multi-second traces; intractable for grid studies. | Supported by Middlebrook (1976) analysis of switching circuit simulation intractability. | **Satisfies F1, F2, F3, F4, C1.** Severely **fails Q1** (elapsed execution time exceeds 300 seconds for a 10-second workload trace). |
| **Approach 3: Reduced-Order Dynamic State-Space Framework (Selected Candidate)**<br>*Sources: Middlebrook (1976) [[1](#1-middlebrook-r-d-1976)]; Pratt et al. (2007) [[2](#2-pratt-a-kumar-p--aldridge-t-2007)]; Åström & Murray (2021) [[6](#6-astrom-k-j-and-murray-r-m-2021)]* | Captures multi-stage converter regulation, closed-loop negative resistance, and frequency-dependent impedance $Z_{\text{in}}(f)$ while averaging out switching ripple. | Requires mathematical state-space derivation and small-signal linearization around moving operating points. | Supported by Middlebrook (1976) input filter impedance criteria, Pratt et al. (2007) multi-stage distribution topologies, and standard state-space controls methods [6]. | **Satisfies F1, F2, F3, F4, C1, and Q1.** Captures dynamic resonance while executing in < 5.0 seconds. |

##### Analytical justification and source evidence
The evaluation demonstrates that the static ZIP model (Approach 1) is fundamentally incapable of satisfying the project requirements because it omits the physical differential equations that govern converter control loops and local battery buffers. While static models satisfy the computational speed target (Q1), they create the very operational blind spot documented in Section 1: regional grid operators cannot detect negative incremental resistance or predict resonance conditions.

Conversely, detailed switched circuit models (Approach 2) capture switching phenomena with high fidelity but suffer from extreme numerical stiffness. Simulating a 50,000-GPU cluster over several minutes of AI training iterations requires billions of numerical time steps, making grid-level parameter sweeps and real-time security assessment computationally intractable.

Approach 3 (Reduced-Order Dynamic State-Space Modeling) achieves the optimal engineering compromise. By cycle-averaging switching dynamics while retaining the continuous differential equations of converter feedback controllers and energy storage buffers, Approach 3 captures the low-frequency impedance behavior ($Z_{\text{in}}(f)$ from 0.1 Hertz to 10 kilohertz) where sub-synchronous grid resonance occurs, while satisfying the 5.0-second execution target (Q1).

*The formalized selection and two architectural decision records follow in Deliverable 3 (Assignment 3).*

##### Decision 1
**Work to come in Deliverable 3.**

##### Decision 2
**Work to come in Deliverable 3.**

---

#### 4 Architectural design

**Work to come — due Friday, November 20, 2026 (Deliverable 3; presentation November 23).** I will add a context/architecture diagram showing the simulation components, their responsibilities, and labeled data flows.

---

#### 5 Component design and interfaces

**Component responsibility table:** *Work to come in Deliverable 3.*  
**Critical operation contract:** *Work to come in Deliverable 3.*  
**Inputs, outputs, and errors:** *Work to come in Deliverable 3.*  
**Repeated or overlapping calls:** *Work to come in Deliverable 3.*  

---

#### 6 Data structure design

**Work to come — due Friday, November 27, 2026 (Deliverable 4; presentation November 30).** I will define the records for workload profiles, converter state variables, impedance sweep results, and comparison outputs.

---

#### 7 Algorithm design and execution

**Work to come — due Friday, November 27, 2026 (Deliverable 4; presentation November 30).** I will add pseudocode for the simulation pipeline and explain normal and interrupted sequences.

---

#### 8 Failures and security

**Adverse scenarios and expected behavior:** *Work to come in Deliverable 4.*  
**Plausible misuse cases:** *Work to come in Deliverable 4.*  
**Selected prototype demonstration:** *Work to come in Deliverable 4.*  

---

#### 9 Implementation and feasibility

**Minimal path:** *Work to come in Deliverables 3–5.*  
**Feasibility experiment:** *Work to come in Deliverables 3–5.*  
**Current implementation status:** *Phase 1 active (literature synthesis, mathematical formulation, and specification).*  
**Run instructions and continuous integration:** *Work to come in Deliverables 5–6.*  

---

#### 10 Testing and verification

**Test specifications:** *Work to come in Deliverables 4–5.*  
**Baseline and comparison method:** *Work to come in Deliverables 4–5.*  
**Benchmark measurements:** *Work to come in Deliverables 5–6.*  

---

#### 11 Operation maintenance and future work

**Startup and diagnosis:** *Work to come in Deliverables 5–6.*  
**Recovery procedures:** *Work to come in Deliverables 5–6.*  
**Future change and rollback plan:** *Work to come in Deliverable 6.*  
**Semester II milestones:** *Work to come in Deliverable 6.*  

---

#### 12 Revision history and references

##### Revision history
The following table documents the design evolution across course milestones.

| Revision Date | Changes to Design Document | Reason and Supporting Evidence |
| ------ | ------ | ------ |
| November 5, 2026 (Initial) | Created initial Section 1 problem formulation, operational scope, concrete scenario, stakeholder impact table, progress note, and foundational references. | Initial submission for Deliverable 1 meeting CSC 59866 schedule requirements. |
| November 5, 2026 (Revision) | Refined problem narrative, added operational workflow context diagram (Figure 1), expanded stakeholder needs links, and updated Section 12 listings. | Incorporated visual diagram requirements and handbook template alignment. |
| November 13, 2026 (Assignment 2) | Formalized Section 2 system specification with four functional requirements (F1–F4), an energy-balance correctness invariant (C1), and a proposed latency target (Q1); completed inputs/outputs examples, assumptions, and constraints. Drafted Section 3 comparing the proposed dynamic state-space approach against static ZIP and switched SPICE models. Updated progress note, revision history, and references. | Deliverable 2: requirements and possible solutions. |

##### Open questions
The following table tracks active engineering uncertainties, their architectural significance, and planned actions.

| Open Question | Why It Matters | Next Action |
| ------ | ------ | ------ |
| Under what workload burst frequencies do converter feedback loops resonate with grid sub-synchronous modes? | Identifies critical oscillation risks and voltage instability points before grid deployment. | Formulate frequency-sweep simulation scenarios in prototype testing (Deliverables 4–5). |
| What state-space model order provides sufficient transient fidelity without introducing excessive numerical stiffness into the ordinary differential equation solver? | Balances simulation execution speed (Q1) against accuracy in capturing DC-bus voltage dips during 20 MW compute steps. | Conduct numerical step-response feasibility spike in Assignment 3 (Section 9). |

##### Assistance and reuse
This design document synthesizes research and state-space modeling formulations authored by Patience Divine Aimee IZERE for CSC 59866. Python code development will reuse open-source libraries including SimPy (v4.1.2), NumPy, SciPy, and Control under standard academic license terms. No proprietary simulation software or uncredited external designs are used.

##### References
1. <a id="1-middlebrook-r-d-1976"></a> **Middlebrook, R. D.** (1976). "Input Filter Considerations in Design and Application of Switching Regulators." *IEEE Power Electronics Specialists Conference (PESC)*, pp. 366–382. [Semantic Scholar Record](https://www.semanticscholar.org/paper/Input-filter-considerations-in-design-and-of-Middlebrook/22397996af080102703615bbf902bfbe48868300). Supports Section 1 impedance interaction problem, Section 2 requirements F3–F4, and Section 3 architectural comparison.
2. <a id="2-pratt-a-kumar-p--aldridge-t-2007"></a> **Pratt, A., Kumar, P., & Aldridge, T.** (2007). "Power Distribution Topologies for Modern Data Centers." *IEEE Transactions on Power Electronics*, vol. 22, no. 3, pp. 1012–1018. [IEEE Xplore Record](https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=63). Supports Section 1 distribution architectures, Section 2 requirement F2, and Section 3 baseline ZIP comparison.
3. <a id="3-ieee-power--energy-society-pes-2022"></a> **IEEE Power & Energy Society (PES)** (2022). *IEEE Standard 1547-2018 / IEEE Standard 2800-2022 for Interconnection and Interoperability of Distributed Energy Resources and Large Inverter-Based Resources*. IEEE. [IEEE Standards](https://standards.ieee.org/ieee/2800/). Supports Section 1 grid compliance standards and Section 2 requirements C1 and F4.
4. <a id="4-us-national-science-foundation-nsf-2026"></a> **U.S. National Science Foundation (NSF)** (2026). Directorate for Engineering (ENG), Division of Electrical, Communications, and Computing Systems (ECCS). *Energy, Power, Control, and Learning (EPCL) Program Guidelines*. Solicitation NSF 26-514. [NSF Funding Record](https://www.nsf.gov/funding/opportunities/epcl-energy-power-control-learning). Supports Section 1 scientific problem significance and research framework.
5. <a id="5-simpy-development-team-2024"></a> **SimPy Development Team** (2024). *SimPy: Process-based Discrete-Event Simulation Framework in Python (v4.1.2)*. [SimPy Documentation](https://simpy.readthedocs.io/). Supports Section 1 scope and Section 2 requirement F1.
6. <a id="6-astrom-k-j-and-murray-r-m-2021"></a> **Åström, K. J., & Murray, R. M.** (2021). *Feedback Systems: An Introduction for Scientists and Engineers*, 2nd ed. Princeton University Press. [Free online edition](https://fbsbook.org). Supports the state-space modeling and feedback-control methods used in the selected approach (Section 3).

##### Supporting media and evidence
* **Workflow Diagram (Figure 1):** `assets/ai_load_to_grid_workflow.png` — Visual schematic illustrating the sequence from AI cluster workload dispatch through multi-stage power electronic conversion to utility PCC grid interface.

##### Final document check
* [ ] Terms and examples make the project understandable to a beginner.
* [ ] All twelve sections contain project-specific content.
* [ ] Requirements connect to design and tests.
* [ ] Architecture, components, data, and algorithms agree.
* [ ] Targets and plans are separate from observations.
* [ ] Tables, images, pseudocode, references, and evidence links render correctly.
* [ ] Images have alternative text, captions, and readable labels.
* [ ] Run instructions and evidence support reproduction.
* [ ] I am prepared to present my work and orally review the same selected group mate.
* [ ] Remaining work and maintenance needs are explicit.
* [ ] Instructional placeholders are removed from the final submission.
