# Vaani Build Log

A chronological record of observations, decisions, and tradeoffs made while building Vaani. Newest entries at the bottom.

---

## Entry 0: Project origin, initial planning, and early tooling decisions (Steps 1 to 4)

**The starting point: a personal itch.** Vaani began with a recurring frustration: thinking of questions while walking or doing something hands on, phone in pocket, earphones on, and losing the curiosity by the time an app was opened and the question typed out. The base concept was a hands free voice interface to an LLM, triggered from TWS earphones. A live translation feature was layered on top to make it genuinely useful for an Indian context, where conversations around you can be in any of a dozen languages.

**Initial scope: three states, two command words.** The first full design was a state machine: sleeping (wake word listening), active (LLM conversation), and translating (live language translation, triggered and exited by voice commands). "Bhasha" to enter translate mode, "Bas" to exit, both detected via string matching on the transcript rather than separate wake word models, since training custom wake words was assessed as too time consuming. This three state design was the mental model carried into the actual build, even before any code was written.

**Tech stack was chosen before any code.** The deliberate framing was: wake word locally (cost, privacy), STT via Sarvam (saarika), translation via Sarvam (speech to text translate), LLM reasoning as a swappable component, TTS via Sarvam (bulbul). Sarvam's models are built specifically for Indian languages and accents, which made them the natural foundation for a product whose entire premise is multilingual Indian voice interaction. Wake word (originally planned via Picovoice/Porcupine) and the LLM layer were the two components not on Sarvam's stack, for cost and capability reasons respectively, both flagged early as the most likely points of friction.

**Picovoice's free tier had disappeared.** The first thing actually attempted from this plan was wake word, since it was assessed as the most technically uncertain piece. Picovoice, the default choice for Porcupine, turned out to have deprecated personal free tier accounts, leaving only a 7 day trial before a $6,000/year Foundation plan. Replaced with OpenWakeWord, a fully local, open source alternative with pre built models including "Hey Jarvis," requiring no API key and no recurring cost. First instance of a recurring theme across this build: a plan made on paper had to be revised against what was actually available, and the revision (OpenWakeWord) turned out to be a better long term fit for the local first framing than the original choice anyway.

**pyaudio could not be built on Windows.** Installing pyaudio for microphone capture failed with a Visual C++ Build Tools requirement, since it compiles a C extension from source. Rather than install several gigabytes of build tooling for one library, switched to sounddevice plus soundfile, which install via pre built wheels and cover capture and playback equally well.

**Windows Defender blocked Python 3.14's own compiled extensions.** The most disruptive issue of the early setup. Installing google-generativeai failed with "DLL load failed while importing cygrpc: An Application Control policy has blocked this file." The same error reappeared for sklearn, a dependency pulled in by openwakeword. Root cause: Python 3.14 is new enough that Windows Defender's reputation system has no trust history for these .pyd files and blocks them by default, even on a personal machine with no corporate policy involved. Fixed by adding Defender exclusions for both the Python install directory and the project folder, followed by a full machine restart, not just a VS Code restart, for the exclusions to take effect. Running VS Code as Administrator afterward reduces recurrence. This single issue cost more time than every other Step 1 to 4 issue combined, and is the kind of thing that would be invisible on Mac or Linux.

**Replaced google-generativeai with google-genai.** Separately from the Defender issue, moved away from google-generativeai, which depends on grpc, toward google-genai, a newer SDK using plain HTTPS. This sidesteps the grpc/cygrpc problem at the root rather than patching around it.

**Picked Gemini over Claude, DeepSeek, and Sarvam's own LLM, before writing a line of LLM code.** Claude was ruled out on cost grounds for a personal project, since Anthropic's API has no free tier. DeepSeek was ruled out over data handling concerns for an assistant that will eventually carry personal context. Sarvam's own LLM was set aside since it is not yet positioned for general reasoning tasks. Landed on Gemini 2.5 Flash via AI Studio, the only option with a genuinely indefinite free tier. Decided early to isolate this choice behind a single get_llm_response function, anticipating that it would need to change again later.

**sarvamai, not sarvam-ai.** Minor but easy to lose time on: the correct PyPI package name has no hyphen. `pip install sarvam-ai` returns no matching distribution.

**Sarvam STT needs a file, not an array.** The transcribe endpoint expects a WAV file, not a raw numpy array, so every recording is written to a temporary file via soundfile before the API call.

**Windows file handle locking broke the temp file cleanup.** After writing audio to a NamedTemporaryFile and sending it to Sarvam inside a with open(...) block, os.unlink() failed with "the process cannot access the file because it is being used by another process." NamedTemporaryFile holds its own handle separate from the with open() block, and Windows enforces this strictly where Linux and Mac do not. Fixed with an explicit tmp.close() immediately after writing, before the file is reopened for the API call.

**saarika:v2 was deprecated mid build.** The first STT call returned a clean BadRequestError naming the exact replacement model, saarika:v2.5. Five minute fix, but a reminder that Sarvam's API surface is actively moving and model names in any tutorial or doc snippet should be treated as provisional.

**language_code="unknown" was the right default, not a placeholder.** Passing "unknown" triggers Sarvam's automatic language detection across Indian languages. Given Vaani's premise, that either the user or someone near them could be speaking any Indian language, hardcoding a language code would have been actively wrong, not just less flexible. Confirmed the response object returns both .transcript and a populated .language_code (for example "te-IN") only when "unknown" was passed, meaning no separate detection call is needed later.

