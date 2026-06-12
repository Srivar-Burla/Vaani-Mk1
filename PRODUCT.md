# Vaani: Product Context

## The Problem

Voice-based AI interactions are largely broken for Indian users today, in three specific ways.

First, the major AI assistants like Gemini, ChatGPT, are meaningfully better at text than voice. The voice interfaces feel bolted on rather than native. The quality gap is noticeable.

Second, the drop in quality is even sharper when the language shifts away from English. Indic language voice interactions (Hindi, Telugu, Kannada, etc) are poorly handled by western AI stacks not built with these languages and accents in mind.

Third, if you want voice interaction with a specific LLM, say, Claude instead of Gemini, there is no clean way to do it. Voice is bundled with the model. There is no orchestration layer that gives you control over which reasoning engine sits underneath.

These are not capability problems. The AI is capable enough. They are accessibility and architecture problems.

## Why Sarvam's Stack

Sarvam AI has built their STT and TTS models specifically for Indian languages and accents. Transcription quality on Hindi, Telugu, and Kannada is noticeably better than generic western models. Their TTS produces natural-sounding Indian voice output rather than the flat, accented output you get from most English-first TTS systems.

For a voice assistant that needs to feel seamless to an Indian user speaking in their own language, Sarvam's stack is the right foundation.

## The Solution

Vaani is a thin orchestration layer that separates voice I/O from reasoning.

The flow is: user speaks (in any supported Indian language) → Sarvam STT transcribes and detects the language → transcript is translated to English → passed to the LLM of the user's choice → English response is translated back to the user's language → Sarvam TTS speaks it back in a natural Indian voice.

The key design decision is that the LLM is swappable. Gemini, Claude or other open source models, changing the reasoning engine requires changing one function. Everything else stays the same. This is the orchestration layer that doesn't exist natively in any of the current consumer AI products.

Gemini 2.5 Flash is the reasoning layer for Mk1, chosen primarily because it is the only major LLM provider that offers free API access, which makes it practical for development and testing without upfront costs. Swapping to Claude or an open source model in a future version requires changing one function.

For Mk1, invocation is handled via a gesture on the TWS (button press). Always-on wake word detection has been deliberately scoped out. Without deep hardware-level integration of the kind Siri and Gemini have, always-on mic scanning is too battery-intensive to be a viable approach on commodity earphones.

## Why I Built This

I kept thinking of questions while walking or working on something hands-on, phone in pocket, earphones on. And by the time I'd opened an app and typed it out, the curiosity had already faded. I wanted to just ask, out loud, and get an answer.

As AI-native product development becomes the norm, I wanted to close the gap between understanding how APIs work conceptually and actually wiring them together, hitting the edges where things break, making deliberate tradeoffs, and shipping something real. Also, Building the solution yourself is more interesting than waiting for someone else to.

## Build Plan

### Mk1 — Core Conversation Loop (current)
- [x] Sarvam STT working across Hindi, Telugu, Kannada
- [x] Gemini integration as reasoning layer
- [ ] Sarvam TTS speaks response back to user
- [ ] Full conversation turn: voice in → voice out
- [ ] TWS gesture invocation
- [ ] Silence detection to end user turn dynamically

### Mk2 — Considered but deferred
- Wake word detection (needs hardware-level battery optimisation to be viable)
- Bhasha translate mode (needs further thought on mic pickup of opposite party in real environments)
- Web search grounding (P0 for Mk2: without live information access, hallucination risk on factual queries is high; grounded responses can also cite sources)
- Persistent memory across sessions (Vaani takes notes on tasks, people, and personal context, and can refer to them in future conversations)