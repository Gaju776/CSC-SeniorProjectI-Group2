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

![Flow diagram: public sources A and B feed five steps, collect, clean and convert, AI extraction, index, and search. A staff member checks a search result by tracing it back to its source. Three red markers show where the trail breaks: a source editing a document after collection, a processing step crashing after 50 of 100 documents and being rerun, and the model or prompt in the AI step changing between runs.](assets/workflow.png)

*Figure 1. The pipeline workflow, with the three points where a result loses its link to its source. Editable source: [assets/workflow-source.mmd](assets/workflow-source.mmd).*

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
| What information is saved? | Processed text and AI-extracted fields in the index, plus whatever records the pipeline keeps about each document |
| When might a response not arrive? | The worker crashes after writing 50 of 100 documents, before reporting back; or a call to the model service times out |

The last row is a partial failure. The coordinator sees a failed task, but half the output already sits in the store. As with a timeout, the failure tells the coordinator nothing about what was saved, so the pipeline has to record enough for a retry to separate finished work from unfinished work. The sources add a second difficulty: they change documents on their own schedule without telling the pipeline. The model service adds a third. It is an outside participant reached over the network, its calls can time out, and a timed-out call says nothing about whether the model produced an answer.

### 1.6 What supports this

The handbook asks for each piece of evidence to be labeled by type. Nothing here is observed yet; the first observations will come from the prototype.

| Statement | Evidence type | Source |
|---|---|---|
| A federal research call seeks AI that supports a semi-automated extract-transform-load process, including selecting, tagging, and transforming collected data | Documented | FBI problem sets, section 1.2 [1] |
| The same call wants answers that describe connections in the data up to the time they were requested, drawn from non-duplicated sources with accurate sourcing | Documented | FBI problem sets, section 1.8 [1] |
| Provenance is the derivation history of data starting from its original sources, and existing systems differ in how they record it | Documented | Simmhan, Plale, and Gannon [2] |
| Airflow coordinates pipeline steps and can rerun failed tasks | Documented | Airflow documentation [3], [4] |
| Airflow leaves the choice of what document history to keep to the pipeline | My reading of [3] and [4] | — |
| Airflow's Common AI provider can run a model call as a pipeline task and return typed, structured output | Documented | Airflow blog [5] |
| The provider logs token usage and tool calls, and agent tasks record the name of the model that answered | Documented | Airflow blog [5], [6] |
| Its durable execution keeps a per-task journal so a retry replays completed model steps instead of calling the model again | Documented | Airflow blog [6] |
| None of these records ties an AI output to the document version it read | My reading of [5] and [6] | — |
| Links to source versions really do get lost in a pipeline like this | Assumed; my prototype will test it | — |
| Staff need the exact document version, not only the web address | Assumed from the Problem A09 description | — |

The research call shows a related need exists, and section 1.8 in particular describes the same goal as this project: point-in-time answers with no duplicates and accurate sourcing. This project works with public documents and is not being built for that agency.

### 1.7 Approaches that exist today

The Problem A09 description names two ways of running such a pipeline. A scheduled batch processes a group of documents together at fixed times. One record can describe the whole run, but it can't say which document version led to a particular result. A per-document pipeline handles each document as it arrives and can keep a record for each one, at the cost of more records that must stay consistent with each other.

The provenance survey [2] adds a distinction between storing history alongside the data and reconstructing it later from the output. Reconstruction only works while the original source data still exists, which is exactly what an edited web page takes away. My reading is that changing sources mean history has to be recorded when a document is collected.

Airflow's Common AI provider offers a third relevant approach for the AI step. Its durable execution records each completed model and tool step in a journal kept for the task instance, and on retry it replays recorded steps until it reaches one whose request has changed [6]. That avoids paying for repeated model calls during a retry, but it is scoped to one task's retries, not to the documents flowing through the pipeline. It does not say which document version an output came from, and the post notes that replay records results rather than effects, so steps with side effects still need to be safe to repeat. Section 3 will compare these approaches against the requirements.

### 1.8 Scope

The prototype uses two public sources with one search task. I have not picked the sources yet; they need to be public, change over time, and hold no personal information. The question is which details each processed document and each AI output must carry (likely candidates are its source address, document version, processing version including the model and prompt, and whether processing finished) for every result to stay traceable after one document changes and one processing step is interrupted on purpose and retried. The prototype passes if every result and every AI-extracted field names its correct document version and processing version, with nothing missing or repeated.

| Six-week prototype | Semester II | Not part of this project |
|---|---|---|
| Two public sources, one search task | Interruptions at more points in the pipeline | Search quality or ranking |
| One AI extraction step whose fields record the model, prompt, and document version | AI-written answers that cite the document versions they used, and human review of AI output | Training or fine-tuning models, or judging how accurate the AI output is |
| One document edited at its source | Sources that change repeatedly | A user interface beyond the command line |
| One processing step interrupted and retried | A lookup that shows the full trail for any result | More than two sources, private data, large scale |
| Check that each result names its document version and processing version | Measuring the storage and time cost of the records against a pipeline that keeps no history | Disk loss or corrupted sources, authentication |

