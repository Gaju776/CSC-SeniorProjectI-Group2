**Secure communication across UAVs and ground stations**

Candidate Problem Background

Dorcas Bwenge Gaju | Senior Project I  

**Part 1: The Problem**

**Who experiences it.** Teams that fly small unmanned aerial vehicles (UAVs) for inspection, mapping, agriculture, search and rescue, and delivery. More of these teams now fly several drones at once, sometimes from more than one ground control station (GCS). The systems involved are the flight controller on each drone and the GCS software the operator uses.

**What they are trying to do.** During a flight, the GCS sends commands such as take-off, upload a mission, or return home, and each drone sends back telemetry: position, battery level, and mission status. The operator needs to know that only their own stations can command the drones, that the telemetry on screen is real, and that outsiders cannot read routes or locations.

**How it is done today.** Much of the open-source drone ecosystem, including the ArduPilot and PX4 autopilots, carries this traffic using the MAVLink protocol over telemetry radios, Wi-Fi, or cellular links. MAVLink 2 has an optional message-signing feature that lets a receiver check that a message came from someone holding a shared secret key.

**The limitation.** MAVLink does not encrypt messages. Signing is turned off by default in PX4, and even when it is on, message contents are still sent as readable plaintext. The specification also leaves the creation and delivery of keys to each implementation. These gaps grow with a fleet. Every drone needs keys, keys should change over time, a lost or captured drone has to be cut off, and a drone may need to be handed from one station to another. On top of that, drones have limited processing power and battery, and all drones in a fleet share the same limited radio bandwidth.

**Why it matters.** These messages control physical aircraft. A forged command can stop a mission or cause a crash, and readable telemetry can reveal a client’s site, a delivery route, or where the operator is standing. If drones in a fleet share keys, one compromised drone can put the others at risk.

**When it occurs.** The problem is most serious when an attacker is within radio range or on the same network, when links cross shared networks such as the internet, when the fleet grows, when a drone is lost or captured, and when links drop and reconnect, since protection that depends on both sides staying in sync is most likely to fail at that moment.

**Part 2: Evidence**

The table separates what published sources confirm from what I still believe but need to test.

|**#**|**Claim**|**Type**|**Source**|
| :- | :- | :- | :- |
|1|MAVLink is one of the most widely used protocols for GCS-based drone control, and its weaknesses can be used to disable a drone’s ongoing mission.|Documented|Kwon et al. [1]|
|2|MAVLink 2 signing gives authentication and integrity only. Messages stay in plaintext, and signing is disabled by default in PX4.|Documented|PX4 documentation [2]|
|3|How the secret key is generated is left to each implementation. The specification recommends that the GCS share the key over a secure link.|Documented|MAVLink documentation [3]|
|4|Researchers attacked MAVLink 2 signing by manipulating GPS-based timestamps, without knowing the secret key.|Documented|Colton et al. [4]|
|5|Encryption was added to MAVLink in ArduPilot. Of four ciphers tested, ChaCha20 used the least CPU and memory.|Documented|Allouch et al. [5]|
|6|Many operators leave signing off because setup and key handling are inconvenient.|Hypothesized|To investigate|
|7|As a fleet grows, the extra bytes added by encryption on a shared, slow radio link matter more than the processing cost on each drone.|Hypothesized|To investigate|
|8|There is no widely adopted method for managing keys across a MAVLink fleet (enrolling drones, changing keys, revoking a drone, handing over between stations).|Hypothesized|Not found in my research so far|

Claims 1 to 5 show that the weakness in single-link protection is real and recognized. Claims 6 to 8 are where my project would add something, so they are the claims I most need to test.

**Part 3: Existing Approaches**

|<p></p><p>**Approach**</p>|**How It Addresses the Problem**|**Strengths**|**Limitations / Questions**|
| :- | :- | :- | :- |
|**MAVLink 2 message signing**|Adds a keyed signature and timestamp to each message so forged or replayed messages can be rejected.|Already part of the protocol and supported by major autopilots. Small overhead.|No encryption. Off by default. Key delivery is left open [2][3]. The timestamp protection has been attacked [4]. Designed around a shared key, not a fleet.|
|**MAVSec** (research prototype)|Encrypts MAVLink messages inside the autopilot and compares four ciphers.|Shows encryption is practical on autopilot hardware and gives performance data [5].|Focused on encryption cost. I still need to read how it handles keys, rekeying, and link loss. Unclear whether it is maintained or used.|
|**General secure channel** (e.g., DTLS 1.3)|Wraps the traffic in a standard secure channel with a handshake, encryption, and authentication.|Mature, heavily reviewed IETF standard built for datagram traffic [6].|Built for IP networks, not serial radio links. Handshake and per-message overhead on slow, lossy links is an open question.|

