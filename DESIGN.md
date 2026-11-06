# Secure communication across UAVs and ground stations

**Author:** Dorcas Bwenge Gaju
**Course:** Senior Project I
**Last updated:** November 6, 2026
**Status:** Draft for the November 9 review. Sections 1, 2 and 12 are complete, and Section 10 has an initial draft. The other sections are marked as work to come.

---

## Progress note

**November 9.** I wrote the first full draft of Section 1 (who has the problem) and Section 2 (what I will and will not do). I added a workflow figure, a stakeholder table, an evidence table, and linked sources.

After feedback on my findings report, I made three changes:

1. **Narrower scope.** This semester is now a comparison of existing ways to protect drone-to-GCS messages, with one GCS and up to three simulated drones. Building per-drone key management moved to Semester II.
2. **Measurable criteria.** Section 2.2 lists what I will measure: security tests, bandwidth use, latency, packet loss, and processing cost.
3. **Two kinds of flight.** Every comparison will cover both autonomous missions and manually piloted flight, since they put different demands on the link.

I have not chosen an algorithm, autopilot, or simulator yet. The comparison is how I will choose.

## Open question

What added delay is acceptable before an approach is "too slow"? The answer is probably different for manual piloting, where the operator reacts in real time, than for an autonomous mission that follows uploaded waypoints. I need a target for each before I can rank the approaches. I plan to look at how often autopilots expect manual control messages and when their link-loss failsafes trigger, and at published studies on control delay.

---

## 1. Problem and users

### 1.1 Who has the problem

Teams that fly small unmanned aerial vehicles (UAVs, or drones) for search and rescue, inspection, mapping, agriculture, and delivery. More of these teams now fly several drones at once, sometimes from more than one ground control station (GCS). The drones may be doing different jobs at the same time, and some flights are autonomous while others are flown by hand.

The people affected are the operators at the GCS, the organization that owns the drones and the mission data, and the people on the ground under the flight path. The systems involved are the flight controller on each drone and the GCS software.

| Stakeholder | What they need | What goes wrong today |
| --- | --- | --- |
| Operator running autonomous missions | Only their GCS can change the mission, and the telemetry on screen is real | Commands are accepted without any check unless signing is turned on |
| Operator piloting by hand | The same protection, plus a quick response between their input and the drone | Any added delay from security is felt directly in control |
| Organization or client | Routes, sites, and the operator's location stay private | Telemetry is sent as readable data that anyone in range can receive |
| People and property under the flight path | The drone is not taken over or made to behave unsafely | A forged or replayed command can stop a mission or change the drone's behavior |
| Autopilot and GCS developers | Protection that is easy to set up and light on the radio link | Key creation and delivery are left to each implementation |

### 1.2 Current workflow

1. Before the flight, the operator connects the GCS software to each drone over a telemetry radio, Wi-Fi, a cellular network, or a satellite link.
2. For an **autonomous** flight, the operator uploads a mission (a list of waypoints) and mostly watches telemetry. For a **manual** flight, the operator sends control inputs continuously, so delay matters more.
3. During the flight, the GCS sends commands such as take off, change the mission, or return home. Each drone keeps sending back telemetry: position, battery level, and mission status.
4. These messages use the MAVLink protocol, which the ArduPilot and PX4 autopilots use. *(Documented [1][3])*
5. If the team turned on MAVLink 2 message signing, both sides hold the same 32-byte secret key and each packet carries a 13-byte signature. If signing is off, which is the default in PX4, nothing is checked. *(Documented [2][3])*

