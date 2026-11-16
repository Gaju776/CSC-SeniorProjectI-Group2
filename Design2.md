# Secure communication across UAVs and ground stations

**Author:** Dorcas Bwenge Gaju
**Course:** CSC 59866 Senior Project I, Fall 2026
**Last updated:** November 13, 2026 (Assignment 2)
**Status:** Sections 1 and 2 complete; Section 3 drafted; Sections 4 to 11 are work to come; Section 12 current.

## Progress note

**November 13.** This week I moved the document into the course's twelve-section structure. The scope, Semester II goal, and exclusions now sit in Section 1. I wrote the Section 2 specification: five functional requirements, three correctness rules, two proposed quality targets, assumptions, and constraints, each with an ID and an acceptance check. I drafted Section 3, which compares no protection (the baseline), MAVLink 2 signing, per-message authenticated encryption, and a DTLS 1.3 tunnel against the same requirements. While writing the requirements I learned that the six-week scope was still too broad, so I narrowed it to one protected command path. The main unresolved issue is the latency target for manual piloting (see the open question). Next step: select an approach and draw the architecture for Assignment 3.

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

*Draft for Assignment 2. The final selection and two decision records follow in Assignment 3.*

### 3.1 Approaches compared

| Approach | What it is |
| --- | --- |
| **A. No protection (baseline)** | Plain MAVLink, as most drones run today. Every other approach is measured against it. |
| **B. MAVLink 2 signing** | Built into ArduPilot and PX4. Adds a 13-byte signature and timestamp to each packet using one shared 32-byte key [2][3]. |
| **C. Per-message authenticated encryption** | Each MAVLink message is encrypted and given a check value before it is sent, similar to the MAVSec research prototype [5]. Candidate algorithms: Ascon-AEAD128 [7], ChaCha20-Poly1305, AES-GCM. |
| **D. Secure tunnel (DTLS 1.3)** | The whole MAVLink stream is carried inside a standard secure channel that first runs a handshake to set up keys [6]. |

### 3.2 Comparison against the same requirements

Each entry says whether the approach can meet the requirement, and where that judgment comes from: **(doc)** a source states it, **(judg.)** my judgment from reading, **(test)** still to be measured.

| Requirement | A. No protection | B. Signing | C. Per-message encryption | D. DTLS 1.3 tunnel |
| --- | --- | --- | --- | --- |
| F1 Enroll a drone | Nothing to enroll | Key loaded by hand; how it is delivered is left open (doc [3]) | Needs a key per drone; enrollment to be designed (judg.) | Handshake with pre-shared keys or certificates (doc [6]) |
| F2, F3 Commands and telemetry get through | Yes | Yes (doc [2]) | Yes in MAVSec tests (doc [5]) | Yes on IP links (doc [6]) |
| F4 Each drone accepts only its own messages | No | Not if all drones share one key (judg.) | Yes, with a separate key per drone (judg.) | Yes, one session per drone (judg.) |
| C1 Reject altered or unknown-sender messages | No | Yes (doc [2]) | Yes, if an authenticated mode is used (judg.) | Yes (doc [6]) |
| C2 Reject replayed commands | No | Timestamp-based; attacked through GPS time (doc [4]) | Needs a message counter; to be designed (judg.) | Optional feature that must be turned on (doc [6]) |
| C3 Content unreadable | No | No, messages stay readable (doc [2]) | Yes (doc [5]) | Yes (doc [6]) |
| Q1 Added delay | Baseline | Small (test) | Small processing cost in MAVSec (doc [5]); link delay (test) | Handshake plus per-packet cost (test) |
| Q2 Link use | Baseline | 13 extra bytes per packet (doc [2]) | More than signing (test) | More than signing, plus handshake traffic (test) |
| Works over a serial telemetry radio | Yes | Yes | Yes (judg.) | Designed for datagram networks such as IP, not serial radios (doc [6]; judg.) |
| Effort for six weeks | None | Configuration only | Moderate | Moderate to high (judg.) |

### 3.3 What the comparison shows so far

- **A** is needed only as a baseline. It fails every correctness rule.
- **B** meets C1 but fails C3 (nothing is hidden) and has a known weakness on C2. It is a useful second reference point because it already exists and adds a known 13 bytes.
- **C** and **D** are the two real candidates. Both can meet C1 and C3. C fits a serial radio more directly but leaves replay protection and enrollment for me to design. D brings a reviewed handshake and replay option but was designed for IP networks, which may not match a telemetry radio.
- The deciding questions are C2 (replay protection) and Q1/Q2 (cost on a slow link). These will drive the choice in Assignment 3.

### 3.4 Sources behind the comparison

- **MAVLink signing guide [3] and PX4 signing guide [2]** support every entry for approach B: what signing protects, the 13-byte size, the shared key, and that key delivery is left open.
- **Colton et al. [4]** supports the weakness of B on replay protection (C2).
- **MAVSec, Allouch et al. [5]** supports approach C: encryption can run on autopilot software, with measured processing and memory costs.
- **RFC 9147 [6]** supports approach D: its handshake, protection, optional replay detection, and design for datagram networks.
- **NIST SP 800-232 [7]** supports Ascon as a standardized lightweight option for C.

