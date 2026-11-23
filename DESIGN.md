# Secure communication across UAVs and ground stations

**Author:** Dorcas Bwenge Gaju
**Course:** CSC 59866 Senior Project I, Fall 2026
**Last updated:** November 22, 2026 (Assignment 3)
**Status:** Sections 1 to 5 complete; Section 9 started; Sections 6 to 8, 10, and 11 are work to come; Section 12 current.

## Progress note

**November 22.** This week I selected a solution and designed how its parts work together. I chose per-message authenticated encryption with a separate key for each drone, recorded in two decision records, and placed it in a proxy at each end of the link so the GCS software and autopilot stay unchanged. Sections 4 and 5 now show the context and architecture views, a component table, and the contract for delivering a protected command. For Section 9 I ran a feasibility experiment on replay protection. I learned that a strict counter wrongly rejects late packets and that a restart lets old commands through again, so the design now uses a 64-message window and saved counters. The main unresolved issue is bandwidth: three drones with one flown by hand may exceed the 80% target. Next step: connect the proxies to an autopilot simulator.

## Open question

What added delay is acceptable before an approach is too slow? Manual piloting, where the operator reacts in real time, probably needs a tighter limit than an autonomous mission that follows uploaded waypoints. Q1 in Section 2 uses a proposed value until I find a better basis. I plan to check how often autopilots expect manual control messages and when their link-loss failsafes trigger, and to look for published studies on control delay.

## Contents

