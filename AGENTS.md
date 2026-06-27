# Working Agreement for Vaani

## Who decides what
I am the product manager and architect. You are the implementer.
Write the code. I make the product and architecture calls.

## STOP and ask me before doing any of these
Pause, explain the tradeoff in plain language, give me 2 to 3 options
with your recommendation, and wait for my answer. Do not proceed on these alone:
- Changing the data model or any API request/response shape
- Adding a new library or dependency
- Any choice that affects what the user hears, says, or experiences
  (voice flow, prompts, error messages, conversation steps)
- When to call the cloud vs handle something locally
  (for example, whether to ground every query on web search or only some)
- Cost or latency tradeoffs (extra API calls, model choices)
- Anything where a reasonable PM would want a say

## How to write code for me
- Make ONE change at a time. Do not rewrite whole files.
- Before editing, tell me what you are about to do and why.
- Comment every block: what it does AND how it connects to the
  rest of the pipeline (STT, translate, Gemini, translate, TTS).
- Write comments a PM with rusty Python can follow.
- After a change, summarise what changed in 2 or 3 lines.

## The existing architecture (do not break this)
Pipeline: user speaks, Sarvam STT (saarika v2.5), conditional inbound
translation, Gemini 2.5 Flash behind get_llm_response(), conditional
outbound translation, Sarvam TTS (bulbul v2, anushka).
The LLM is isolated in get_llm_response() so it stays swappable.

## Documentation and decision capture

This project keeps two living documents that must stay current as we work:
BUILDLOG.md and PRODUCT.md. Capturing decisions while the reasoning is fresh is
a required part of the workflow, not an afterthought. Do not let it accumulate
as a debt to reconstruct later from diffs or memory.

**When to capture.** Whenever we do any of the following, draft the relevant
documentation update before moving on to the next task:
- Make a design, architecture, or product decision (choosing an approach,
  structuring a flow, picking or swapping a tool, model, or library)
- Deliberately scope something out, defer it, or reject an option we considered
- Hit and resolve a non-obvious bug, or diagnose a limitation worth remembering
- Revise an earlier decision based on new evidence

Routine edits, refactors, and obvious fixes do not need an entry. Capture
decisions and their reasoning, not every change. The diff already records what
changed. The documentation records why.

**Which document.**
- BUILDLOG.md is the chronological record of decisions, tradeoffs, and debugging
  lessons. It answers why. New entries go at the bottom, numbered in sequence.
  Read the existing file first to continue the numbering correctly.
- PRODUCT.md is the product definition and build plan. It answers what. Update it
  when a build-plan item is completed (flip its checkbox), when scope changes, or
  when a decision affects the product framing, the stack rationale, or the
  deferred Mk2 list.

A single decision often touches both: BUILDLOG gets the reasoning, PRODUCT.md
gets the checkbox or the scope change.

**BUILDLOG entry style, follow it exactly:**
- Each entry is a short bold lead-in sentence stating the decision or
  observation, followed by prose explaining what we did, why, and the tradeoff
  we accepted. One paragraph per distinct point.
- Write the reasoning and the alternatives we rejected, not just the conclusion.
  The rejected option is often the most valuable part for an interview.
- No em dashes anywhere. Use commas, colons, or separate sentences instead.
- No bullet points or numbered lists inside an entry. Use connective prose.
- Plain, direct language. No buzzwords, no marketing tone.

**When a decision revises an earlier one,** write a new entry that references and
supersedes the old one rather than silently editing the original. The fact that
a decision changed, and why, is itself part of the record.

**Workflow.** Draft the entry as an edit to BUILDLOG.md, plus any PRODUCT.md
change, and present it for my approval like any other diff. I review and adjust
the wording before it lands, since these are in my voice. Once approved, it is
committed alongside the code change it documents, or in a closely following docs
commit.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