## 2 Requirements and system specification

This section states what the pipeline must do, not how. Requirement IDs use three letters from the handbook: F for a functional requirement (something the pipeline does), C for a correctness rule (something that must never go wrong), and Q for a quality target (how well it must perform). The acceptance checks are planned procedures; none has been run yet.

### 2.1 Requirements

| ID | Requirement | Acceptance check |
|---|---|---|
| F1 | When the pipeline collects a document whose content differs from the last stored copy, it saves the new content as a new document version and keeps the earlier versions | Collect a test document, edit it, and collect again; two versions are stored and the first is unchanged |
| F2 | The pipeline converts each document version to plain text and records which version of the cleaning code produced it | Process one document version and inspect the record; it names the document version and the code version |
| F3 | The AI step extracts a fixed set of fields (topic, key dates, organizations named) from each document version and records the document version it read, the model it used, and the version of the prompt | Run the AI step on one document version and inspect the stored fields; all three are recorded |
| F4 | A search returns results that each name their source address, document version, collection time, and processing version, including the model and prompt for any AI-extracted field | Run a query that matches a known document; every field in the result is filled in and matches the stored records |
| C1 | After any processing step is interrupted and retried, each document version appears exactly once in that step's output and exactly once in the index | Stop the cleaning step after 50 of 100 documents, retry it, then count entries per document version in its output and in the index; every count is exactly 1 |
| C2 | A result or AI-extracted field always refers to the document version and processing version that actually produced it. A later edit at the source, or a change of model or prompt, never changes what an existing output refers to | Index a document, edit it at the source, collect again, and switch the model; the original result still names version 1 and the original model, and the new outputs name version 2 or the new model |
| Q1 | **Proposed, not measured.** On the documented local setup, a full run over 100 documents with provenance records takes at most 25% longer than the same pipeline that stores no history, with model call time counted in both | Run both pipelines three times on the same 100 documents and compare total run time; a failed run counts as a miss, not as a run to drop |

F1 to F4 follow the pipeline from collection to search. C1 is the rule from my original open question, and it is the rule most likely to separate the two approaches in Section 3. C2 covers both of the ways a link can silently point at the wrong thing: an edited source and a changed model. Q1 matters because recording history is only useful if it does not make the pipeline too slow to run; 25% is a starting value that I expect to revise once I measure the baseline.

### 2.2 An ordinary example

A document from source A is collected on Monday and becomes version 1. The cleaning step and the AI step process it, and a search for "effective date" returns this result:

```json
{
  "source": "https://example-source-a.gov/guidance/page-12",
  "document_version": "page-12@v1",
  "collected_at": "2026-11-16T09:00:00-05:00",
  "text_produced_by": "cleaner v0.3",
  "fields": {
    "topic": "reporting requirements",
    "effective_date": "2025-07-01",
    "organizations": ["Agency X"]
  },
  "fields_produced_by": {"model": "model-a", "prompt": "extract-v1"}
}
```

The address, model name, and values are invented placeholders; the real sources and model are not chosen yet. A staff member can see exactly which version of the page this came from and what produced each part of it.

### 2.3 Unsuccessful cases

The AI step calls the model for a document, and the call times out. The pipeline does not know whether the model produced an answer, so it records the AI step for that document version as not finished and indexes no fields for it. The retry then calls the model again for that document only. The search result for that document shows its text without AI fields rather than showing fields with no recorded origin.

The cleaning step crashes after 50 of 100 documents. Under C1, the retry must finish the other 50 without creating a second entry for any of the first 50. A pipeline that cannot tell which 50 finished fails this case: it either duplicates them or skips some.

### 2.4 Assumptions

| Assumption | How I will check it |
|---|---|
| The two chosen sources stay reachable for the length of the project | Collect from both at least once a week and record any failures |
| A changed document can be detected by comparing its content with the stored copy | Edit a test document and confirm the comparison flags it; see the open question about what counts as a change |
| Saved records survive restarting the pipeline | Stop and restart Airflow after a run and confirm the records are still there |
| The same model and prompt can return different fields for the same document | Run the AI step twice on one document and compare the output |
| For testing, one source can be a local copy I control, so I can edit a document on demand | Set up the local copy before the first test |

### 2.5 Constraints

- Only public data, with no personal information.
- The prototype must run on my own laptop.
- The Common AI provider 1.0 needs Airflow 2.11 or later and Python 3.11 or later [6], [7].
- The AI step needs a model to call: either a paid service through an API key, or a free model running locally, such as through Ollama, which the provider supports [5].
- Six weeks and two sources, as set in Section 1.8.

## 3 Alternatives and selected solution

*Draft. The final choice and two decision records follow in Assignment 3.*

### 3.1 The two approaches

**A. Scheduled batch with one record per run (the baseline).** At a fixed time, the pipeline collects every document, overwrites the stored copies, cleans them, runs the AI step, and rebuilds the index. It keeps one record per run: when it ran, the code version, and the model and prompt it used. This is the simplest pipeline I could build with Airflow, which already schedules runs and reruns failed tasks [3], [4].