1. [Problem research and scope](#1-problem-research-and-scope)
2. [Requirements and system specification](#2-requirements-and-system-specification)
3. [Alternatives and selected solution](#3-alternatives-and-selected-solution)
4. [Architectural design](#4-architectural-design)
5. [Component design and interfaces](#5-component-design-and-interfaces)
6. [Data structure design](#6-data-structure-design)
7. [Algorithm design and execution](#7-algorithm-design-and-execution)
8. [Failures and security](#8-failures-and-security)
9. [Implementation and feasibility](#9-implementation-and-feasibility)
10. [Testing and verification](#10-testing-and-verification)
11. [Operation, maintenance, and future work](#11-operation-maintenance-and-future-work)
12. [Revision history and references](#12-revision-history-and-references)

---

## 1 Problem research and scope

### 1.1 Who has the problem

Teams that fly small unmanned aerial vehicles (UAVs, or drones) for search and rescue, inspection, mapping, agriculture, and delivery. More of these teams now fly several drones at once, sometimes from more than one ground control station (GCS). The drones may do different jobs at the same time. Some flights are autonomous, and others are flown by hand.

The people affected are the operators at the GCS, the organization that owns the drones and the mission data, and the people on the ground under the flight path. The systems involved are the flight controller on each drone and the GCS software.

| Stakeholder | What they need | What goes wrong today |
| --- | --- | --- |
| Operator running autonomous missions | Only their GCS can change the mission, and the telemetry on screen is real | Commands are accepted without any check unless signing is turned on |
| Operator piloting by hand | The same protection, plus a quick response between their input and the drone | Any delay added by security is felt directly in control |
| Organization or client | Routes, sites, and the operator's location stay private | Telemetry is sent as readable data that anyone in range can receive |
| People and property under the flight path | The drone is not taken over or made to behave unsafely | A forged or replayed command can stop a mission or change the drone's behavior |
| Autopilot and GCS developers | Protection that is easy to set up and light on the radio link | Key creation and delivery are left to each implementation |

### 1.2 Current workflow

1. Before the flight, the operator connects the GCS software to each drone over a telemetry radio, Wi-Fi, a cellular network, or a satellite link.
2. For an **autonomous** flight, the operator uploads a mission (a list of waypoints) and mostly watches telemetry. For a **manual** flight, the operator sends control inputs continuously, so delay matters more.
3. During the flight, the GCS sends commands such as take off, change the mission, or return home. Each drone keeps sending back telemetry: position, battery level, and mission status.
4. These messages use the MAVLink protocol, which the ArduPilot and PX4 autopilots use. *(Documented [1][3])*
5. If the team turned on MAVLink 2 message signing, both sides hold the same 32-byte secret key and each packet carries a 13-byte signature. If signing is off, which is the default in PX4, nothing is checked. *(Documented [2][3])*

![Diagram of the current workflow. An operator's ground control station on the left sends commands to three drones on the right over one shared link, and the drones send telemetry back. Below the link, a person within radio range can read the telemetry because it is not encrypted, and can replay or forge commands if signing is off. A note on the left says MAVLink has no encryption and signing is optional. A note on the right states the Semester I contribution: compare existing protection options on this same link.](assets/uav-gcs-workflow.png)

*Figure 1. Current workflow for a team flying three drones from one ground station, showing where an outsider can interfere. Sketch by the author; editable source in [assets/uav-gcs-workflow.svg](assets/uav-gcs-workflow.svg).*

### 1.3 The difficulty

- **No encryption.** MAVLink sends every message as readable data. Anyone within radio range, or anyone on the network path for cellular and satellite links, can read positions, missions, and battery levels. *(Documented [2])*
- **Signing is optional and limited.** Signing proves who sent a message but does not hide it. It is off by default in PX4, and the specification leaves key creation and delivery to each implementation. *(Documented [2][3])*
- **Protection has a cost.** Signing adds 13 bytes to every packet, and encryption adds more. How much this matters depends on packet size and available bandwidth. On a slow radio shared by several drones, this overhead, the processing it needs, and the work of managing keys may explain why protection is often left off. *(13 bytes: Documented [2]. Reasons: Assumed, A1)*
- **No built-in key lifecycle.** Signing does not handle key rotation, revocation, or recovery by itself. In PX4 the key is stored on the drone's SD card, and changing it needs a message signed with the current key. *(Documented [2])*
- **The replay protection has been attacked.** Signing relies on timestamps, and researchers broke this protection by manipulating GPS time without knowing the key. *(Documented [4])*
- **Several drones make keys harder.** If all drones share one key, losing one drone exposes the others. *(Assumed, A3)*

### 1.4 Concrete scenario

*Illustrative scenario. The team is invented; the weaknesses it shows are documented in the sources.*

A volunteer search-and-rescue team flies three drones over a forest to find a missing hiker. Drones 1 and 2 fly autonomous search patterns. The operator flies Drone 3 by hand to look closely under the trees. All three are controlled from one laptop GCS at the trailhead over one telemetry radio.

- **With signing off (the PX4 default).** Someone parked nearby with an inexpensive radio receiver can see each drone's live position and the search pattern. They can also record a "return to launch" command and send it again later, pulling a drone off the search. Research has shown that attacks of this kind can stop a drone's ongoing mission [1].
- **With signing on and one shared key.** The replayed command is now rejected. But Drone 2 crashes in the forest and someone recovers it. PX4 stores the signing key on the drone's SD card [2], and the same key works for Drones 1 and 3.
- **With full encryption.** Outsiders can no longer read telemetry. But every packet is larger, and three drones share one slow radio. If the link fills up, Drone 3's manual control starts to lag, which is risky close to trees.
- **What the team needs.** Protection that hides and checks every message, keeps working when a drone is lost, and still leaves enough bandwidth and speed for manual control.

### 1.5 Evidence and assumptions

| # | Statement | Label | Source |
| --- | --- | --- | --- |
| E1 | MAVLink is widely used for GCS-based drone control, and its weaknesses can be used to disable a drone's ongoing mission. | Documented | [1] |
| E2 | MAVLink 2 signing gives authentication and integrity only. Messages stay readable, and signing is off by default in PX4. | Documented | [2] |
| E3 | Signing adds a 13-byte signature to every MAVLink 2 packet. | Documented | [2] |
| E4 | PX4 stores the signing key on the drone's SD card. Changing or disabling the key needs a message signed with the current key. | Documented | [2] |
| E5 | Key generation is left to each implementation. The specification recommends that the GCS share the key over a secure link. | Documented | [3] |
| E6 | Researchers attacked MAVLink 2 signing by manipulating GPS-based timestamps, without knowing the key. | Documented | [4] |
| E7 | Researchers added encryption to MAVLink in a modified version of ArduPilot. Of four ciphers tested, ChaCha20 used the least processing power and memory. | Documented | [5] |
| E8 | DTLS 1.3 is a standard secure channel for datagram traffic; its replay detection is optional. | Documented | [6] |
| E9 | The US Defense Innovation Unit funded cybersecurity improvements to the open-source PX4 autopilot. | Reported | [8] |
| A1 | Operators leave signing and encryption off because of bandwidth overhead, processing cost, and the work of managing keys. | Assumed | To test |
| A2 | With several drones on one radio, the extra bytes from protection matter more than the processing cost on each drone. | Assumed | To test |
| A3 | There is no widely adopted method for managing a separate key for each drone in a MAVLink fleet. | Assumed | Not found so far |
| A4 | Manual piloting is more sensitive to added delay than autonomous missions. | Assumed | To test |

### 1.6 Scope

**Problem statement.** For drone teams that control one or more drones from a ground station, readable and easily forged MAVLink messages let an outsider track missions or interfere with a flight. My project will investigate how to protect commands and telemetry between one GCS and its drones so that messages cannot be read, altered, faked, or replayed, while keeping the added delay and bandwidth small enough for manual piloting.

**Six-week contribution.** One protected command path, from one GCS to simulated drones:

- **Operation:** the GCS sends a protected command to an enrolled drone, the drone acts on it, and the drone's protected telemetry reaches the GCS.
- **Normal case:** a valid command is accepted and acknowledged.
- **Adverse case:** a captured command is replayed later and is rejected without changing the drone's behavior.
- **Inputs:** one GCS, one to three simulated drones, test keys only, and a simulated link with added delay, loss, and a bandwidth limit.
- **Measurement:** added delay and added bytes per message, compared with the unprotected baseline.

**Semester II goal.** A complete protection layer for one or more drones and ground stations that adds key changes during a mission, cutting off a lost or captured drone without grounding the others, recovery after a dropped link or reboot, and tests with 5 and 10 simulated drones. Handing a drone from one GCS to another is a stretch goal.

**Out of scope.**

- Real flights and real drone hardware; all testing is in simulation.
- Designing a new encryption or key-exchange algorithm.
- Key rotation, revocation, recovery, and handover this semester (moved to Semester II).
- Video streams and other payload data; only command and telemetry messages are covered.
- Defending against radio jamming, or GPS spoofing of the drone's navigation.
- Securing the GCS computer itself, such as malware or operator accounts.
- Large swarms and drone-to-drone mesh networks.
- Military systems and export-controlled technology.
- Aviation certification and regulation.

---

## 2 Requirements and system specification

The requirements below describe what the protected link must do, not how it does it. The mechanism is chosen in Section 3. IDs stay fixed so later sections and tests can refer to them. **F** marks a functional requirement, **C** a correctness rule that must never be broken, and **Q** a quality target. Every check below is *planned*; none has been run yet.

### 2.1 Functional requirements

| ID | Required behavior | How to check it (acceptance check) |
| --- | --- | --- |
| F1 | Before flight, a drone can be **enrolled** with the GCS so that the two can exchange protected messages. | Enroll one test drone, then send one command and confirm it is accepted. |
| F2 | The GCS can send a **command** (for example "return to launch") to an enrolled drone, and the drone acts on it and sends back an acknowledgment. | Send the command; confirm the simulated drone changes mode and the GCS receives the acknowledgment. |
| F3 | An enrolled drone's **telemetry** (position, battery, mode) reaches the GCS with the same values the drone sent. | Compare the values logged on the drone with the values shown at the GCS for 100 messages. |
| F4 | The GCS can work with **up to three drones at once**, and each drone accepts only messages meant for it. | Run three drones; send a command addressed to Drone 2 and confirm only Drone 2 acts. |
| F5 | Every **rejected** message is logged with the time, the drone, and the reason (altered, unknown sender, or replayed). | Trigger each rejection type once and inspect the log. |

### 2.2 Correctness rules

These must hold in every run, not just most runs. A system could satisfy them by rejecting everything, which is why F2 and F3 require that valid messages still get through.

| ID | Rule that must never be broken | How to check it |
| --- | --- | --- |
| C1 | A drone **never acts on an altered message** or on a message from a device that was not enrolled. | Change bytes in a captured command and resend it; send a command from an unenrolled test device. Both must be rejected, and the drone's mode must not change. |
| C2 | A drone **never acts on the same command twice.** A recorded valid command sent again later is rejected. | Capture a valid command, resend it 30 seconds later, and confirm it is rejected and logged. Repeat after restarting the GCS software. |
| C3 | **No command or telemetry content can be read** by someone who captures the traffic without the key. | Capture all traffic on the simulated link and try to decode it with a standard MAVLink decoder; no field values may be recovered. |

### 2.3 Quality targets (proposed)

Both targets are **proposed** values. Neither has been measured. I will revise them after measuring the unprotected baseline, and record the reason for any change.

| ID | Measure | Proposed target | Conditions |
| --- | --- | --- | --- |
| Q1 | Delay added by protection to a command, from the GCS sending it to the drone accepting it | At least 95 of 100 commands arrive no more than **50 ms** later than the same commands without protection | Three simulated drones on the simulated radio link described in A6; commands that time out count as misses |
| Q2 | Share of link capacity used by three drones' telemetry and commands | Stays **below 80%** of the link's capacity | Same link and message rates as the unprotected baseline |

**Why these values.** The 50 ms value is a starting point chosen to stay well below the reaction time of a human pilot; it is not based on a measurement yet (see the open question). The 80% limit leaves room for bursts and retransmissions on a shared radio.

**Evidence so far (Section 9).** Q1: with the selected approach, one command takes 3.5 ms longer on a 57.6 kbit/s link than without protection; the proxy hop is not measured yet. Q2: three drones on one shared channel are projected to use 71.9% of the link if all fly autonomously and 86.8% if one is flown by hand, so Q2 is at risk in the hand-flown case. Both values stay proposed until measured with an autopilot simulator.

### 2.4 Example inputs and outputs

**Ordinary case (F2).** The operator tells Drone 1 to return home during a search.

```text
Input   GCS -> Drone 1   command: RETURN_TO_LAUNCH   (protected, message #1042)
Output  Drone 1          switches to return-to-launch mode
        Drone 1 -> GCS   acknowledgment: ACCEPTED    (protected)
        Observer         sees only unreadable bytes on the link
```

**Unsuccessful case (C2).** An outsider recorded message #1042 and sends the same bytes again 30 seconds later, after the operator has sent Drone 1 back to its search.

```text
Input   Outsider -> Drone 1   exact copy of message #1042
Output  Drone 1               rejects it and keeps searching
        Drone 1 log           "14:02:31 rejected: replayed message"
        GCS                   no change; operator sees a warning count go up
```

### 2.5 Assumptions

| ID | Assumption | How I will check it |
| --- | --- | --- |
| A5 | The GCS computer and the drone's software are not themselves compromised; the attacker only has access to the link. | Stated as a boundary; revisited in Section 8. |
| A6 | A simulated link with added delay, loss, and a bandwidth limit similar to a telemetry radio (about 57,600 bits per second) is close enough to show relative costs between approaches. | Compare against published telemetry-radio settings before measuring. |
| A7 | Keys can be installed safely while the drone is on the ground, over a cable or in person, before flight. | Stated as a boundary; secure enrollment over the air is not attempted. |
| A8 | The simulated drones send telemetry at rates similar to a real autopilot's default settings. | Check the simulator's default message rates against autopilot documentation. |

### 2.6 Constraints

- Everything must run on a student laptop, in simulation, with free and open-source software.
- Only existing, standardized encryption algorithms may be used ([7] and [6] list candidates).
- The GCS software and autopilot must still receive normal MAVLink messages after protection is removed, so existing tools keep working.
- The six-week work is limited to one GCS and one to three drones.

---

## 3 Alternatives and selected solution

### 3.1 Approaches compared

| Approach | What it is |
| --- | --- |
| **A. No protection (baseline)** | Plain MAVLink, as most drones run today. Every other approach is measured against it. |
| **B. MAVLink 2 signing** | Built into ArduPilot and PX4. Adds a 13-byte signature and timestamp to each packet using one shared 32-byte key [2][3]. |
| **C. Per-message authenticated encryption** | Each MAVLink message is encrypted and given a check value before it is sent, similar to the MAVSec research prototype [5]. Candidate algorithms: Ascon-AEAD128 [7], ChaCha20-Poly1305 [9], AES-GCM. |
| **D. Secure tunnel (DTLS 1.3)** | The whole MAVLink stream is carried inside a standard secure channel that first runs a handshake to set up keys [6]. |

### 3.2 Comparison against the same requirements

Each entry says where it comes from: **(doc)** a source states it, **(judg.)** my judgment from reading, **(exp.)** measured in the feasibility experiment in Section 9, with the test ID. D was compared on paper only.

| Requirement | A. No protection | B. Signing | C. Per-message encryption | D. DTLS 1.3 tunnel |
| --- | --- | --- | --- | --- |
| F1 Enroll a drone | Nothing to enroll | Key loaded by hand; delivery left open (doc [3]) | One key per drone, installed on the ground (A7); enrollment step still to design | Handshake with pre-shared keys or certificates (doc [6]) |
| F2, F3 Commands and telemetry get through | Yes (exp. T1) | Yes (exp. T1) | Yes (exp. T1) | Yes on IP links (doc [6]) |
| F4 Each drone accepts only its own messages | No (exp. T6) | No with one shared fleet key (exp. T6) | Yes, separate key per drone (exp. T6) | Yes, one session per drone (judg.) |
| C1 Reject altered or unknown-sender messages | No (exp. T2, T3) | Yes (exp. T2, T3) | Yes (exp. T2, T3) | Yes (doc [6]) |
| C2 Reject replayed commands | No (exp. T4) | Yes (exp. T4), but rejected 47 of 1,000 valid late messages (exp. T8); timestamps attacked through GPS time (doc [4]) | Yes with a 64-message window and saved counters (exp. T4, T8, T9) | Optional feature that must be turned on (doc [6]) |
| C3 Content unreadable | No (exp. T5) | No, latitude readable (exp. T5) | Yes (exp. T5) | Yes (doc [6]) |
| Q1 Time on the link for one command at 57.6 kbit/s | 7.8 ms (exp.) | 10.1 ms (exp.) | 11.3 ms, 3.5 ms more than A (exp.) | Not measured; handshake plus per-record cost |
| Q2 Bytes added per message | 12 (exp.) | 25 (exp.) | 32 (exp.) | Not measured; record header and tag on top of the MAVLink frame (doc [6]) |
| Works over a serial telemetry radio | Yes | Yes | Yes | Designed for datagram networks such as IP (doc [6]; judg.) |

### 3.3 Selected solution

I selected **approach C: per-message authenticated encryption, with a separate key for each drone, a 4-byte message counter checked against a 64-message replay window, and counters saved across restarts.** ChaCha20-Poly1305 is the provisional cipher.

**Why.** C is the only approach that met every correctness rule in the experiment (C1, C2, C3) and the per-drone requirement F4. B blocks forgeries but leaves positions readable (C3 fails) and, as usually deployed, uses one key for the whole fleet (F4 fails). D could meet the security rules, but it needs an IP link and a handshake that must restart after a dropped connection, which does not fit a serial telemetry radio and would take most of the six weeks to set up. A stays as the baseline for every measurement.

**What it costs.** C adds 32 bytes per message, compared with 12 for A and 25 for B. That is about 3.5 ms more link time per command, far below the 50 ms target in Q1. It is harder on Q2: on one shared 57.6 kbit/s channel, three drones with one flown by hand are projected to use 86.8% of the link (Section 9.3). This is the main risk I carry forward.

### 3.4 Decision record 1: protection approach

| | |
| --- | --- |
| **Context** | The project must make commands and telemetry unreadable, unforgeable, and not replayable (C1 to C3) on a slow serial radio, for one to three drones, within six weeks. |
| **Options** | A. No protection. B. MAVLink 2 signing. C. Per-message authenticated encryption. D. DTLS 1.3 tunnel. |
| **Choice** | C, with a separate key per drone, a 64-message replay window, saved counters, and ChaCha20-Poly1305 as the provisional cipher. |
| **Reasons** | Only C passed tests T1 to T9 in the experiment. It works over a serial link without a handshake. ChaCha20 was the most efficient cipher on autopilot hardware in MAVSec [5]. |
| **Consequences** | +32 bytes per message, which puts Q2 at risk on a shared channel. I must design key enrollment and counter saving myself, because no standard covers them for MAVLink. The message format is my own, so it needs careful review. |
| **Reconsider if** | The target drones use IP links and DTLS overhead is measured as acceptable; the 32 bytes make Q2 impossible even with lower telemetry rates; or ChaCha20 is too slow on a flight controller, in which case Ascon-AEAD128 [7] or AES-GCM is compared. |

### 3.5 Decision record 2: where the protection runs

| | |
| --- | --- |
| **Context** | The protection has to sit somewhere between the GCS software and the autopilot. Constraint 2.6 requires that existing GCS software and autopilots keep receiving normal MAVLink. |
| **Options** | (a) Change the autopilot firmware, as MAVSec did [5]. (b) Change the GCS software. (c) Run a separate proxy at each end of the link: one on the operator laptop, one on each drone. |
| **Choice** | (c) A proxy at each end. Plain MAVLink stays inside each machine; only protected frames cross the link (Figures 2 and 3). |
| **Reasons** | It works with unmodified ArduPilot or PX4 and unmodified GCS software. It is small enough to build and test in six weeks. The same proxy code serves both ends. |
| **Consequences** | One extra hop at each end, which adds delay I still need to measure. On a real drone it needs a small companion computer between the radio and the flight controller. Plain MAVLink still flows between the proxy and the autopilot inside the drone, which is acceptable under assumption A5. |
| **Reconsider if** | The target drones have no companion computer; the proxy hop pushes command delay past Q1; or an autopilot adds built-in encryption that meets C1 to C3. |

### 3.6 Sources behind the comparison

- **MAVLink signing guide [3] and PX4 signing guide [2]** support every entry for approach B: what signing protects, the 13-byte size, the shared key, and that key delivery is left open.
- **Colton et al. [4]** supports the weakness of B on replay protection (C2).
- **MAVSec, Allouch et al. [5]** supports approach C and decision 2(a): encryption can run on autopilot software, and ChaCha20 was the most efficient cipher there.
- **RFC 9147 [6]** supports approach D: its handshake, protection, optional replay detection, and design for datagram networks.
- **NIST SP 800-232 [7]** supports Ascon as the alternative cipher for C.
- **RFC 8439 [9]** supports the rule that a ChaCha20-Poly1305 nonce must never repeat under the same key, which is why counters must be saved.
- **My experiment (Section 9)** supports every entry marked (exp.).

---

## 4 Architectural design

### 4.1 Context view

![Context view. The operator uses unchanged GCS software, which sends plain MAVLink to a GCS-side proxy on the same machine. The GCS-side proxy and a drone-side proxy form the secure link layer built in this project, connected by a protected, simulated radio link. The drone-side proxy passes plain MAVLink to an unchanged autopilot running in a simulator, for one to three drones. Keys are enrolled into both proxies on the ground before flight. An outsider in radio range can listen to, alter, replay, or forge messages on the link.](assets/context-view.png)

*Figure 2. Context view: what the secure link layer connects to. Editable source: [assets/context-view.svg](assets/context-view.svg).*

The operator keeps using normal GCS software, and the autopilot is unchanged. The project adds a secure link layer between them. Keys are installed in both proxies on the ground before flight (assumption A7). The outsider can reach only the radio link; the GCS computer and the drone's own software are assumed to be safe (assumption A5).

### 4.2 Architecture view

![Architecture view. On the operator laptop, GCS software talks plain MAVLink over local UDP to the GCS-side proxy, which contains a protector, a checker, a replay guard, and a router that picks each drone's key. It saves a key table, a counter file, and an event log. Protected frames pass through a link emulator that simulates a 57.6 kbit/s radio with delay, 10 percent loss, and late packets. An attack test harness taps the emulator. On each of one to three simulated drones, a drone-side proxy with a checker, replay guard, and protector talks plain MAVLink over local UDP to an unchanged autopilot simulator, and saves its own key, counter file, and event log.](assets/architecture-view.png)

*Figure 3. Architecture view: running parts, where they run, how they communicate, and what they save. Editable source: [assets/architecture-view.svg](assets/architecture-view.svg).*

| Part | Responsibility | Runs on | Talks to | Saved state | Build, reuse, or simulate |
| --- | --- | --- | --- | --- | --- |
| GCS software | Operator sends commands and sees telemetry | Operator laptop | GCS-side proxy (plain MAVLink, local UDP) | Its own settings only | Reuse, unchanged |
| GCS-side proxy | Protects commands to each drone; checks and decrypts telemetry; logs rejections | Operator laptop | GCS software; link emulator (protected frames) | Key table, counter file, event log | Build |
| Link emulator | Stands in for the radio: bandwidth limit, delay, loss, late packets, one shared channel | Operator laptop | Both proxies (protected frames over UDP) | None | Build (simulates the radio) |
| Attack test harness | Captures, alters, replays, and forges frames for tests T2 to T9 | Operator laptop | Link emulator | Captured frames for the test run | Build (test only) |
| Drone-side proxy | Checks and decrypts commands; drops bad ones; protects telemetry; logs rejections | Each drone (a companion computer on a real drone) | Link emulator; autopilot (plain MAVLink, local UDP) | This drone's key, counter file, event log | Build |
| Autopilot | Flies the drone and acts on commands | Each drone | Drone-side proxy | Its own parameters | Reuse, run in a simulator (for example ArduPilot SITL [11]) |

### 4.3 Communication

- **Inside one machine:** plain MAVLink over local UDP, between the GCS software and the GCS-side proxy, and between the drone-side proxy and the autopilot. It never leaves the machine.
- **Across the link:** only protected frames. In the simulator, UDP stands in for the serial radio, and the link emulator applies the radio's limits.
- **Protected frame layout:** the 10-byte MAVLink header (readable for routing, but covered by the authentication check), a 4-byte counter, the encrypted payload, a 16-byte authentication tag, and a 2-byte CRC. That is 32 bytes more than the payload, compared with 12 for plain MAVLink.

### 4.4 What I build, reuse, or simulate

- **Build:** both proxies (shared code), the link emulator, the attack test harness, and the key and counter files.
- **Reuse:** GCS software, the autopilot, and the `cryptography` library for ChaCha20-Poly1305 and AES-GCM.
- **Simulate:** the drones (autopilot simulator), the radio (link emulator), and the attacker (test harness).

---

## 5 Component design and interfaces

### 5.1 Component responsibilities

Both proxies are built from the same components.

| Component | Responsibility | State it reads or changes |
| --- | --- | --- |
| Frame reader | Reads plain MAVLink from the local side, or protected frames from the link, and finds frame boundaries | None |
| Router | Picks the key and counter record for the drone a frame is addressed to or comes from | Reads the key table |
| Protector | Adds the next counter, encrypts the payload, and adds the authentication tag | Increases and saves the sent counter |
| Replay guard | Rejects a counter that is too old or already seen; accepts late packets inside a 64-message window | Reads, then updates, the received counter and window |
| Checker | Checks the tag and decrypts the payload; rejects anything that fails | None directly; tells the replay guard to record a counter only after a frame passes |
| Forwarder | Sends accepted plain MAVLink to the local side, or protected frames to the link | None |
| Event log | Records every rejected frame with time, drone, and reason (F5) | Appends to the log file |
| Key and counter store | Loads keys at startup; saves counters so they survive a restart | Key table file, counter file |

### 5.2 Interface contract: deliver a protected command (OP-1)

**Linked requirements:** F2 (a command reaches the drone and is acknowledged), C1 (altered or unknown-sender frames rejected), C2 (replays rejected), C3 (content unreadable), and F5 (rejections logged). Telemetry from the drone uses the same two calls in the opposite direction.

**Calls.**

```text
GCS-side proxy:    protect(drone_id, mavlink_frame)  -> protected_frame | error
Drone-side proxy:  accept(protected_frame)           -> (ACCEPTED, mavlink_frame) | (REJECTED, reason)
```

| | `protect` (GCS side) | `accept` (drone side) |
| --- | --- | --- |
| **Input** | Drone ID (MAVLink system ID, 1 to 3) and one plain MAVLink 2 frame from the GCS software | One protected frame from the link |
| **Preconditions** | The drone is enrolled (its key is in the key table); the counter file is loaded | This drone's key and counter file are loaded |
| **Output** | Protected frame: header, counter, encrypted payload, tag, CRC (payload + 32 bytes) | On success, the original plain MAVLink frame, forwarded to the autopilot |
| **State changes** | Sent counter for that drone increases by 1 and is saved before the frame is sent | Only if the frame passes every check: received counter and window updated and saved. A rejected frame changes nothing. |
| **Errors** | `UNKNOWN_DRONE`: no key for that ID; nothing is sent and the error is logged | `MALFORMED`: not a valid frame. `NOT_PROTECTED`: plain MAVLink arrived on the link. `REPLAYED`: counter too old or already seen. `AUTH_FAILED`: tag check failed (altered frame or wrong key). Each is logged and nothing is forwarded. |

**Successful example (F2).**

```text
GCS software -> GCS proxy   COMMAND_LONG RETURN_TO_LAUNCH, target drone 1   (45 bytes, plain)
GCS proxy                   drone 1 sent counter 1041 -> 1042, saved
GCS proxy -> link           header | counter 1042 | encrypted payload | tag | CRC   (65 bytes)
Drone 1 proxy               counter 1042 is new; tag valid; decrypts
Drone 1 proxy -> autopilot  original 45-byte COMMAND_LONG; drone switches to return-to-launch
                            received counter 1042 recorded and saved
```

**Unsuccessful example: replay (C2).**

```text
Attacker -> link            exact copy of the 65-byte frame with counter 1042, sent 30 s later
Drone 1 proxy               counter 1042 already seen -> REJECTED, REPLAYED
Event log                   "14:02:31 drone 1 rejected: REPLAYED (counter 1042)"
Autopilot                   receives nothing; state unchanged
```

**Unsuccessful example: altered frame (C1).**

```text
Attacker -> link            the same frame with one bit changed in the encrypted payload
Drone 1 proxy               tag check fails -> REJECTED, AUTH_FAILED; counter not recorded
```

**Still being worked out.**

- How often counters are saved: after every message, or by reserving a block of counters at a time and skipping ahead after a restart (Sections 6 and 7).
- The key file format and the exact enrollment step for F1.
- What the drone does after many rejections in a row, so it never flies uncontrolled (Section 8).
- How many messages per second one proxy can handle before it adds noticeable delay; to be measured in step 6 of Section 9.1.

---

## 6 Data structure design

*Work to come (Assignment 4).* Keys, per-drone records, message counters, and what is saved across a restart.

## 7 Algorithm design and execution

*Work to come (Assignment 4).* Pseudocode for protecting and checking a message, with normal and interrupted sequences.

## 8 Failures and security

*Work to come (Assignment 4).* Adverse scenarios (link drop, drone reboot, failed check) and misuse cases. The drone must fall back to safe behavior and never fly uncontrolled.

## 9 Implementation and feasibility

### 9.1 Smallest implementation path

Each step adds one thing to a path that already runs from end to end.

| Step | What it adds | Status |
| --- | --- | --- |
| 1 | Protect and check one command with a fixed test key, in a stand-alone program | Done in the experiment |
| 2 | Counter and 64-message replay window; event log of rejections | Done in the experiment |
| 3 | Attack tests T1 to T9 on a simulated link | Done in the experiment (Section 9.2) |
| 4 | Proxies pass plain MAVLink unchanged between real GCS software and one autopilot simulator | Next |
| 5 | Turn on protection in the proxies; the GCS controls the drone and a replayed command is rejected | Next |
| 6 | Three drones with separate keys through the link emulator; measure delay, link use, and proxy throughput | After step 5 |
| 7 | Save counters to disk; repeat T9 with a real restart | After step 6 |

### 9.2 Feasibility experiment: can replay protection work on an unreliable link?

**Question.** Can a counter-based replay check reject every replayed command (C2) without rejecting valid messages when packets are lost or arrive late, and does it still work after the drone restarts?

**Why this uncertainty.** Section 3 named C2 as the deciding question. If replay protection either let replays through or rejected good messages on a poor radio, approach C would not be usable, and the architecture would need a different design.

**Procedure.** I wrote a small stand-alone Python test program that builds MAVLink 2 frames following the MAVLink serialization rules [10] and runs each approach through the same tests on a simulated link, with a fixed random seed (20261119) so the results repeat exactly.

1. Capture a valid RETURN_TO_LAUNCH command, let five more messages pass, then resend it (T4).
2. Send 1,000 attitude messages with 10% randomly lost (T7).
3. Send 1,000 attitude messages where 5% swap places with the next one, so they arrive late (T8).
4. Restart the drone-side checker, once with its counter kept only in memory and once with it saved, then resend a command captured before the restart (T9).

I ran this for no protection (A), signing (B), and approach C with a strict counter (C1) and with a 64-message window (C2).

**Evidence.** Results of the run:

| Test | A. None | B. Signing | C1. Strict counter | C2. 64-message window |
| --- | --- | --- | --- | --- |
| T4 Replayed command rejected | FAIL (accepted) | PASS | PASS | PASS |
| T7 Valid messages wrongly rejected at 10% loss | 0 of 897 | 0 of 897 | 0 of 897 | 0 of 897 |
| T8 Valid messages wrongly rejected when 5% arrive late | 0 of 1,000 | 47 of 1,000 | 47 of 1,000 | 0 of 1,000 |
| T9 Replay after restart, counter kept in memory | | | | FAIL (old command accepted) |
| T9 Replay after restart, counter saved | | | | PASS |

**Finding.** Replay protection is feasible, but only with two features I had not planned. A strict counter, like signing's strict timestamp, wrongly rejected 4.7% of valid messages when some arrived late; a 64-message window removed those errors and still rejected every replay. And if the drone forgets its counter on restart, an old command is accepted again. The same problem on the sender side would be worse: a counter that restarts at zero reuses nonces, which breaks ChaCha20-Poly1305 [9].

**Decision.** The design uses a 64-message replay window, and both proxies save their counters before using them (Sections 3.4 and 5.2). Saving counters became a requirement of the key and counter store. How often to save them is still open (Section 5.2).

**Limits.** The link was simulated in software, not a radio; timing was not part of this test; and the restart was simulated by clearing the checker's memory. Step 7 repeats T9 with a real process restart.

### 9.3 Second check: bytes on the link (Q2)

Using the same test program and an assumed telemetry mix of 24 messages per second per drone, plus 20 manual-control messages per second for one hand-flown drone:

| Three drones on one shared 57.6 kbit/s channel | A. None | B. Signing | C. Selected |
| --- | --- | --- | --- |
| All autonomous | 46.9% | 63.1% | 71.9% |
| One flown by hand | 54.9% | 75.6% | 86.8% |

C meets Q2 when all drones fly autonomously but not when one is flown by hand, under the worst-case assumption that all drones share one channel. **Decision:** keep Q2 at 80% for now, and replace the assumed telemetry rates with measured ones in step 6. If Q2 still fails, I will test lower telemetry rates before changing the message format.

## 10 Testing and verification

*Work to come (Assignment 4).* Test specifications linked to F1 to F5, C1 to C3, Q1, and Q2, with the unprotected baseline. Tests T1 to T9 from Section 9.2 will become part of this suite.

## 11 Operation, maintenance, and future work

*Work to come (Assignments 4 to 6).* Startup, diagnosis, recovery, one likely change, and Semester II milestones.

---

## 12 Revision history and references

### 12.1 Revision history

| Date | Change | Reason |
| --- | --- | --- |
| November 6, 2026 | First version: problem, stakeholders, workflow figure, evidence, scope, references. | Assignment 1. |
| November 13, 2026 | Moved to the twelve-section course structure; scope moved into Section 1.6; figure moved to `assets/`. | Match the course template and handbook. |
| November 13, 2026 | Narrowed the six-week scope to one protected command path with a normal and a replay case. | Writing testable requirements showed the earlier scope could not be finished. |
| November 13, 2026 | Added Section 2 (requirements) and a draft of Section 3 (alternatives). | Assignment 2. |
| November 22, 2026 | Completed Section 3 with a selection and two decision records; added Sections 4 and 5 with context and architecture views, a component table, and the OP-1 contract; started Section 9 with the implementation path, the replay experiment, and a bandwidth check. | Assignment 3. |
| November 22, 2026 | Updated the Section 3.2 comparison with measured results; added evidence notes to Q1 and Q2 in Section 2.3. | Keep sections consistent with the experiment. |

### 12.2 Response to feedback

| Feedback received | What I changed | Where | Status |
| --- | --- | --- | --- |
| Narrow the project scope | Six-week work limited to one protected command path for one GCS and up to three simulated drones | Section 1.6 | Done |
| Define measurable performance criteria | Requirements with IDs and acceptance checks; targets Q1 and Q2; tests T1 to T9 with recorded results | Sections 2 and 9.2 | Done; Q1 and Q2 values still proposed |
| Compare existing approaches before selecting one | Four approaches compared against the same requirements, then a selection backed by measured results | Sections 3.2 to 3.5 | Done |
| Measure bandwidth, latency, packet loss, and processing as the fleet grows | Bytes and link time per message, link use for three drones, behavior at 10% loss | Sections 3.2, 9.2, 9.3 | Partly done: processing on real hardware and measured telemetry rates are still open |
| Cover both autonomous and manually piloted operation | Q1 targets manual control; bandwidth checked for all-autonomous and one-hand-flown cases | Sections 2.3, 9.3 | Done |
| Check behavior when a link drops, a drone reboots, or keys change | Tested loss, late packets, and restart; added saved counters to the design | Sections 9.2, 5.2 | Key changes are still unresolved and planned for Semester II |

**Unresolved items.** The latency target for manual piloting (open question), Q2 under a shared channel (Section 9.3), how often counters are saved (Section 5.2), and key changes and revocation (Semester II).

### 12.3 Assistance disclosure

I used Claude, an AI assistant, to help find sources, organize sections, edit wording, draw the figures, and write the test program used in Section 9. I ran the test program, checked its results against the tables in this document, checked the cited sources, and can explain every part of this design.

### 12.4 References

**Starting source.** The MAVLink message signing guide [3] shows what existing protection does and what it leaves open. It authenticates messages with one shared key, but it does not encrypt them and does not define how keys reach the drone.

1. Y.-M. Kwon, J. Yu, B.-M. Cho, Y. Eun, and K.-J. Park, "Empirical Analysis of MAVLink Protocol Vulnerability for Attacking Unmanned Aerial Vehicles," *IEEE Access*, vol. 6, pp. 43203–43212, 2018. <https://scholar.dgist.ac.kr/handle/20.500.11750/9227>
2. PX4 Autopilot, "MAVLink Message Signing," *PX4 User Guide*. <https://docs.px4.io/main/en/mavlink/message_signing>
3. MAVLink Developer Guide, "Message Signing (Authentication)." <https://mavlink.io/en/guide/message_signing.html>
4. Z. Colton, A. Oracevic, and S. Dilek, "Timestamp Manipulation-Based GPS Spoofing Attacks on the MAVLink 2.0 Protocol for UAV Communication: An Empirical Study," University of Bristol. <https://research-information.bris.ac.uk/en/publications/timestamp-manipulation-based-gps-spoofing-attacks-on-the-mavlink-/>
5. A. Allouch, O. Cheikhrouhou, A. Koubaa, M. Khalgui, and T. Abbes, "MAVSec: Securing the MAVLink Protocol for Ardupilot/PX4 Unmanned Aerial Systems," in *Proc. International Wireless Communications and Mobile Computing Conference (IWCMC)*, June 2019. <https://cister-labs.pt/docs/mavsec__securing_the_mavlink_protocol_for_ardupilot_px4_unmanned_aerial_systems/1504/>
6. E. Rescorla, H. Tschofenig, and N. Modadugu, "The Datagram Transport Layer Security (DTLS) Protocol Version 1.3," IETF RFC 9147, April 2022. <https://www.rfc-editor.org/rfc/rfc9147.html>
7. National Institute of Standards and Technology, "NIST Finalizes 'Lightweight Cryptography' Standard to Protect Small Devices" (NIST SP 800-232), August 2025. <https://www.nist.gov/news-events/news/2025/08/nist-finalizes-lightweight-cryptography-standard-protect-small-devices>
8. Defense One, "US Drones May Soon Run on Open-Source Software," May 2019. <https://www.defenseone.com/technology/2019/05/us-drones-may-soon-run-open-source-software/156699/>
9. Y. Nir and A. Langley, "ChaCha20 and Poly1305 for IETF Protocols," IETF RFC 8439, June 2018. <https://www.rfc-editor.org/rfc/rfc8439.html>
10. MAVLink Developer Guide, "Packet Serialization." <https://mavlink.io/en/guide/serialization.html>
11. ArduPilot Dev Team, "SITL Simulator (Software in the Loop)." <https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html>
