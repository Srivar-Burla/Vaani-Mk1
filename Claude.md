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