**First product decision surfaced by a technical test.** Testing STT across Hindi, Telugu, and Kannada returned accurate transcripts, but all in native script. This raised a real design question for Step 5 onward: whether to translate non English transcripts to English before sending to Gemini, and translate Gemini's response back to the user's detected language before TTS. Logged as the first decision in this project where a passing test still changed the plan.

**sd.wait() is not optional.** sd.rec() returns immediately since it runs asynchronously; without sd.wait(), the script proceeds against an incomplete audio array.

**A mistranscribed name, correctly attributed.** "Srivar" came back as "Sriward" in one test. Full sentences in the same session, across three languages, transcribed correctly, so this was logged as a likely microphone or proper noun issue rather than a flag on Sarvam STT's general reliability.

---

## Entry 1: Project setup and scoping (repo creation)

**Renamed the project from Jarvis Mk1 to Vaani Mk1** before creating the GitHub repo. Renaming before the first commit meant no messy history rewrites later.

**Scoped wake word detection out of Mk1.** Initial plan assumed always-on wake word detection ("Hey Jarvis") via OpenWakeWord. Realised during planning that always-on mic scanning is heavily battery-intensive, and companies like Apple and Google solve this through deep hardware integration that commodity TWS earphones do not have. This is likely why OpenAI and Anthropic have not shipped voice invocation either. Decision: Mk1 uses a TWS gesture (button press) for invocation. Wake word moves to Mk2, conditional on a viable low-power approach.

**Scoped the Bhasha translate mode out of Mk1.** The live translation feature (for example, understanding an auto driver speaking Tamil) has an unresolved hardware problem: earphone mics are tuned to pick up the wearer's voice, not the opposite party's. Shipping a flaky version would be worse than not shipping it. Deferred to Mk2 pending real-environment testing.

**Separated README and PRODUCT.md.** README covers what the project is and how to run it. PRODUCT.md covers the problem, the reasoning behind the stack, and the build plan.

## Entry 2: Gemini integration (Step 5)

**Chose Gemini 2.5 Flash as the Mk1 reasoning layer** primarily because it is the only major LLM provider offering free API access, which makes development and testing practical without upfront cost. The LLM is deliberately isolated behind one function (get_llm_response) so swapping providers later touches one place.

**Debated and parked internet grounding.** Without live web access, hallucination risk on factual queries is real, and grounded responses can cite sources. But grounding adds a search step to an already 4-call-per-turn pipeline (latency), and each provider implements it differently (Gemini grounding is Gemini-specific), which would break the clean swappability design. Decision: ship Mk1 without grounding, feel the latency and the "I don't know" responses in practice, then treat grounding as P0 for Mk2. Longer term plan: one integration function per major provider, plus one for locally hosted open source models.

**Identified persistent memory as a future feature.** Chat sessions hold context within a conversation but reset between sessions. A real assistant needs to remember tasks, people, and personal context across days. Added to Mk2.

**First real debugging war story.** Passing the STT result object directly into Gemini's send_message raised a type error: the method expected a string but received an object. Initial hypothesis (client initialisation format) was wrong. Tracing the data flow showed the Sarvam STT response is an object with .transcript and .language_code fields, and only the transcript string should cross the API boundary. Lesson: every API boundary is a contract, and type errors usually point at exactly which contract was violated.

## Entry 3: TTS and the misread error (Step 6)

**Vaani spoke for the first time.** Sarvam TTS (bulbul:v2, speaker anushka) returns audio as Base64 inside JSON, since JSON cannot carry raw binary. Decode, write to a temp WAV, play through sounddevice. Latency felt acceptable.

**Misdiagnosed a 503 as a code bug.** First Telugu test crashed with a long traceback. Initial conclusion: "Telugu broke it." The actual final line of the traceback was a 503 UNAVAILABLE from Google's servers (model overloaded). The request never reached Gemini at all, and the same code worked minutes later. Lesson: read the error before forming the hypothesis, and distinguish server-side failures from client-side bugs.

**Discovered a product requirement from the crash.** A voice assistant cannot show a stack trace. Any API failure should be caught and spoken: "sorry, I'm having trouble right now." Error handling is a core requirement for a screenless product, not a polish item. To be built with the conversation loop.

**A surprise that challenged the architecture.** With the TTS language hardcoded to en-IN, a Telugu run worked anyway: Gemini responded in Telugu script and bulbul:v2 spoke it, with a slightly off accent. This raised the question of whether the translation legs are needed at all (skipping them would cut 2 API calls per turn). Decided to keep the translation pipeline for two reasons: Gemini's response language is inconsistent for non-English input (sometimes native script, sometimes Latin script, sometimes English), and LLM reasoning quality is strongest in English. Logged a future experiment: an isolated TTS test harness fed with real Gemini outputs of varying scripts, run only if Mk1 latency proves too high.

## Entry 4: The full multilingual loop (Step 7)

**Wired both translation legs.** The STT-detected language_code drives everything: whether to translate inbound, whether to translate outbound, and the TTS target language. English queries skip both translation calls entirely, keeping the common case fast. Tested end to end in English, Hindi, and Telugu.

**System prompt iteration after real usage.** The first prompt draft said "be decisive, do not front-load uncertainty," yet Vaani still opened answers with disclaimers ("the best is subjective...") and once demanded trip details before estimating a drive time. Diagnosis: caveat behaviour is different from uncertainty hedging, and LLM training rewards thoroughness that voice cannot afford, because the listener must sit through every word. Fix: explicit instructions to never open with disclaimers, to answer first and caveat after in one short phrase only if it matters, and to make stated assumptions instead of asking follow-up questions. Before/after difference was immediate and large. Lesson: system prompts are never done after one draft; real usage exposes the gaps.