# Vaani

Vaani is a hands-free, multilingual voice assistant built for Indian languages and accents. It started from an everyday problem: questions would come to mind while I was walking or working with my hands, but taking out my phone, opening an app, and typing interrupted the moment. I wanted to invoke an assistant from my earphones, ask the question naturally, and hear the answer without reaching for a screen.

Mk1 is an early working version of that product. A Play or Pause gesture on a TWS earbud invokes Vaani, which can understand supported Indian languages, reason through an LLM, search the live web when needed, and speak the response back in the language used for that turn.

## What Vaani can do

- Start listening from a TWS Play or Pause gesture, with a Start Listening button in the web interface as a fallback.
- Detect the language on every turn and support language changes within one conversation.
- Translate non-English speech to English for reasoning, then translate the response back before speaking.
- Use Google Search conditionally when a question requires current information.
- Maintain conversational context across multiple turns in the same session.
- Call external APIs to perform actions, not only answer questions. Transaction recording is the first implementation: Vaani converts a spoken description into structured fields, confirms the details, and submits them to a finance-tracker backend.
- Save timestamped session logs containing transcripts, pipeline output, and errors for troubleshooting.

## Architecture

```text
TWS Play/Pause or Start Listening button
                    |
                    v
Sarvam STT and per-turn language detection
                    |
                    v
Conditional translation to English
                    |
                    v
Gemini reasoning and optional Google Search
                    |
                    v
Conditional translation to the user's language
                    |
                    v
Sarvam TTS and audio playback
```

The voice pipeline and reasoning layer are deliberately separated. Gemini is currently isolated behind `get_llm_response()`, so another reasoning provider can replace it without rebuilding speech recognition, translation, or speech synthesis. Action flows can call external APIs behind the same voice interface.

## Technology stack

- Speech-to-text and language detection: Sarvam Saarika v2.5
- Translation: Sarvam Translate
- Reasoning: Google Gemini 3.1 Flash-Lite
- Live information: conditional Gemini Google Search grounding
- Text-to-speech: Sarvam Bulbul v2, using the Anushka voice
- Primary interface: Python standard-library HTTP server with Server-Sent Events (web_ui.py), a mobile-first chat view and a step-by-step pipeline view
- TWS gesture integration: Windows Runtime System Media Transport Controls
- Audio capture and playback: sounddevice and soundfile

## Running locally

The Mk1 desktop and TWS integration currently target Windows.

1. Clone the repository and open the project directory.
2. Install the Python dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root:

   ```dotenv
   SARVAM_API_KEY=your_sarvam_api_key
   GEMINI_API_KEY=your_gemini_api_key
   FINANCE_API_URL=your_finance_tracker_api_url
   ```

   `FINANCE_API_URL` is required only for action flows that write to the finance-tracker backend.

   **A billing-enabled Gemini key is recommended.** Vaani's live web grounding uses Gemini's Google Search tool, which works only on a billing-enabled key. Without one, you have three options:

   - Set the chat model in `create_chat_session()` (in `main.py`) to `gemini-2.5-flash`. It grounds on the free tier but is capped at about twenty requests per day, which is enough to try Vaani out. This is the simplest no-cost path.
   - Keep `gemini-3.1-flash-lite` but remove the Google Search tool from `create_chat_session()`. Vaani then runs uncapped on the free tier, answering from the model's own knowledge with no live web access.
   - For live grounding without a paid Gemini key, integrate a separate search API with a more generous free tier, such as [Brave Search](https://brave.com/search/api/) (2,000 queries per month) or [Tavily](https://tavily.com/) (1,000 per month), and feed the results to a free-tier LLM. This is not built into Mk1.

4. Start Vaani:

   ```powershell
   python web_ui.py
   ```

   Open `http://localhost:8765` in a browser. Use the Start Listening button or a TWS Play or Pause gesture to begin a conversation. To access Vaani from a phone on the same Wi-Fi network, use the LAN address printed on startup.

   The original Tkinter desktop interface is still available as a fallback:

   ```powershell
   python ui.py
   ```

For development and full terminal output without any interface, run:

```powershell
python main.py
```

All entry points write timestamped diagnostic logs under `logs/`. The directory is excluded from Git.

## Project documentation

The project keeps product thinking, engineering history, and agent instructions separate so each document has a clear purpose:

- [`README.md`](README.md) is the public introduction. It explains what Vaani does, how it works, and how to run it.
- [`PRODUCT.md`](PRODUCT.md) contains the product context, the problem being solved, current Mk1 scope, roadmap, and capabilities being considered for later versions.
- [`BUILDLOG.md`](BUILDLOG.md) is the chronological engineering record. It captures architecture decisions, tradeoffs, rejected approaches, debugging lessons, and why earlier decisions changed.
- [`AGENTS.md`](AGENTS.md) defines the working agreement for AI coding agents contributing to this repository, including architecture boundaries and documentation rules.
- [`Claude.md`](Claude.md) provides the same working agreement in the project-instruction filename used by Claude-based development tools.

## Project status

Vaani Mk1 is in active development. The multilingual conversation loop, mobile-first web interface, hands-free TWS invocation, conditional web grounding, session logging, and transaction recording via external API are working. See [`PRODUCT.md`](PRODUCT.md) for the current build plan and future direction, and [`BUILDLOG.md`](BUILDLOG.md) for the decisions behind the implementation.
