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

Gemini 2.5 Flash is the reasoning layer for Mk1, chosen primarily because it is the only major LLM provider that offers free API access, which makes it practical for development and testing without upfront costs. Swapping to Claude or an open source model in a future version requires changing one function.

For Mk1, invocation is handled via a gesture on the TWS (button press). Always-on wake word detection has been deliberately scoped out. Without deep hardware-level integration of the kind Siri and Gemini have, always-on mic scanning is too battery-intensive to be a viable approach on commodity earphones. 

The spoken language is detected fresh on every turn during conversation. This ensures Vaani handles mid-conversation language changes seamlessly: a user can ask one question in English, the next in Telugu, and switch back, with Vaani responding in whatever language each question was asked. The conversation is not locked to a single language at the start.

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
- [ ] Error handling for API failures (spoken, not crashed)
- [ ] TWS gesture invocation
- [ ] Silence detection to end conversation

## Where Vaani Is Headed

Mk1 proves the core loop: speak in any supported Indian language, and Vaani listens, reasons, and replies in that same language. Several features are deliberately deferred to Mk2, each addressing a real gap rather than just adding surface area.

**Bhasha (live translation mode).** A spoken command ("Bhasha") that switches Vaani into a two-way interpreter: it listens to a second person speaking another language and relays the conversation between both parties in real time, useful when you and the person in front of you do not share a language. Deferred because it needs the earphone mic to reliably capture a second speaker's voice, an unsolved hardware question in real environments.

**Persistent memory across sessions.** Today Vaani remembers everything within a single conversation but forgets once it ends. Mk2 gives Vaani the ability to take durable notes on tasks, people, and personal context, and recall them in future conversations, so it behaves like an assistant that actually knows you over time rather than a fresh stranger each session.

**Your choice of reasoning engine.** Vaani's architecture deliberately isolates the LLM so it can be swapped. Mk2 builds dedicated integration functions for each major provider (Gemini, Claude, and others) plus a path for locally hosted open source models, letting the user choose which intelligence sits underneath the voice, including private on-device options.

**Web search grounding.** Without live information, Vaani can only answer from training data and must say "I don't know" for anything current. Mk2 adds grounded search so factual and time-sensitive questions get accurate, sourced answers.

**Better English voice, and natural conversation endings.** Two known Mk1 limitations: English pronunciation (routing the English path to a stronger Indian-English voice provider) and detecting when a user naturally winds down a conversation ("thanks, that's all for now") rather than only catching explicit exit words.

### Mk2 — Current envisioned scope

- Multiple reasoning-engine integrations (dedicated functions for Gemini, Claude, and other major providers, plus locally hosted open source models, so the LLM is user-selectable including private on-device options)

- Semantic conversation-ending detection (Mk1 ends only on explicit exit words like "goodbye" or "stop"; natural wind-downs like "thanks, that's all for now" or "I'll let you know if I need anything else" are intent signals, not fixed phrases, and cannot be caught by string matching, so Mk2 would use the LLM to judge whether the user means to end)

- Web search grounding (P0 for Mk2: without live information access, hallucination risk on factual queries is high; grounded responses can also cite sources(only if the User asks))

- Persistent memory across sessions (Vaani takes notes on tasks, people, and personal context, and can refer to them in future conversations)

- Adaptive noise-floor threshold for silence detection (Mk1 uses a fixed threshold calibrated in a quiet environment; a robust version would continuously sample ambient noise and set the speech threshold relative to it, so detection holds up in noisy real-world settings like streets or cafes)

- Wake word detection (needs hardware-level battery optimisation to be viable. Solutions to be explored before taking a call)

- Bhasha translate mode (needs further thought on mic pickup of opposite party in real environments)

- TTS English pronunciation quality (confirmed model-level limitation in Bulbul across all speakers; English text from Latin script is mispronounced, including romanized Indian place names, and English is expected to be the dominant usage language; fix is to route the English path to a second provider with strong Indian-English voices, e.g. Google Cloud TTS or Azure, behind a provider-agnostic speak() function while keeping Sarvam for Indic languages; architecture designed, deferred due to cloud billing setup friction. Or maybe feed the English response phonetically to the TTS layer? Further exploration needed)

- Text normalization pass between the LLM and TTS (deterministically expand alphanumeric codes, identifiers, and abbreviations so pronunciation does not depend on prompt instructions holding; currently handled by a system prompt rule that will not scale to every pattern)

