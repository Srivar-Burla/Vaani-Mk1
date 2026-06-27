# Vaani: Product Context

## Why I Built This - the Origin

I've had questions that came to my mind while walking or working on something hands-on, phone in pocket, earphones on. Stopping what I was doing, pulling out my phone, opening an app and typing my query out felt like too much of a hassle and the curiosity just faded. I wanted to just ask, out loud, and get an answer.

Building it myself felt like the obvious next step. And it turned out to be more interesting than I expected — closing the gap between understanding how these systems work conceptually and actually wiring them together, hitting the edges where things break, making tradeoffs, and shipping something real.

## The Problem

Voice-based AI interactions are largely broken for Indian users today, in three specific ways.

First, the major AI assistants like Gemini, ChatGPT, are meaningfully better at text than voice. The voice interfaces feel bolted on rather than native. The quality gap is noticeable.

Second, the drop in quality is even sharper when the language shifts away from English. Indic language voice interactions (Hindi, Telugu, Kannada, etc) are poorly handled by western AI stacks not built with these languages and accents in mind.

Third, if you want voice interaction with a specific LLM, say, Claude instead of Gemini, there is no clean way to do it. Voice is bundled with the model. There is no orchestration layer that gives you control over which reasoning engine sits underneath.

These are not capability problems. The AI is capable enough. They are accessibility and architecture problems.

## The Solution

Vaani is a thin orchestration layer that separates voice I/O from reasoning.

The flow is: user speaks (in any supported Indian language) → Sarvam STT transcribes and detects the language → transcript is translated to English → passed to the LLM of the user's choice → English response is translated back to the user's language → Sarvam TTS speaks it back in a natural Indian voice.

The key design decision is that the LLM is swappable. Gemini, Claude or other open source models, changing the reasoning engine requires changing one function. Everything else stays the same. This is the orchestration layer that doesn't exist natively in any of the current consumer AI products.

Gemini 3.1 Flash-Lite is the reasoning layer for Mk1, chosen for its low latency and cost with quality positioned on par with 2.5 Flash, and it runs the conversational path and the transaction-extraction calls on a single model. Gemini was picked as the provider primarily because it offered free API access, which made early development practical without upfront cost. Live web grounding, however, requires a billing-enabled Gemini key: on the free tier the 3.x models cannot ground at all, and 2.5 Flash grounds but is capped at about twenty requests per day. Swapping to Claude or an open source model in a future version requires changing one function.

For Mk1, invocation is handled via a gesture on the TWS (button press). Always-on wake word detection has been deliberately scoped out. Without deep hardware-level integration of the kind Siri and Gemini have, always-on mic scanning is too battery-intensive to be a viable approach on commodity earphones. 

The spoken language is detected fresh on every turn during conversation. This ensures Vaani handles mid-conversation language changes seamlessly: a user can ask one question in English, the next in Telugu, and switch back, with Vaani responding in whatever language each question was asked. The conversation is not locked to a single language at the start.

Vaani can now take actions, not just answer. A spoken command ("record a transaction") starts a guided flow that turns a natural spoken description into structured data and writes it to a real backend over an API. This is the shift from a voice interface to a voice agent, and it connects Vaani to the separate finance tracker project as the action layer behind the voice.

## Why Sarvam's Stack

Sarvam AI has built their STT and TTS models specifically for Indian languages and accents. Transcription quality on Hindi, Telugu, and Kannada is noticeably better than generic western models. Their TTS produces natural-sounding Indian voice output rather than the flat, accented output you get from most English-first TTS systems.

For a voice assistant that needs to feel seamless to an Indian user speaking in their own language, Sarvam's stack felt like a no-brainer.

## Build Plan

### Mk1 — Core Conversation Loop (current)
- [x] Sarvam STT working across Hindi, Telugu, Kannada
- [x] Gemini integration as reasoning layer
- [x] Sarvam TTS speaks response back to user
- [x] Single Query: voice in → voice out
- [x] Silence detection to end user turn dynamically instead of fixed duration input
- [x] Full conversation turn: voice in → voice out
- [x] Error handling for API failures (spoken, not crashed)
- [x] Conditional web grounding (Gemini decides per turn when to search the live web)
- [x] Transaction recording: voice command to structured fields to a real POST against the finance tracker API
- [x] Session logging: every interaction and traceback captured to a per-session log file
- [x] Desktop UI with assistant state, multilingual transcript, and Start Listening fallback
- [x] TWS Play/Pause gesture invocation through Windows media controls
- [x] Mobile-first web UI (Python standard-library server plus Server-Sent Events): an everyday chat view and a step-by-step pipeline view behind a discreet toggle, now the primary interface in place of the Tkinter desktop UI
- [x] LLM-based transaction intent detection, replacing the brittle keyword phrase list that silently missed natural requests
- [x] System prompt hardened so Vaani never claims to have performed an action it cannot, and stops ending every reply with a check-in question
- [ ] Silence detection to end conversation

