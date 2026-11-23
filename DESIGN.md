# Source-Version Traceability for Search Over Changing Public Documents

Mohammed Miad · CSC 59866 · Problem A09 · Assignment 2

## Progress note

This week I worked through the Assignment 2 feedback and chose a design. I redefined an output's identity so that a retry and a model change no longer conflict in C1, added a mixed-version example, gave Q1 a pass rule, and named the two sources: Wikipedia article revisions and eCFR regulation versions. I selected per-document provenance records, with runs still started on a schedule by Airflow, and recorded two decisions on record granularity and output identity. Sections 4 and 5 now show the running parts and the contract for the extraction step, and Section 9 sets up a small experiment on the retry rule. I learned that Airflow can tell me a task failed, but only my own records can say which documents inside it finished. The main unresolved issue is how search picks the current output. Next I will define the records and algorithms.

**Open question.** When one document version has AI outputs from several models or prompts, should search show only the active one, or let staff ask for a specific one?

**Feedback** After the Assignment 2 feedback, I defined an output's identity so C1 counts identities instead of document versions, which keeps outputs from different models without conflict. I added the mixed-version retry example, gave Q1 a median-of-three pass rule, narrowed the Section 3 comparison to record granularity, named Wikipedia and the eCFR as sources, and listed the minimum provenance fields. How often the failure happens in practice is still unresolved.

## Contents

