# Source-Version Traceability for Search Over Changing Public Documents

Mohammed Miad · CSC 59866 · Problem A09 · Assignment 2

## Progress note

This week I revised Section 1 to include AI components, since the FBI problem set calls for them. The pipeline now has an AI extraction step, built on Airflow's Common AI provider, and AI output is a third thing that has to stay traceable. I also wrote the first specification in Section 2 and drafted a comparison of a scheduled batch and a per-document pipeline in Section 3. Writing the correctness rules showed me the baseline can avoid duplicates after a crash only by redoing the whole run, which repeats every model call. The main unresolved issue is how to decide that a document has a new version. Next, for Assignment 3, I will choose an approach, record two decisions, and sketch the architecture.

**Open question.** What should count as a new document version: any change to the page's content, or only a change in its text once it is cleaned?

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
11. [Operation maintenance and future work](#11-operation-maintenance-and-future-work)
12. [Revision history and references](#12-revision-history-and-references)

## 1 Problem research and scope

### 1.1 The problem in brief

For someone searching a collection built from several public websites, a result is only useful if they can check where it came from. Staff who verify results need to know which source it came from, which version of the document, when it was collected, and which version of the processing code turned it into searchable text. The pipeline also uses an AI step: a language model reads each cleaned document and pulls out structured fields, such as its topic, key dates, and the organizations it names, so search can work on those fields as well as the raw text. That makes the trail longer. An AI-extracted field depends on the document version it read, the model that produced it, and the prompt it was given, and a different model or a changed prompt can give a different answer for the same document.

The trail breaks in three ways: a source edits a document after it was collected, a processing step crashes partway and is run again, or the model or prompt changes between runs. The result is a search hit nobody can verify, or one that shows up twice or not at all. This project investigates what a small pipeline needs to record about each document and each AI output so the trail survives all three.

Two terms come up often below. Provenance means the recorded history of where data came from and what was done to it [2]. A document version is one particular state of a document; the same web address can serve different versions over time.

### 1.2 Who is affected

### 1.2 Who is affected

| Person | What they are trying to do | What goes wrong today |
|---|---|---|
| Searcher | Find information across the combined collection | A result may point to a page that no longer says what the result says |
| Staff member checking results | Confirm a result's origin before anyone relies on it | No record of the document version or processing version behind the result |
| Pipeline operator | Keep collection and processing running, and rerun failed steps | Can't tell which documents a failed step already finished |
| Staff relying on AI-extracted fields | Use the fields the model pulled out, such as a date, without rereading every document | No record of which model and prompt produced a field, or which document version it read |

The searcher and the staff member come from the Problem A09 description; the specific kinds of searcher (a researcher, an analyst, a student) are my assumption. The operator is my addition, since whoever reruns a failed step decides whether the history survives. In the prototype, the operator is me. The websites that publish the documents are outside the system: the pipeline has no say over when they change something.

### 1.3 How the work happens today

The pipeline runs in six steps. It collects documents from each source, cleans them and converts them to plain text, runs an AI extraction step that pulls structured fields out of each document, adds the text and fields to a search index, answers user queries from that index, and, when someone questions a result, a staff member traces it back to the source.

Three of those steps are where the trail breaks. Collecting a document a second time after the source edited it can overwrite the stored copy, so older results now point to text that is gone. Rerunning a step that crashed halfway can process some documents twice, miss others, or lose track of which code version produced the output. And if the model or prompt in the AI step changes, the same document can come out with different fields, with nothing recording which combination produced which answer.

Flow diagram: public sources A and B feed five steps, collect, clean and convert, AI extraction, index, and search. A staff member checks a search result by tracing it back to its source. Three red markers show where the trail breaks: a source editing a document after collection, a processing step crashing after 50 of 100 documents and being rerun, and the model or prompt in the AI step changing between runs.

Figure 1. The pipeline workflow, with the three points where a result loses its link to its source. Editable source: assets/workflow-source.mmd.

-----------------------------------------------------------------------------------------------------------------------------------------------------------
![Flow diagram: public sources A and B feed four steps, collect, clean and convert, index, and search. A staff member checks a search result by tracing it back to its source. Two red markers show where the trail breaks: a source editing a document after collection, and a processing step crashing after 50 of 100 documents and being rerun.](assets/workflow.svg)

*Figure 1. The pipeline as it runs today, with the two points where a result loses its link to its source. Editable source: [assets/workflow-source.mmd](assets/workflow-source.mmd).*

### 1.4 An example

*The following example is made up to illustrate the problem. Nothing in it was observed.*

On Monday the pipeline collects 100 documents from two public sites, one of them a guidance page on site A. Halfway through cleaning, after 50 documents, the step crashes and the operator reruns it. Rerunning everything indexes those 50 documents a second time, and they appear twice in search results. Rerunning only "the rest" goes wrong a different way: nothing recorded which 50 were finished, so some are skipped and never reach the index.

On Thursday, site A changes the effective date on the guidance page from 2025 to 2026, and the next collection overwrites the stored copy. Later, a staff member looks at a result saying the rule takes effect in 2025, opens the page, and sees 2026. There is no record of which version of the page the result came from or which processing version produced its text, so there is no way to tell whether the result was ever right.

The following week, the operator switches the AI step to a different model. Rerun on the same document version, the new model extracts the effective date from a different paragraph and records it differently. Both answers now sit in the index, and nothing says which model produced which.

### 1.5 Where the distributed systems difficulty is

Chapter 1 of the handbook asks for four things in any project: a caller, a responder, saved information, and a case where a response does not arrive. Here they are for this pipeline.

| Handbook question | In this project |
|---|---|
| Who makes a request? | A coordinator that starts a processing task |
| Who responds? | A worker that processes a batch of documents |
| What information is saved? | Processed text in the index, plus whatever records the pipeline keeps about each document |
| When might a response not arrive? | The worker crashes after writing 50 of 100 documents, before reporting back |

The last row is a partial failure. The coordinator sees a failed task, but half the output already sits in the store. As with a timeout, the failure tells the coordinator nothing about what was saved, so the pipeline has to record enough for a retry to separate finished work from unfinished work. The sources add a second difficulty: they change documents on their own schedule without telling the pipeline.

### 1.6 What supports this

The handbook asks for each piece of evidence to be labeled by kind. Nothing here is observed yet; the first observations will come from the prototype.

| Statement | Kind | Source |
|---|---|---|
| A federal research call describes a need to manage and transform data from multiple sources | Documented | FBI Enterprise BAA problem sets, Attachment A [1] |
| Provenance is the derivation history of data starting from its original sources, and existing systems differ in how they record it | Documented | Simmhan, Plale, and Gannon [2] |
| Airflow coordinates pipeline steps and can rerun failed tasks | Documented | Airflow documentation [3], [4] |
| Airflow leaves the choice of what document history to keep to the pipeline | My reading of [3] and [4] | — |
| Links to source versions really do get lost in a pipeline like this | Assumed; my prototype will test it | — |
| Staff need the exact document version, not only the web address | Assumed from the Problem A09 description | — |

The research call shows a related need exists. This project works with public documents and is not being built for that agency.

### 1.7 Approaches that exist today

The Problem A09 description names two ways of running such a pipeline. A *scheduled batch* processes a group of documents together at fixed times. One record can describe the whole run, but it can't say which document version led to a particular result. A *per-document pipeline* handles each document as it arrives and can keep a record for each one, at the cost of more records that must stay consistent with each other.

The provenance survey [2] adds a distinction between storing history alongside the data and reconstructing it later from the output. Reconstruction only works while the original source data still exists, which is exactly what an edited web page takes away. My reading is that changing sources mean history has to be recorded when a document is collected. Section 3 will compare these approaches against the requirements.

### 1.8 Scope

The prototype uses two public sources with one search task. I have not picked the sources yet; they need to be public, change over time, and hold no personal information. The question is which details each processed document must carry (likely candidates are its source address, document version, processing version, and whether processing finished) for every result to stay traceable after one document changes and one processing step is interrupted on purpose and retried. The prototype passes if every result names its correct document version and processing version, with nothing missing or repeated.

| Six-week prototype | Semester II | Not part of this project |
|---|---|---|
| Two public sources, one search task | Interruptions at more points in the pipeline | Search quality or ranking |
| One document edited at its source | Sources that change repeatedly | A user interface beyond the command line |
| One processing step interrupted and retried | A lookup that shows the full trail for any result | AI or machine learning features |
| Check that each result names its document version and processing version | Measuring the storage and time cost of the records against a pipeline that keeps no history | More than two sources, private data, large scale, disk loss or corrupted sources, authentication |

## 2 Requirements and system specification

This section states what the pipeline must do, not how. Requirement IDs use three letters from the handbook: F for a functional requirement (something the pipeline does), C for a correctness rule (something that must never go wrong), and Q for a quality target (how well it must perform). The acceptance checks are planned procedures; none has been run yet.

### 2.1 Requirements
|---|---|---|

## 3 Alternatives and selected solution

Draft:

### 3.1 The two approaches

A. Scheduled batch with one record per run (the baseline). At a fixed time, the pipeline collects every document, overwrites the stored copies, cleans them, runs the AI step, and rebuilds the index. It keeps one record per run: when it ran, the code version, and the model and prompt it used. This is the simplest pipeline I could build with Airflow, which already schedules runs and reruns failed tasks [3], [4].

B. Per-document pipeline with per-document records. Each document version moves through the steps on its own. Every output (cleaned text, AI fields, index entry) is saved with a record that names the document version, the step, the processing version, and whether that step finished for that document. A retry checks these records and skips work that is already finished.

## 4 Architectural design

Not yet written. Due with Assignment 3 (November 20). Will show the system's surroundings, its running parts, what each part saves, and what I build, reuse, or simulate.

## 5 Component design and interfaces

Not yet written. Due with Assignment 3 (November 20). Will describe the responsibilities inside each part and the contract for the most important operation.

## 6 Data structure design

Not yet written. Due with Assignment 4 (November 27). Will define the records kept for each document and the rules they must follow.

## 7 Algorithm design and execution

Not yet written. Due with Assignment 4 (November 27). Will give pseudocode for the critical operation with a normal sequence and an interrupted one.

## 8 Failures and security

Not yet written. Due with Assignment 4 (November 27). Will cover adverse scenarios, misuse cases, and the one failure the prototype demonstrates.

## 9 Implementation and feasibility

Not yet written. The plan and a feasibility experiment start in Assignment 3 (November 20); implementation status is reported in Assignments 5 and 6. No code exists yet.

## 10 Testing and verification

Not yet written. Test plans are due with Assignment 4 (November 27); results with Assignments 5 and 6.

## 11 Operation maintenance and future work

Not yet written. Drafted in Assignment 4 and finished in Assignment 6 (December 11), including Semester II milestones.

## 12 Revision history and references

### Changes to this design

| Date | What changed | Why |
|---|---|---|
| [date] | First version: problem and scope, workflow figure, tables, progress note, sources | Assignment 1 |

### Open questions

- If a processing step fails after finishing some of its documents, what must already be saved so the retry neither repeats nor drops any document and still records the processing version? This is the core of the project; Assignment 2 will turn it into a correctness rule.

### Sources

1. Federal Bureau of Investigation. *FBI Enterprise Broad Agency Announcement: Problem Sets* (Attachment A). <https://biz.fbi.gov/broad-agency-announcement-baa/fbi-enterprise-baa-problem-sets>. Accessed [date].
2. Simmhan, Y. L., Plale, B., and Gannon, D. (2005). "A Survey of Data Provenance in e-Science." *ACM SIGMOD Record*, 34(3), 31–36. <https://doi.org/10.1145/1084805.1084812>
3. Apache Software Foundation. "What is Airflow?" Apache Airflow documentation. <https://airflow.apache.org/docs/apache-airflow/stable/index.html>. Accessed [date].
4. Apache Software Foundation. "Architecture Overview." Apache Airflow documentation. <https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html>. Accessed [date].