## Where Vaani Is Headed

Mk1 proves the core loop: speak in any supported Indian language, and Vaani listens, reasons, and replies in that same language. Several features are deliberately deferred to Mk2, each addressing a real gap rather than just adding surface area.

**Bhasha (live translation mode).** A spoken command ("Bhasha") that switches Vaani into a two-way interpreter: it listens to a second person speaking another language and relays the conversation between both parties in real time, useful when you and the person in front of you do not share a language. Deferred because it needs the earphone mic to reliably capture a second speaker's voice, an unsolved hardware question in real environments.

**Persistent memory across sessions.** Today Vaani remembers everything within a single conversation but forgets once it ends. Mk2 gives Vaani the ability to take durable notes on tasks, people, and personal context, and recall them in future conversations, so it behaves like an assistant that actually knows you over time rather than a fresh stranger each session.

**Your choice of reasoning engine.** Vaani's architecture deliberately isolates the LLM so it can be swapped. Mk2 builds dedicated integration functions for each major provider (Gemini, Claude, and others) plus a path for locally hosted open source models, letting the user choose which intelligence sits underneath the voice, including private on-device options.

**Better English voice, and natural conversation endings.** Two known Mk1 limitations: English pronunciation (routing the English path to a stronger Indian-English voice provider) and detecting when a user naturally winds down a conversation ("thanks, that's all for now") rather than only catching explicit exit words.

### Mk2 — Current envisioned scope

- Multiple reasoning-engine integrations (dedicated functions for Gemini, Claude, and other major providers, plus locally hosted open source models, so the LLM is user-selectable including private on-device options)

- Free-tier accessibility for users without a paid Gemini key (Mk1 assumes a billing-enabled Gemini key, because live grounding needs one: on the free tier the 3.x models cannot ground and 2.5 Flash grounds but caps at about twenty requests per day. For a distributable product this paid dependency is a real barrier, so a future version would offer a graceful path for free-tier users, either running without live grounding, falling back to 2.5 Flash within its daily cap, or routing grounding through a separate search API with a more generous free tier such as Brave Search or Tavily paired with a free-tier LLM. This supersedes the earlier idea of a selective-grounding router, which existed only to work around free-tier quota and was made unnecessary by enabling billing, as recorded in BUILDLOG Entries 18 and 19.)

- Semantic conversation-ending detection (Mk1 ends only on explicit exit words like "goodbye" or "stop"; natural wind-downs like "thanks, that's all for now" or "I'll let you know if I need anything else" are intent signals, not fixed phrases, and cannot be caught by string matching, so Mk2 would use the LLM to judge whether the user means to end)

- Persistent memory across sessions (Vaani takes notes on tasks, people, and personal context, and can refer to them in future conversations)

- Adaptive noise-floor threshold for silence detection (Mk1 uses a fixed threshold calibrated in a quiet environment; a robust version would continuously sample ambient noise and set the speech threshold relative to it, so detection holds up in noisy real-world settings like streets or cafes)

- Wake word detection (needs hardware-level battery optimisation to be viable. Solutions to be explored before taking a call)

- Bhasha translate mode (needs further thought on mic pickup of opposite party in real environments)

- TTS English pronunciation quality (confirmed model-level limitation in Bulbul across all speakers; English text from Latin script is mispronounced, including romanized Indian place names, and English is expected to be the dominant usage language; fix is to route the English path to a second provider with strong Indian-English voices, e.g. Google Cloud TTS or Azure, behind a provider-agnostic speak() function while keeping Sarvam for Indic languages; architecture designed, deferred due to cloud billing setup friction. Or maybe feed the English response phonetically to the TTS layer? Further exploration needed)

- Text normalization pass between the LLM and TTS (deterministically expand alphanumeric codes, identifiers, and abbreviations so pronunciation does not depend on prompt instructions holding; currently handled by a system prompt rule that will not scale to every pattern)

- Code-mixed translation quality (romanized English spoken inside an Indic sentence, for example "I need to log an expense" said within a Telugu utterance, is mistranslated by Sarvam before any downstream logic sees it; surfaced when it defeated the new transaction-intent classifier, which can only act on the English it is handed, so the lost intent cannot be recovered downstream)