1.  [Problem research and scope](#1-problem-research-and-scope)
2.  [Requirements and system specification](#2-requirements-and-system-specification)
3.  [Alternatives and selected solution](#3-alternatives-and-selected-solution)
4.  [Architectural design](#4-architectural-design)
5.  [Component design and interfaces](#5-component-design-and-interfaces)
6.  [Data structure design](#6-data-structure-design)
7.  [Algorithm design and execution](#7-algorithm-design-and-execution)
8.  [Failures and security](#8-failures-and-security)
9.  [Implementation and feasibility](#9-implementation-and-feasibility)
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
| F1 | When the pipeline collects a document version it has not seen, it saves it under the source's version identifier and keeps earlier versions | Collect an older revision of a test article, then a newer one; both are stored and the older one is unchanged |
| F2 | The pipeline converts each document version to plain text and records which version of the cleaning code produced it | Process one document version and inspect the record; it names the document version and the cleaning version |
| F3 | The AI step extracts a fixed set of fields (topic, key dates, organizations named) from each document version and records the document version it read, the model it used, and the prompt version | Run the AI step on one document version and inspect the stored fields; all three are recorded |
| F4 | A search returns results that each name their source address, document version, collection time, and processing version, including the model and prompt for any AI-extracted field | Run a query that matches a known document; every field in the result is filled in and matches the stored records |
| F5 | When a document has several versions or several AI outputs, search returns the current one by a stated policy (the newest document version, processed with the active model and prompt), and older outputs stay stored and can be looked up by identity | Process D7 version 2 with M1 and then M2, with M2 active; search returns the M2 output, and the M1 output can still be retrieved by its identity |
| C1 | After any processing step is interrupted and retried, each output identity the step should produce exists exactly once: none is missing and none is repeated | Stop the cleaning step after it saves item 50 of 100 but before it reports completion, retry the same 100 inputs, then list the identities; there are exactly 100, each appearing once |
| C2 | A result or AI-extracted field always refers to the document version and processing version that actually produced it. A later edit at the source, or a change of model or prompt, never changes what an existing output refers to | Index a document, collect a newer revision, and switch the model; the original result still names the older revision and the original model, and the new outputs name the newer revision or the new model |
| Q1 | **Proposed, not measured.** On the documented local setup, a full run over the 100-document fixture with provenance records takes at most 25% longer than the one-record-per-run baseline, with model call time counted in both | Run both configurations three times on the same fixture and report all six times. Q1 passes only if the median overhead is at most 25% and none of the six runs failed; a failed run counts as a miss, not as a run to drop |

F1 to F4 follow the pipeline from collection to search, and F5 states which output search shows when several exist. C1 now counts identities rather than document versions, which was the main change after Assignment 2 feedback: keeping one output from M1 and one from M2 for the same document version is two identities, each existing once, so it no longer conflicts with F3. C2 covers both of the ways a link can silently point at the wrong thing: an edited source and a changed model. Q1 matters because recording history is only useful if it does not make the pipeline too slow to run; 25% is a starting value that I expect to revise once I measure the baseline.

### 2.2 An ordinary example

A Wikipedia article in the fixture is document D17, and its older revision is collected first. The cleaning step and the AI step process it, and a search for an effective date returns this result:

```json
{
  "source": "https://en.wikipedia.org/wiki/Example_article",
  "document_id": "D17",
  "document_version": "rev-1001",
  "content_hash": "3f9a1c",
  "collected_at": "2026-11-22T09:00:00-05:00",
  "text_identity": "D17/rev-1001/clean-0.3",
  "fields": {
    "topic": "reporting requirements",
    "effective_date": "2025-07-01",
    "organizations": ["Agency X"]
  },
  "fields_identity": "D17/rev-1001/clean-0.3/model-a/extract-v1"
}
```

The address, revision number, hash, model name, and values are invented placeholders; the real pages and model are not chosen yet. A staff member can see exactly which revision this came from and what produced each part of it.

### 2.3 Unsuccessful cases

**Model timeout.** The AI step calls the model for a document, and the call times out. The pipeline does not know whether the model produced an answer, so it marks that output identity as pending and indexes no fields for it. The retry calls the model again for that identity only. Until then, the search result shows the document's text without AI fields rather than showing fields with no recorded origin.

**Crash halfway through cleaning.** The cleaning step saves item 50 of 100 and crashes before reporting completion. Under C1, the retry must finish the other 50 without creating a second output for any of the first 50. A pipeline that cannot tell which 50 finished fails this case: it either duplicates them or skips some.

**Mixed-version retry**, using document D7 version 2:

1. The AI step runs with model M1 and saves `D7/v2/clean-0.3/M1/extract-v1`, marked complete.
2. The active model is switched to M2. The next run starts `D7/v2/clean-0.3/M2/extract-v1`, and the model call times out. That output is marked pending and has no fields.
3. The retry calls M2 again for that identity only. It succeeds, and the same identity is marked complete. No second M2 output is created, and the M1 output is untouched.

Afterwards two outputs exist for D7 version 2, one per model, each exactly once, which is what C1 requires. Search returns the M2 output because M2 is the active model (F5). The M1 output remains as history and can still be looked up by its identity (C2).

### 2.4 Assumptions

| Assumption | How I will check it |
|---|---|
| Wikipedia and the eCFR stay reachable long enough to build the fixture; after that, tests run from the saved copy | Build the fixture early and confirm every chosen page has two saved versions |
| A new version can be recognized from the source's version identifier, and a content hash catches a new identifier with unchanged text | Compare two saved revisions of the same page and confirm both the identifier and the hash differ |
| An older and a newer revision of the same page can stand in for an edit | Confirm that, for each chosen page, the two revisions differ in text that the AI step extracts |
| Saved records survive restarting the pipeline | Stop and restart Airflow after a run and confirm the records are still there |
| The same model and prompt can return different fields for the same document | Run the AI step twice on one document and compare the output |

### 2.5 Constraints

- Only public data, with no personal information.
- The prototype must run on my own laptop.
- Wikipedia text is licensed under Creative Commons (CC BY-SA), so stored copies keep their source address and attribution.
- The Common AI provider 1.0 needs Airflow 2.11 or later and Python 3.11 or later [6], [7].
- The AI step needs a model to call: either a paid service through an API key, or a free model running locally, such as through Ollama, which the provider supports [5].
- Six weeks and two sources, as set in Section 1.8.

## 3 Alternatives and selected solution

### 3.1 The two configurations compared

After Assignment 2 feedback, the comparison is framed around record granularity. Both configurations can be started on a schedule by Airflow; scheduling is not what separates them, and a scheduled batch could keep per-document records too. The conclusions below apply only to these two configurations.

A. One record per run (the baseline). At a scheduled time, the pipeline collects every document, overwrites the stored copies, cleans them, runs the AI step, and rebuilds the index. It keeps one record per run: when it ran, the code version, and the model and prompt it used. This is the simplest pipeline I could build with Airflow, which already schedules runs and reruns failed tasks [3], [4].

B. Per-document records. Runs start on the same schedule, but every output (cleaned text, AI fields, index entry) is saved under its identity with a status of pending, complete, or failed. Earlier document versions are kept. A retry checks these records and skips identities already marked complete.

### 3.2 Comparison against the requirements

| Requirement | A. One record per run | B. Per-document records | Basis |
|---|---|---|---|
| F1 Keep earlier versions | Does not meet it, since each run overwrites the stored copy | Meets it; each version is stored under its own identifier | My judgment |
| F2, F3 Record what produced each output | Records it once per run, which is correct only if nothing changes mid-run | Records it on every output | My judgment |
| F4 Results name their document version | Can name the run, but not which version of a document the result came from | Names the document version directly | My judgment, using the batch limitation noted in Section 1.7 |
| F5 Current output chosen by policy | Only one output per document exists, so there is nothing to choose, but history is lost | Keeps every output; needs an explicit policy to pick the current one | My judgment |
| C1 Each identity exactly once after a retry | Meets it only by discarding the run's partial output and redoing everything, which repeats every model call | Meets it by skipping identities already marked complete | My judgment; Section 9.2 tests the mechanism |
| C2 Edits and model changes don't rewrite history | Fails after an edit, because the old copy is overwritten | Meets it, because old outputs keep their own identities | My judgment, supported by [2] |
| Q1 Run-time overhead | Lowest; one record per run | Higher; one record per output, per step | To be measured |
| Effort to build | Small | Larger; needs a record store and skip-if-complete logic | My judgment |

### 3.3 What the sources support

The provenance survey [2] supports configuration B's main idea. It distinguishes recording history as data is produced from reconstructing it afterward, and reconstruction needs the original data to still exist. An edited web page removes the original, so recording at collection time is the option that can satisfy C2.

The Airflow documentation [3], [4] supports both configurations equally. Airflow can schedule a run and rerun a failed task, but rerunning a task does not decide what happens to output the task already wrote, which is exactly what C1 is about.

The Common AI provider posts [5], [6] matter for the AI step in either configuration. Durable execution replays completed model steps on a retry within one task [6], which could reduce the cost of a retry. It does not record which document version an output came from, so it does not satisfy F3 or C2 by itself.

FBI section 1.8 [1] asks for non-duplicated sources with accurate sourcing, which corresponds to C1 and C2. Those are the two rules on which the configurations differ most.

### 3.4 Selected solution

I selected configuration B: per-document records keyed by output identity, with runs still started on a schedule by Airflow. Of the two, it is the only one that can meet C2, because configuration A overwrites the stored copy when a source changes. It meets C1 by skipping identities already marked complete, where A can only meet it by discarding the partial output and redoing the whole run, including every model call. The cost is more records and more code, and the open risk is Q1: if writing one record per output per step adds too much time, B misses its quality target. Configuration A stays in the project as the baseline that Q1 is measured against.

The two decision records below follow the context, options, choice, and consequences format the handbook recommends [11].

### 3.5 Decision 1: Record granularity

**Context and requirement.** C1 needs to know, after a crash, which documents a step finished. C2 and F1 need old versions and their outputs kept. Airflow records whether a task finished, not which documents inside it did.

**Options.** (a) One record per run, as in the baseline. (b) Rely on the Common AI provider's durable execution, which keeps a journal of model steps for one task's retries [6]. (c) One record per output, keyed by its identity, kept in the pipeline's own provenance store.

**Choice.** Option (c).

**Reasons.** Option (a) cannot meet C2 or name a document version in a result. Option (b) covers only the AI step and only one task's retries, and does not say which document version an output came from. Option (c) is the only one that covers every step and keeps history.

**Consequences.** There are more records, every step needs a skip-if-complete check, and every step depends on the provenance store. This is the main source of the overhead Q1 measures.

**Reconsider if.** The median overhead in Q1 is well over 25% and cannot be reduced, or the project grows past what a single SQLite file on a laptop can handle.

### 3.6 Decision 2: Output identity and current versus history

**Context and requirement.** Assignment 2 feedback pointed out that F3 keeps outputs from several models for the same document version, while C1 said each document version appears exactly once. Both cannot be true under the old wording.

**Options.** (a) Identity is the document version only, and a new model overwrites the old output. (b) Identity is the document ID, document version, cleaning version, model, and prompt version; every distinct identity is kept, and search chooses the current one. (c) Keep only the newest output and write older ones to a separate log.

**Choice.** Option (b).

**Reasons.** Option (a) breaks C2, because switching models rewrites what an old result refers to. Option (c) keeps history but splits it across two places that can drift apart. Option (b) makes a retry of the same identity harmless and makes a model change a new, separate output, which removes the conflict.

**Consequences.** Storage grows with each model or prompt change. Search needs an explicit current-version policy (F5), and the pipeline needs a single setting that names the active model and prompt.

**Reconsider if.** Staff turn out to need only the current output, or storage from repeated model changes becomes a problem.

## 4 Architectural design

### 4.1 Context

Everything in the prototype runs on my laptop. The table lists who and what sits outside that boundary.

| Outside participant | What crosses the boundary |
|---|---|
| Wikipedia and the eCFR | Chosen revisions, fetched once by the fixture builder. After that, the pipeline reads the saved fixture, not the live sites |
| Model service | Cleaned text goes out and typed fields come back. The plan is a local model through Ollama; a hosted service through an API key is the fallback |
| Searcher and staff | Queries go in through a command-line search tool, and results come back with their provenance |
| Operator (me) | Starts runs, triggers the failure injector, and retries failed runs |

### 4.2 Running parts

![Architecture diagram: Wikipedia and the eCFR feed a fixture builder that saves a read-only fixture on the laptop. An Airflow scheduler and worker run one DAG with four tasks in order: collect, clean, AI extract, and index. Each of the first three tasks reads and writes records in a SQLite provenance store; the AI extract task exchanges text and typed fields with an outside model service; the index task reads complete outputs and writes a SQLite full-text search index. A search command-line tool reads the index and the provenance store and answers the searcher. A failure injector, used only in tests, stops the clean task after item 50. The operator starts and retries runs.](assets/architecture.png)

*Figure 2. The running parts of the prototype, what each one talks to, and where state is saved. Editable source: [assets/architecture-source.mmd](assets/architecture-source.mmd).*

| Part | Responsibility | Saves | Build, reuse, or simulate |
|---|---|---|---|
| Fixture builder | Fetches the chosen older and newer revisions from Wikipedia and the eCFR, with their version identifiers | The fixture files | Build; runs once |
| Airflow scheduler and worker | Starts a run on a schedule, runs the four tasks in order, retries a failed task | Task and run status in Airflow's own database | Reuse |
| Collect task | Reads the fixture, recognizes new document versions, registers them | Document version records | Build |
| Clean task | Converts each document version to plain text | Cleaned text under its identity, with status | Build |
| AI extract task | Calls the model through the Common AI provider and validates the typed fields it returns | Fields under their identity, with status | Reuse the provider; build the record logic |
| Index task | Writes the current outputs into the search index, following the F5 policy | Index entries | Build, on reused SQLite full-text search |
| Provenance store | Holds document versions and every output record with its identity and status | All provenance | Reuse SQLite; build the tables |
| Search CLI | Answers queries and attaches each result's provenance | Nothing | Build |
| Model service | Runs the language model | Nothing the pipeline relies on | Reuse |
| Failure injector | Stops the clean task after a set number of items, or forces a model timeout | Nothing | Simulate; tests only |

### 4.3 Communication

The Airflow scheduler starts a run on a schedule, and the worker runs the tasks in order: collect, clean, AI extract, index. Tasks pass only small values between each other, such as lists of document IDs and identities, through XCom, Airflow's store for small values passed between tasks [6]. Text, fields, and records go through the provenance store, not XCom. The AI extract task sends cleaned text to the model service over the network through the Common AI provider and gets typed fields back [5]. The search CLI reads the search index and the provenance store directly and does not go through Airflow.

### 4.4 Saved state

The provenance store is the authority on which outputs exist and whether each one finished. Airflow's own database is the authority on whether a task run finished, which is not the same thing: a task can fail after half its documents are complete, and only the provenance store knows which half. This difference is the reason for Decision 1. The search index is derived from the provenance store and can be rebuilt from it, and the fixture is read-only during runs.

The provenance store is a single shared dependency. If it cannot be written, no step can mark anything complete, so the task fails and Airflow retries it later. That stops the pipeline, but it never produces a result with a false or missing record.

### 4.5 Built, reused, and simulated

- **Built:** the fixture builder, the four task bodies, the provenance tables, the identity and skip-if-complete logic, the search CLI, and the failure injector.
- **Reused:** Airflow for scheduling, ordering, and task retries; the Common AI provider for the model call and typed output; SQLite for storage and full-text search; the model itself; and the Wikipedia and eCFR content.
- **Simulated:** a source edit, by switching from an older to a newer saved revision; a crash, by the failure injector stopping the clean task after item 50; and a model timeout, by the injector or a short time limit.

## 5 Component design and interfaces

### 5.1 Component responsibilities

These components are functions or modules inside the running parts from Section 4, not separate services.

| Component | Lives in | Responsibility | Input | Output or state change |
|---|---|---|---|---|
| Version register | Collect task | Decide whether a document version is new and save it | A fixture document and its version identifier | A new document version record, or nothing if already seen |
| Cleaner | Clean task | Convert a document version to plain text | A document version | Cleaned text saved under its identity |
| Identity builder | Shared | Build the identity string for an output | IDs, versions, and the active model and prompt | An identity such as `D7/v2/clean-0.3/M1/extract-v1` |
| Completion recorder | Shared | Mark an identity pending, complete, or failed, and answer whether it is already complete | An identity | A status change |
| Extractor | AI extract task | Send cleaned text and the prompt to the model and check the returned fields against the expected types | Cleaned text and its identity | Fields saved under the new identity |
| Indexer | Index task | Write the current output of each document into the search index | Complete outputs and the F5 policy | Index entries |
| Search policy | Search CLI | Choose the current output for each matching document | A query | Results with provenance |
| Failure injector | Tests only | Stop a task after a set number of items, or force a timeout | A setting such as "stop after 50" | A simulated crash or timeout |

### 5.2 Critical operation: extract fields for one document version

This operation is linked to F3 (record what produced each field), C1 (exactly one output per identity after a retry), and C2 (old outputs keep their provenance).

| Part of the contract | Description |
|---|---|
| Caller | The AI extract task in an Airflow run, once per document version |
| Input | Document ID, document version, the identity of its cleaned text, the active model, and the active prompt version |
| Identity | The cleaned text's identity plus the model and prompt version |
| Normal output | Fields (topic, key dates, organizations named) saved under that identity, marked complete |
| State changes | Creates at most one output record per identity. Its status moves from pending to complete, or from pending to failed. It never changes another identity's record |
| Errors | See the outcomes below |

| Outcome | When it happens | State afterwards | What the caller does |
|---|---|---|---|
| Complete | The model returns fields that pass the type check | The record is complete and holds the fields | Moves on |
| Already complete | The identity is already marked complete | Unchanged; the model is not called | Moves on. This is what makes a retry safe |
| Pending | The model call does not answer in time | The record is pending and holds no fields | Retries this identity later, up to a set number of attempts |
| Invalid output | The model's answer fails the type check, such as a date field holding "next spring" | The record is failed, with the reason | Retries within the limit, then leaves it failed and reports it |
| Missing input | The cleaned text for that identity does not exist | Nothing is created | Reports it; the clean step must run first |
| Store unavailable | The provenance store cannot be written | Nothing is marked complete | The task fails, and Airflow retries the task |

### 5.3 Minimum provenance fields

Assignment 1 feedback asked for the minimum fields a record must hold. Section 6 will define the full records in Assignment 4.

| Field | Example | Why it is needed |
|---|---|---|
| Document ID | D17 | Names the document across all its versions |
| Source address | Wikipedia or eCFR page address | Says where the document came from |
| Document version | rev-1001 | The source's own version identifier (F1, C2) |
| Content hash | 3f9a1c | Recognizes a new identifier with unchanged text |
| Collection time | 2026-11-22 09:00 | When the version was collected |
| Cleaning version | clean-0.3 | What produced the text (F2) |
| Model and prompt version | model-a, extract-v1 | What produced the fields (F3) |
| Status | pending, complete, or failed | Lets a retry skip finished work (C1) |
| Identity | `D17/rev-1001/clean-0.3/model-a/extract-v1` | The key that makes each output exist once |

### 5.4 Examples

**Success.** Input: D17, revision rev-1001, cleaned text `D17/rev-1001/clean-0.3`, model-a, prompt extract-v1. The model returns a topic, one date, and one organization, all passing the type check. Result: a new record `D17/rev-1001/clean-0.3/model-a/extract-v1`, marked complete, holding those fields.

**Repeated call.** The same input arrives again, as it would on a retry. The identity is already complete, so the outcome is "already complete," the model is not called, and there is still exactly one record.

**Timeout and retry.** The mixed-version case in Section 2.3: D7 version 2 with M2 times out and stays pending, the retry completes the same identity, and the M1 output for D7 version 2 is untouched.

**Invalid output.** The model returns "next spring" for an effective date. The type check rejects it, the record is marked failed with that reason after the allowed attempts, and no fields are indexed for it.

### 5.5 Still being worked out

- Whether the pending record is written before the model call, so a crash during the call leaves a trace, or only after it. This affects C1 and will be settled with the algorithm in Assignment 4.
- The number of retry attempts and the wait between them.
- The full record layout and how long old outputs are kept, which belong to Section 6.
- What search shows when the newest document version has no complete AI output yet: the older complete output, or the text alone.

## 6 Data structure design

Not yet written. Due with Assignment 4 (November 27). Will define the records kept for each document and the rules they must follow.

## 7 Algorithm design and execution

Not yet written. Due with Assignment 4 (November 27). Will give pseudocode for the critical operation with a normal sequence and an interrupted one.

## 8 Failures and security

Not yet written. Due with Assignment 4 (November 27). Will cover adverse scenarios, misuse cases, and the one failure the prototype demonstrates.

## 9 Implementation and feasibility

The path starts with one document and grows only after each step works.

A fixture with one Wikipedia article: an older and a newer revision, saved locally.
An Airflow DAG with the four tasks, run on the older revision: collect, clean, extract with one model, index.
The search CLI returns the result with its identity and provenance fields (F3, F4).
Switch to the newer revision and run again. Search returns the newer version, and the older one can still be looked up (F1, F5, C2).
Only then grow the fixture to about 100 documents across both sources and add the failure injector to test C1.

Status: not started. No pipeline exists yet, implementation status will be reported in Assignments 5 and 6. No code exists yet.

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