![Diagram of the current workflow. An operator's ground control station on the left sends commands to three drones on the right over one shared link, and the drones send telemetry back. Below the link, a person within radio range can read the telemetry because it is not encrypted, and can replay or forge commands if signing is off. A note on the left says MAVLink has no encryption and signing is optional. A note on the right states the Semester I contribution: compare existing protection options on this same link, measuring security, bandwidth, delay, packet loss, and processing.](images/uav-gcs-workflow.png)

*Figure 1. Current workflow for a team flying three drones from one ground station, showing where an outsider can interfere. Sketch by the author.*

### 1.3 The difficulty

- **No encryption.** MAVLink sends every message as readable data. Anyone within radio range, or anyone on the network path for cellular and satellite links, can read positions, missions, and battery levels. *(Documented [2])*
- **Signing is optional and limited.** Signing proves who sent a message but does not hide it. It is off by default in PX4, and the specification leaves key creation and delivery to each implementation. *(Documented [2][3])*
- **Protection has a cost.** Signing adds 13 bytes to every packet, and encryption adds more. How much this matters depends on packet size and the bandwidth available. On a slow radio shared by several drones, this overhead, the processing it needs, and the work of managing keys may explain why protection is often left off. *(13 bytes: Documented [2]. Reasons: Assumption A1)*
- **No built-in key lifecycle.** Signing does not handle key rotation, revocation, or recovery on its own. In PX4 the key is stored on the drone's SD card, and changing it needs a message signed with the current key. *(Documented [2])*
- **The replay protection has been attacked.** Signing relies on timestamps, and researchers broke this protection by manipulating GPS time without knowing the key. *(Documented [4])*
- **Several drones make keys harder.** If all drones share one key, losing one drone exposes the others. *(Assumption A3)*

### 1.4 Concrete scenario

*Illustrative scenario. The team is fictional; the weaknesses it shows are documented in the sources.*

A volunteer search-and-rescue team flies three drones over a forest to find a missing hiker. Drones 1 and 2 fly autonomous search patterns. The operator flies Drone 3 by hand to look closely under the trees. All three are controlled from one laptop GCS at the trailhead over one telemetry radio.

- **With signing off (the PX4 default).** Someone parked nearby with an inexpensive radio receiver can see each drone's live position and the search pattern. They can also record a "return to launch" command and send it again later, pulling a drone off the search. Research has shown that attacks of this kind can stop a drone's ongoing mission [1].
- **With signing on and one shared key.** The replayed command is now rejected. But Drone 2 crashes in the forest and someone recovers it. PX4 stores the signing key on the drone's SD card [2], and the same key works for Drones 1 and 3.
- **With full encryption.** Outsiders can no longer read telemetry. But every packet is now larger, and three drones share one slow radio. If the link fills up, Drone 3's manual control starts to lag, which is risky close to trees.
- **What the team needs.** Protection that hides and checks every message, keeps working when a drone is lost, and still leaves enough bandwidth and speed for manual control. The team cannot pick an approach without knowing what each one costs.

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
| A1 | Operators leave signing and encryption off because of bandwidth overhead, processing cost, and the work of managing keys. | Assumption | To test |
| A2 | With several drones on one radio, the extra bytes from protection matter more than the processing cost on each drone. | Assumption | To test |
| A3 | There is no widely adopted method for managing a separate key for each drone in a MAVLink fleet. | Assumption | Not found so far |
| A4 | Manual piloting is more sensitive to added delay than autonomous missions. | Assumption | To test |

---

## 2. Scope and contribution

The project goal is to encrypt communication between a drone in the sky and its GCS. Several existing approaches could do part of this, and each has different costs. Before building anything, I need to know which one fits drone conditions best.

### 2.1 Semester I contribution

**A fair, repeatable comparison of existing ways to protect drone-to-GCS messages, run with one GCS and up to three simulated drones, measured against the same criteria, and ending with a justified choice for Semester II.**

| Approach | What it protects | How keys are handled | Why it is included |
| --- | --- | --- | --- |
| A. No protection | Nothing | None | The baseline every other approach is measured against |
| B. MAVLink 2 signing | Authenticity, integrity, replay (by timestamp) | One shared 32-byte key, loaded by hand [3] | Already built into ArduPilot and PX4 |
| C. Encryption added to MAVLink messages | Confidentiality, authenticity, integrity | A separate key per drone in my tests | Closest research approach [5]. Candidate algorithms: Ascon-AEAD128 [7], ChaCha20-Poly1305, AES-GCM. None chosen yet. |
| D. Secure channel around the link (DTLS 1.3) | Confidentiality, authenticity, integrity; replay detection optional | A handshake sets up session keys | Mature standard [6], but designed for IP networks, not serial radios |

Each approach will be tested under the same conditions:

- **Fleet size:** 1, 2, and 3 drones.
- **Flight type:** an autonomous waypoint mission, and manual piloting.
- **Link quality:** a good link, and a poor link with added delay, packet loss, and limited bandwidth like a telemetry radio.

**Example test.** Drone 1 flies a waypoint mission while the GCS sends "return home." The test records that command, sends it again 30 seconds later, and checks whether it is rejected. The same test runs for approaches A to D, and the results go into one table.

### 2.2 Measurable criteria

| Area | What I will measure | How | Initial target |
| --- | --- | --- | --- |
| Confidentiality | Whether captured telemetry can be read without the key | Capture traffic on the link and try to decode it | No fields readable |
| Integrity | Whether altered messages are accepted | Change bytes in captured messages and resend them | 100% rejected |
| Authenticity | Whether messages from an unenrolled device are accepted | Send commands from a test device without the key | 100% rejected |
| Replay | Whether recorded valid messages are accepted again | Resend captured commands after a delay | 100% rejected |
| False rejections | Valid messages wrongly rejected | Count rejections during normal flight | 0 |
| Bandwidth | Bytes added per packet; share of link capacity used | Compare against the baseline at 1, 2, and 3 drones | Reported for each case; must leave headroom on the link |
| Latency | Added delay, median and 95th percentile | Time stamps at the GCS and drone, compared with the baseline | Separate limits for manual and autonomous flight (see Open question) |
| Packet loss | Messages lost or dropped on a poor link | Count sent versus accepted messages | No more than the baseline |
| Processing | Time per message and memory use on the drone side | Measure in the simulated drone software | Reported; lower is better |

**How I will choose.** An approach must pass all the security tests. Among the approaches that pass, I will pick the one with the best balance of bandwidth, latency, packet loss, and processing, with extra weight on latency for manual piloting.

### 2.3 Semester II goal

Build the selected approach into a working layer for one or more drones and one or more ground stations, and add:

- a separate key for each drone, with secure enrollment before flight,
- changing keys during a mission,
- cutting off a lost or captured drone without grounding the others,
- recovering after a dropped link or a reboot, measured as time to resume protected communication, and
- testing with 5 and 10 simulated drones using the same criteria.

Handing a drone from one GCS to another is a stretch goal.

### 2.4 Out of scope

- Real flights and real drone hardware. All testing will be in simulation.
- Designing a new encryption or key-exchange algorithm.
- Building key rotation, revocation, or recovery this semester. These move to Semester II.
- Handover between ground stations this semester.
- Video streams and other payload data. Only command and telemetry messages are covered.
- Defending against radio jamming, or GPS spoofing of the drone's navigation.
- Securing the GCS computer itself, such as malware or operator accounts.
- Large swarms and drone-to-drone mesh networks.
- Military systems and export-controlled technology.
- Aviation certification and regulation.

---

## 3. Requirements

*Work to come.* Functional and non-functional requirements, drawn from the criteria in Section 2.2.

## 4. Use cases

*Work to come.* The test cases for autonomous and manual flight, written step by step.

## 5. System architecture

*Work to come.* Where each approach sits between the GCS and the drones, and how the test setup connects them.

## 6. Key and state management

*Work to come.* What each side stores for each approach, and how keys and message counters stay consistent.

## 7. Message format and protocol

*Work to come.* How a protected message is laid out under each approach.

## 8. Failure handling and recovery

*Work to come.* Behavior when the link drops, a drone reboots, or a check fails. The drone must fall back to safe behavior and never fly uncontrolled.

## 9. Threat model and security analysis

*Work to come.* Who the attacker is, what they can do, and what each approach does and does not protect against.

## 10. Evaluation plan

*Initial draft.* The criteria are in Section 2.2. Each approach (A to D) will run in the same simulated setup with one GCS and 1, 2, or 3 drones. The link will be shaped to add delay, packet loss, and a bandwidth limit. Each test will run several times, and results will be reported as the median and 95th percentile against the no-protection baseline. The full test procedure, the number of runs, and the latency targets are work to come.

## 11. Project plan and risks

*Work to come.* Schedule for both semesters. Known risks so far: scope growth, and simulation not matching real radio conditions.

---

## 12. References

**Starting source for this semester.** The MAVLink message signing guide [3] shows what existing protection does and what it leaves open. It authenticates messages with one shared key, but it does not encrypt them and it does not define how keys reach the drone. The MAVSec paper [5] is the closest existing approach and shows that encryption is practical on autopilot hardware. Together they define approaches B and C in my comparison.

1. Y.-M. Kwon, J. Yu, B.-M. Cho, Y. Eun, and K.-J. Park, "Empirical Analysis of MAVLink Protocol Vulnerability for Attacking Unmanned Aerial Vehicles," *IEEE Access*, vol. 6, pp. 43203–43212, 2018. <https://scholar.dgist.ac.kr/handle/20.500.11750/9227>
2. PX4 Autopilot, "MAVLink Message Signing," *PX4 User Guide*. <https://docs.px4.io/main/en/mavlink/message_signing>
3. MAVLink Developer Guide, "Message Signing (Authentication)." <https://mavlink.io/en/guide/message_signing.html>
4. Z. Colton, A. Oracevic, and S. Dilek, "Timestamp Manipulation-Based GPS Spoofing Attacks on the MAVLink 2.0 Protocol for UAV Communication: An Empirical Study," University of Bristol. <https://research-information.bris.ac.uk/en/publications/timestamp-manipulation-based-gps-spoofing-attacks-on-the-mavlink-/>
5. A. Allouch, O. Cheikhrouhou, A. Koubaa, M. Khalgui, and T. Abbes, "MAVSec: Securing the MAVLink Protocol for Ardupilot/PX4 Unmanned Aerial Systems," in *Proc. International Wireless Communications and Mobile Computing Conference (IWCMC)*, June 2019. <https://cister-labs.pt/docs/mavsec__securing_the_mavlink_protocol_for_ardupilot_px4_unmanned_aerial_systems/1504/>
6. E. Rescorla, H. Tschofenig, and N. Modadugu, "The Datagram Transport Layer Security (DTLS) Protocol Version 1.3," IETF RFC 9147, April 2022. <https://www.rfc-editor.org/rfc/rfc9147.html>
7. National Institute of Standards and Technology, "NIST Finalizes 'Lightweight Cryptography' Standard to Protect Small Devices" (NIST SP 800-232), August 2025. <https://www.nist.gov/news-events/news/2025/08/nist-finalizes-lightweight-cryptography-standard-protect-small-devices>
8. Defense One, "US Drones May Soon Run on Open-Source Software," May 2019. <https://www.defenseone.com/technology/2019/05/us-drones-may-soon-run-open-source-software/156699/>