---

## 4 Architectural design

*Work to come (Assignment 3).* System context and the main running parts: GCS, protection layer, simulated link, and simulated drones; what I build, reuse, or simulate.

## 5 Component design and interfaces

*Work to come (Assignment 3).* Responsibilities inside the protection layer, and the interface for the critical operation: sending a protected command.

## 6 Data structure design

*Work to come (Assignment 4).* Keys, per-drone records, message counters, and what is saved across a restart.

## 7 Algorithm design and execution

*Work to come (Assignment 4).* Pseudocode for protecting and checking a message, with normal and interrupted sequences.

## 8 Failures and security

*Work to come (Assignment 4).* Adverse scenarios (link drop, drone reboot, failed check) and misuse cases. The drone must fall back to safe behavior and never fly uncontrolled.

## 9 Implementation and feasibility

*Work to come (Assignment 3 onward).* The smallest working path and a feasibility experiment.

## 10 Testing and verification

*Work to come (Assignment 4).* Test specifications linked to F1 to F5, C1 to C3, Q1, and Q2, with the unprotected baseline.

## 11 Operation, maintenance, and future work

*Work to come (Assignments 4 to 6).* Startup, diagnosis, recovery, one likely change, and Semester II milestones.

---

## 12 Revision history and references

### 12.1 Revision history

| Date | Change | Reason |
| --- | --- | --- |
| November 6, 2026 | First version: problem, stakeholders, workflow figure, evidence, scope, references. | Assignment 1. |
| November 13, 2026 | Moved to the twelve-section course structure; scope moved into Section 1.6; figure moved to `assets/`. | Match the course template and handbook. |
| November 13, 2026 | Narrowed the six-week scope to one protected command path with a normal and a replay case. Comparing all approaches by measurement was too large for six weeks; the comparison is now done against requirements in Section 3, and only the baseline and the selected approach will be measured. | Writing testable requirements showed the earlier scope could not be finished. |
| November 13, 2026 | Added Section 2 (requirements) and a draft of Section 3 (alternatives). | Assignment 2. |

### 12.2 Assistance disclosure

I used Claude, an AI assistant, to help find sources, organize sections, edit wording, and draw Figure 1. I checked the cited sources myself and can explain every part of this design.

### 12.3 References

**Starting source.** The MAVLink message signing guide [3] shows what existing protection does and what it leaves open. It authenticates messages with one shared key, but it does not encrypt them and does not define how keys reach the drone.

1. Y.-M. Kwon, J. Yu, B.-M. Cho, Y. Eun, and K.-J. Park, "Empirical Analysis of MAVLink Protocol Vulnerability for Attacking Unmanned Aerial Vehicles," *IEEE Access*, vol. 6, pp. 43203–43212, 2018. <https://scholar.dgist.ac.kr/handle/20.500.11750/9227>
2. PX4 Autopilot, "MAVLink Message Signing," *PX4 User Guide*. <https://docs.px4.io/main/en/mavlink/message_signing>
3. MAVLink Developer Guide, "Message Signing (Authentication)." <https://mavlink.io/en/guide/message_signing.html>
4. Z. Colton, A. Oracevic, and S. Dilek, "Timestamp Manipulation-Based GPS Spoofing Attacks on the MAVLink 2.0 Protocol for UAV Communication: An Empirical Study," University of Bristol. <https://research-information.bris.ac.uk/en/publications/timestamp-manipulation-based-gps-spoofing-attacks-on-the-mavlink-/>
5. A. Allouch, O. Cheikhrouhou, A. Koubaa, M. Khalgui, and T. Abbes, "MAVSec: Securing the MAVLink Protocol for Ardupilot/PX4 Unmanned Aerial Systems," in *Proc. International Wireless Communications and Mobile Computing Conference (IWCMC)*, June 2019. <https://cister-labs.pt/docs/mavsec__securing_the_mavlink_protocol_for_ardupilot_px4_unmanned_aerial_systems/1504/>
6. E. Rescorla, H. Tschofenig, and N. Modadugu, "The Datagram Transport Layer Security (DTLS) Protocol Version 1.3," IETF RFC 9147, April 2022. <https://www.rfc-editor.org/rfc/rfc9147.html>
7. National Institute of Standards and Technology, "NIST Finalizes 'Lightweight Cryptography' Standard to Protect Small Devices" (NIST SP 800-232), August 2025. <https://www.nist.gov/news-events/news/2025/08/nist-finalizes-lightweight-cryptography-standard-protect-small-devices>
8. Defense One, "US Drones May Soon Run on Open-Source Software," May 2019. <https://www.defenseone.com/technology/2019/05/us-drones-may-soon-run-open-source-software/156699/>