**B. Per-document pipeline with per-document records.** Each document version moves through the steps on its own. Every output (cleaned text, AI fields, index entry) is saved with a record that names the document version, the step, the processing version, and whether that step finished for that document. A retry checks these records and skips work that is already finished.

### 3.2 Comparison against the requirements

| Requirement | A. Scheduled batch | B. Per-document records | Basis |
|---|---|---|---|
| F1 Keep earlier versions | Does not meet it as described, since each run overwrites the stored copy | Meets it; each version is stored under its own name | My judgment |
| F2, F3 Record what produced each output | Records it once per run, which is correct only if nothing changes mid-run | Records it on every output | My judgment |
| F4 Results name their document version | Can name the run, but not which version of a document the result came from | Can name the document version directly | My judgment, using the batch limitation noted in Section 1.7 |
| C1 No duplicates or gaps after a retry | Meets it only by discarding the run's partial output and redoing everything, which repeats every model call | Meets it by skipping documents already recorded as finished | My judgment; to be tested |
| C2 Edits and model changes don't rewrite history | Fails after an edit, because the old copy is overwritten | Meets it, because old outputs keep their own records | My judgment, supported by [2] |
| Q1 Run-time overhead | Lowest; one record per run | Higher; one record per output, per step | My judgment; to be measured |
| Effort to build | Small | Larger; needs a record store and skip-if-finished logic | My judgment |

### 3.3 What the sources support

The provenance survey [2] supports approach B's main idea. It distinguishes recording history as data is produced from reconstructing it afterward, and reconstruction needs the original data to still exist. An edited web page removes the original, so recording at collection time is the option that can satisfy C2.

The Airflow documentation [3], [4] supports both approaches equally. Airflow can schedule a batch and rerun a failed task, but rerunning a task does not decide what happens to output the task already wrote, which is exactly what C1 is about.

The Common AI provider posts [5], [6] matter for the AI step in either approach. Durable execution replays completed model steps on a retry within one task [6], which could reduce the cost of approach A's redo or approach B's retry. It does not record which document version an output came from, so it does not satisfy F3 or C2 by itself.

FBI section 1.8 [1] asks for non-duplicated sources with accurate sourcing, which corresponds to C1 and C2. Those are the two rules on which the approaches differ most.

### 3.4 Early reading

Approach A fails C2 and meets C1 only at a high cost, so it serves mainly as the baseline for Q1. Approach B looks more likely to meet the requirements, but that depends on whether keeping the per-document records is fast enough, which is the open part of Q1. Assignment 3 will make the choice and record the reasons.

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
| 11/06/2026 | First version: problem and scope, workflow figure, tables, progress note, sources | Assignment 1 |
| 11/16/2026 | Added an AI extraction step to the pipeline; moved AI from the exclusions into scope; added a third failure point (model or prompt changes) to Figure 1; added evidence from FBI sections 1.2 and 1.8 and Airflow's Common AI provider | Made sure that the project explained the AI components, since the FBI problem set calls for them, and the Professor mentioned my project should focus on it when I presented my project proposal |
| 11/16/2026 | Wrote Section 2 (requirements, examples, assumptions, constraints) and drafted Section 3 (scheduled batch versus per-document pipeline) | Assignment 2 |

### Open questions

- What should count as a new document version: any change to the page's content, or only a change in its text once it is cleaned? This affects F1 and the assumption about detecting changes.
- *Resolved into a requirement:* what must be saved so a retry neither repeats nor drops a document. This is now correctness rule C1.

### Sources

1. Federal Bureau of Investigation. *FBI Enterprise Broad Agency Announcement: Problem Sets* (Attachment A). <https://biz.fbi.gov/broad-agency-announcement-baa/fbi-enterprise-baa-problem-sets>. Accessed [date].
2. Simmhan, Y. L., Plale, B., and Gannon, D. (2005). "A Survey of Data Provenance in e-Science." *ACM SIGMOD Record*, 34(3), 31–36. <https://doi.org/10.1145/1084805.1084812>
3. Apache Software Foundation. "What is Airflow?" Apache Airflow documentation. <https://airflow.apache.org/docs/apache-airflow/stable/index.html>. Accessed [date].
4. Apache Software Foundation. "Architecture Overview." Apache Airflow documentation. <https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/overview.html>. Accessed [date].
5. Naik, K., and Gopidesu, P. K. (2026, April 14). "Introducing the Common AI Provider: LLM and AI Agent Support for Apache Airflow." Apache Airflow blog. <https://airflow.apache.org/blog/common-ai-provider/>. Accessed November 16, 2026.
6. Naik, K. (2026, October 19). "Airflow AI Provider 1.0: Agents, Sandboxes, Human Approval and Smarter Retries." Apache Airflow blog. <https://airflow.apache.org/blog/common-ai-provider-1.0/>. Accessed November 16, 2026.
7. Apache Software Foundation. "apache-airflow-providers-common-ai." Provider documentation. <https://airflow.apache.org/docs/apache-airflow-providers-common-ai/stable/index.html>. Accessed November 16, 2026.