These approaches show that protecting an individual message is fairly well understood. Lightweight encryption standards such as NIST’s Ascon family [7] also give options suited to small devices. What I have not found is a clear answer for a fleet: how drones join securely, how keys change mid-mission, how one drone is cut off without grounding the others, and how sessions recover after a dropped link. I have not chosen an algorithm or approach yet. Comparing candidates will be part of the project.

**Part 4: Relation to My Senior Project**

**Who would benefit.** Drone operators and organizations would gain more confidence that only their stations can control their fleet and that mission data stays private. Autopilot and GCS developers would get evidence about which protections are practical on real links. Researchers would get a repeatable comparison under realistic conditions.

**Project option.** This currently looks closer to Option 1, because it would extend or improve an existing communication protocol used by existing tools. It could also fit Option 2 if I frame it around a specific operation such as search and rescue.

**Type of design.** A combination. It is adaptive design and redesign because MAVLink and its signing feature already exist and would be extended for fleets. It is also selection design because choosing among existing encryption algorithms and secure-channel methods is a core decision.

**Distributed-systems relevance.** Several factors genuinely apply. There are multiple machines (several drones and possibly several stations) communicating over an unreliable network. Keys and message counters are shared state that must stay consistent on both ends. Individual parts fail, through link loss, reboots, or a captured drone. Changing keys and handing a drone between stations require coordination. Scalability matters because the whole fleet shares limited radio bandwidth.

**Part 5: What I Still Do Not Know**

|**Question**|**How I Might Investigate It**|
| :- | :- |
|Why do operators leave signing and encryption off: setup effort, key handling, software support, or performance?|Review autopilot and GCS documentation and issue trackers. Ask operators, for example through a local drone club or university lab.|
|How much overhead does encryption add per message, and does a shared radio link still keep up as the number of drones grows?|Read the full MAVSec results and published benchmarks for lightweight ciphers. Later, measure in a simulated fleet with limited bandwidth.|
|How do existing protections behave when a link drops, a drone reboots, or keys are changed mid-flight?|Study the MAVLink specification, the DTLS standard, and the timestamp attack paper. Later, test with simulated packet loss and delay.|

**Part 6: Early Risk**

**Project scope.** The fleet scenarios (enrolling drones, changing keys, revoking a captured drone, handing over between stations, and recovering after link loss) could easily grow beyond what one person can finish in two semesters. Evaluating the result realistically is a related risk, because simulation may not reflect real radio conditions and hardware limits, while real flight tests need equipment, a safe location, and regulatory approval.

**Part 7: Connecting the Readings**

**Reading 1, type of engineering design.** I started out planning a brand-new security framework. After learning about adaptive design and redesign, I see that MAVLink signing and MAVSec already solve parts of the problem. My work is more likely to extend them for fleets than to replace them.

**Reading 2, research and analysis of existing solutions.** Separation of concerns helped me split “secure communication” into separate problems: protecting each message, managing keys, and recovering from failures. Existing work is strongest on the first and weakest on the other two, which tells me where to focus.

**Reading 3, communications in capstone projects.** The emphasis on verifying the need made me question my first assumption. I described the need as encryption, but the evidence suggests key management and recovery for fleets matter just as much. I have recorded this change in my design log.

**References**

Y.-M. Kwon, J. Yu, B.-M. Cho, Y. Eun, and K.-J. Park, “Empirical Analysis of MAVLink Protocol Vulnerability for Attacking Unmanned Aerial Vehicles,” IEEE Access, vol. 6, pp. 43203–43212, 2018.

PX4 Autopilot, “MAVLink Message Signing,” PX4 User Guide. https://docs.px4.io/main/en/mavlink/message\_signing

MAVLink Developer Guide, “Message Signing (Authentication).” https://mavlink.io/en/guide/message\_signing.html

Z. Colton, A. Oracevic, and S. Dilek, “Timestamp Manipulation-Based GPS Spoofing Attacks on the MAVLink 2.0 Protocol for UAV Communication: An Empirical Study,” University of Bristol. https://research-information.bris.ac.uk/en/publications/timestamp-manipulation-based-gps-spoofing-attacks-on-the-mavlink-/

A. Allouch, O. Cheikhrouhou, A. Koubaa, M. Khalgui, and T. Abbes, “MAVSec: Securing the MAVLink Protocol for Ardupilot/PX4 Unmanned Aerial Systems,” in Proc. International Wireless Communications and Mobile Computing Conference (IWCMC), June 2019.

E. Rescorla, H. Tschofenig, and N. Modadugu, “The Datagram Transport Layer Security (DTLS) Protocol Version 1.3,” IETF RFC 9147, April 2022. https://www.rfc-editor.org/rfc/rfc9147.html

National Institute of Standards and Technology, “Ascon-Based Lightweight Cryptography Standards for Constrained Devices,” NIST SP 800-232, August 2025.
1
