import os
import sys
import datetime
import atexit
import tempfile
import numpy as np
import sounddevice as sd
import soundfile as sf
from sarvamai import SarvamAI
from google import genai
from google.genai import types
from dotenv import load_dotenv
import base64
import traceback
import json
import requests

load_dotenv()

# Tee: writes every print() and traceback to both the terminal and the session log file.
# Both stdout and stderr are teed so tracebacks from speak_error also land in the log.
class Tee:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            s.write(data)
    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass

SAMPLE_RATE = 16000
#DURATION = 10
CHUNK_DURATION = 0.1
SILENCE_THRESHOLD = 0.005
SILENCE_CHUNKS = 20
EXIT_PHRASES = ["goodbye", "bye", "stop" , "that's all for now"]
#EXIT_PHRASES = ["bye"]

TRANSACTION_TRIGGER_PHRASES = ["log a transaction", "record a transaction", "add an expense", "log expense", "record expense", "save a transaction", "add a transaction", "record a payment", "log a payment"]

# Base URL for the personal finance tracker API (set in .env as FINANCE_API_URL)
FINANCE_API_URL = os.getenv("FINANCE_API_URL")


SYSTEM_PROMPT = """You are Vaani, a voice assistant. "

You are talking to your user through earphones. They are often walking, commuting, or doing something with their hands while talking to you.

Your personality: you are a capable personal assistant. Warm, direct, and honest. If you disagree with the user or think they are wrong about something, say so politely. Never just tell the user what they want to hear.

Everything you say will be spoken aloud by a text to speech system. Follow these rules strictly:

Keep responses short. Two to four sentences for most answers. This is a voice conversation, not an essay.

Never use bullet points, numbered lists, headings, or any markdown formatting. Use connective language instead, like first, then, finally.

For longer explanations, structure your response sequentially and break it at natural boundaries, like after completing one concept and before starting the next. At these points, check in with the user before continuing. Vary how you ask: "should I go on?", "are you following me so far?", "any questions before I continue?". Never break midway through a single idea or thought, as this disrupts the user's understanding.

Avoid abbreviations and acronyms that sound wrong when spoken. Say "as soon as possible" not ASAP. If an acronym is widely spoken aloud, like API or UPI, it is fine to use. Spell out alphanumeric codes and identifiers the way a person would say them aloud. For example, write "National Highway forty four" not "NH44", and "highway sixty six" not "NH66". Expand any short form that a listener would otherwise hear as a jumble of letters and numbers.

Be decisive. Give a clear answer first, then offer to elaborate. Do not front-load your uncertainty with hedges.

Never begin a response with disclaimers, caveats, or qualifiers like "it depends", "this is subjective", or "the best can vary from person to person". The user knows estimates are estimates and recommendations are opinions. Answer directly with your best recommendation or estimate first. Mention an important caveat only after the answer, in one short phrase, and only if it genuinely matters.

If a question can be reasonably answered with an assumption, make the assumption and state it briefly rather than asking the user for more details. For example, if asked how long a drive takes, assume a car and typical traffic, and say so in passing.

If you do not know something or are not confident, say "I don't know" plainly. Do not guess or make things up. You have access to Google Search and can use it when a question requires live or current information. Use it when needed; don't call it for timeless questions.

Numbers, dates, and currency should be spoken naturally. Say "three thirty in the afternoon" not "15:30". Say "twenty five thousand rupees" not "Rs. 25,000". Do not use "-" in your responses. """


sarvam = SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))

# llm_client: currently Gemini. Kept generic so swapping providers later
# (Claude, open source models) doesn't require renaming this throughout the file.
llm_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
# Factory used by both terminal (main.py __main__) and GUI (ui.py) to create
# a fresh session per conversation run.
def create_chat_session():
    return llm_client.chats.create(
        # Chat model is gemini-2.5-flash, NOT 3.1-flash-lite. Reason: Google Search
        # grounding (the tool below) is free on the 2.5 family but returns an instant
        # 429 RESOURCE_EXHAUSTED on the 3.x family on our tier. Since every chat turn
        # attaches the search tool, a 3.x model made every conversational reply fail.
        # The transaction-extraction calls elsewhere don't use grounding, so they stay
        # on 3.1-flash-lite. See BUILDLOG for the full diagnosis.
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            # google_search: Gemini decides per turn whether to call it (on-demand grounding).
            # No forced search — timeless questions go straight to the model's knowledge.
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    )

def get_llm_response(chat_session, user_text):
    response = chat_session.send_message(user_text)
    u = response.usage_metadata
    print(f"[Gemini] tokens  in={u.prompt_token_count}  out={u.candidates_token_count}  total={u.total_token_count}")
    return response.text

def record_until_silence():
    has_spoken = False
    silence_counter = 0
    collection = []

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32') as stream:
        while silence_counter <= SILENCE_CHUNKS:
            chunk, _ = stream.read(int(CHUNK_DURATION * SAMPLE_RATE))
            collection.append(chunk)

            volume = np.abs(chunk).mean()

            if volume > SILENCE_THRESHOLD:
                has_spoken = True
                silence_counter = 0          # speech resets the counter
            elif has_spoken:
                silence_counter += 1          # only count silence after speech starts

        audio = np.concatenate(collection, axis=0)
        return audio

def vaani_output(output, user_lang_code, ui_queue=None):
    # Signal the UI that Vaani is about to speak, before any processing
    if ui_queue is not None:
        ui_queue.put({"type": "state", "value": "Speaking"})

    if user_lang_code != "en-IN":
        print("Vaani (in English):", output)
        translation = sarvam.text.translate(
            input=output,
            source_language_code="en-IN",
            target_language_code=user_lang_code
        )
        vaani_reply = translation.translated_text
    else:
        vaani_reply = output

    print("Vaani:", vaani_reply)

    # Push transcript: English source + translated reply (translated is None if already English)
    if ui_queue is not None:
        ui_queue.put({
            "type": "transcript", "speaker": "Vaani",
            "text": output,
            "translated": vaani_reply if user_lang_code != "en-IN" else None
        })

    # Vaani speaks
    tts_response = sarvam.text_to_speech.convert(
        text=vaani_reply,
        model="bulbul:v2",
        target_language_code=user_lang_code,
        speaker="anushka"
    )
    
    for segment in tts_response.audios:
        audio_bytes = base64.b64decode(segment)

        tts_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tts_file.write(audio_bytes)
        tts_file.close()
        
        speech, rate = sf.read(tts_file.name)
        sd.play(speech, rate)
        sd.wait()
        
        os.unlink(tts_file.name)

def speak_error(exception, user_lang_code, ui_queue=None):
    # Prints the full traceback to the terminal first so you can see the exact error,
    # then speaks a natural exit message in the user's language via vaani_output.
    # Falls back to a print if TTS itself also fails.
    error_text = str(exception).lower()

    # Always print the full stack trace to terminal before Vaani speaks
    traceback.print_exception(type(exception), exception, exception.__traceback__)

    # Gemini 429 / RESOURCE_EXHAUSTED — hard quota limits (RPM, TPM, or RPD)
    if "429" in error_text or "resource_exhausted" in error_text or "resourceexhausted" in error_text:
        if "requestsperday" in error_text or "daily" in error_text:
            # Daily request quota exhausted — resets at midnight Pacific
            message = ("I apologize, but we've completely maxed out our daily quota. "
                       "I'm locked out for the rest of the day — I'll be fully refreshed "
                       "and ready to help you tomorrow morning. Signing off for now.")
        elif "billing" in error_text or "plan and billing" in error_text:
            # Token or project-level quota — Google surfaces this as a billing/plan message.
            # Usually TPM (tokens per minute); recoverable after ~60 seconds.
            message = ("I've hit a token limit on the AI side — I processed too much text too quickly. "
                       "I'm going to stop here. Please restart me in about sixty seconds, "
                       "and if it keeps happening, check your API quota in Google AI Studio.")
        else:
            # Minute-based RPM limit — recoverable, but ending the session
            message = ("I've hit my processing limit for this minute. "
                       "I'm going to have to stop here — please restart me in about sixty seconds.")

    # Gemini 503 "high demand" — free tier returns this when quota is exhausted
    # Checked separately from the network block because the cause is quota, not connectivity
    elif "high demand" in error_text:
        message = ("I apologize, but I've run into a quota limit and can't take any more questions "
                   "right now. I'm going to stop here — try restarting me in a few minutes, "
                   "or come back tomorrow morning if the daily limit has been reached.")

    # Genuine network or connection failures — Sarvam outage, no internet, etc.
    elif isinstance(exception, (ConnectionError, TimeoutError, OSError)) or \
         any(k in error_text for k in ("connection", "network", "timeout", "unreachable", "unavailable", "503")):
        message = ("I'm having trouble reaching the services I need right now. "
                   "I'm going to stop here — please check your connection and restart me when you're ready.")

    # Catch-all for any other unexpected error
    else:
        message = ("Something went wrong on my end. "
                   "I'm going to stop here — please restart me when you're ready.")

    try:
        # Speak the exit message in the user's language via the normal TTS pipeline
        vaani_output(message, user_lang_code, ui_queue)
    except Exception as tts_err:
        # If TTS itself fails, just log — we're already exiting
        print(f"[speak_error] Could not speak error message: {tts_err}")

def extract_transaction_fields(user_text):
    # One-shot Gemini call to pull structured transaction fields from the user's description.
    # Kept separate from chat_session so these extraction turns don't appear in
    # Vaani's conversational memory (chat_session accumulates every send_message call).
    # Returns a dict; fields Gemini couldn't find are None.
    prompt = f"""Extract transaction details from the text below and return ONLY a JSON object — no markdown, no explanation, nothing else.

Text: "{user_text}"

Return a JSON object with exactly these keys:
- name: merchant or transaction name (string, e.g. "Zomato"), or null
- amount: numeric amount as a float (e.g. 200.0), or null
- category: one of Food, Travel, Fitness, Entertainment, Shopping, Utilities, Healthcare, Others
- payment_medium: one of UPI, Cash, Credit Card, Wallet, Others
- payment_source: specific source if mentioned (e.g. "SBI UPI", "HDFC Credit Card"), or null
- notes: any extra context worth keeping, or null

Example: {{"name": "Zomato", "amount": 200.0, "category": "Food", "payment_medium": "UPI", "payment_source": null, "notes": null}}"""

    response = llm_client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt
    )
    raw = response.text.strip()
    # Extract the JSON object even if Gemini wraps it in markdown fences
    raw = raw[raw.index("{"):raw.rindex("}") + 1]
    return json.loads(raw)

def extract_field_value(field_name, user_answer):
    # Lightweight one-shot Gemini call to extract a single missing field from a
    # short follow-up answer (e.g. "two hundred" → 200.0 for the amount field).
    # Separate from chat_session for the same reason as extract_transaction_fields.
    prompts = {
        "name": f'Extract the merchant or transaction name from: "{user_answer}". Return only the name, nothing else.',
        "amount": f'Extract the numeric amount from: "{user_answer}". Return only the number as a float (e.g. 200.0), nothing else.',
        "category": f'Classify into one of: Food, Travel, Fitness, Entertainment, Shopping, Utilities, Healthcare, Others. Text: "{user_answer}". Return only the category word.',
        "payment_medium": f'Identify the payment method from: "{user_answer}". Return only one of: UPI, Cash, Credit Card, Wallet, Others.',
        "payment_mode": f'Identify the Payment Mode from:"{user_answer}". Return only one of ICICI, Jupiter, Slice, Amazon Pay, Mobiquick, Splitwise Debt'
    }
    response = llm_client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompts[field_name]
    )
    return response.text.strip()

def post_transaction(fields):
    # POSTs a completed transaction dict to the finance tracker API.
    # Raises an exception on HTTP error or connection failure — caller handles it.
    response = requests.post(
        f"{FINANCE_API_URL}/transactions",
        json=fields,
        timeout=10
    )
    response.raise_for_status()
    return True

def record_transaction(user_lang_code, ui_queue=None):
    # Full transaction recording flow — triggered when user says a trigger phrase.
    # Steps: prompt → describe → extract fields → fill gaps → confirm → POST or cancel.
    # Any exception is caught here and spoken as an inline error so Vaani returns
    # to listening rather than exiting the whole conversation.
    # ui_queue: passed through to vaani_output so the UI stays in sync with sub-states.

    REQUIRED_FIELDS = ["name", "amount", "category", "payment_medium", "payment_mode"]
    FIELD_QUESTIONS = {
        "name": "What's the merchant or transaction name?",
        "amount": "How much did you spend?",
        "category": "Which category should I file this under — Food, Travel, Fitness, Shopping, or something else?",
        "payment_medium": "How did you pay — UPI, cash, credit card, or wallet?",
        "payment_mode": "Which Account did you pay from?"
    }
    YES_PHRASES = ["yes", "yeah", "sure", "okay", "ok", "correct", "right", "go ahead", "save", "do it"]

    def push(msg):
        if ui_queue is not None:
            ui_queue.put(msg)

    try:
        # Step 1: ask user to describe the transaction
        vaani_output("Sure, go ahead and describe the transaction.", user_lang_code, ui_queue)

        # Step 2: record, transcribe, and translate the description
        push({"type": "state", "value": "Listening"})
        audio = record_until_silence()
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        try:
            sf.write(tmp.name, audio, SAMPLE_RATE)
            tmp.close()
            with open(tmp.name, "rb") as f:
                desc_query = sarvam.speech_to_text.transcribe(
                    file=("audio.wav", f, "audio/wav"),
                    model="saarika:v2.5",
                    language_code="unknown"
                )
        finally:
            os.unlink(tmp.name)

        desc_text = desc_query.transcript
        user_lang_code = desc_query.language_code  # follow the user's language from here
        print("Transaction description:", desc_text)

        if desc_query.language_code != "en-IN":
            translation = sarvam.text.translate(
                input=desc_text,
                source_language_code=desc_query.language_code,
                target_language_code="en-IN"
            )
            desc_text = translation.translated_text
            print("Translated:", desc_text)

        # Step 3: extract all fields Gemini can find in one shot
        push({"type": "state", "value": "Thinking"})
        fields = extract_transaction_fields(desc_text)
        print("Extracted fields:", fields)

        # Step 4: ask for each required field that came back as None
        for field in REQUIRED_FIELDS:
            if not fields.get(field):
                vaani_output(FIELD_QUESTIONS[field], user_lang_code, ui_queue)

                push({"type": "state", "value": "Listening"})
                audio = record_until_silence()
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                try:
                    sf.write(tmp.name, audio, SAMPLE_RATE)
                    tmp.close()
                    with open(tmp.name, "rb") as f:
                        ans_query = sarvam.speech_to_text.transcribe(
                            file=("audio.wav", f, "audio/wav"),
                            model="saarika:v2.5",
                            language_code="unknown"
                        )
                finally:
                    os.unlink(tmp.name)

                ans_text = ans_query.transcript
                user_lang_code = ans_query.language_code  # re-follow language on each answer
                if ans_query.language_code != "en-IN":
                    translation = sarvam.text.translate(
                        input=ans_text,
                        source_language_code=ans_query.language_code,
                        target_language_code="en-IN"
                    )
                    ans_text = translation.translated_text

                value = extract_field_value(field, ans_text)

                if field == "amount":
                    # Convert to float; fall back to stripping non-numeric chars if needed
                    try:
                        fields[field] = float(value)
                    except ValueError:
                        numeric = "".join(c for c in value if c.isdigit() or c == ".")
                        fields[field] = float(numeric) if numeric else None
                else:
                    fields[field] = value

        # Step 5: read back the full transaction and ask for confirmation
        amount_val = fields.get("amount")
        amount_str = str(int(amount_val)) if isinstance(amount_val, float) and amount_val == int(amount_val) else str(amount_val)

        readback = (
            f"I've got {amount_str} rupees at {fields['name']}, "
            f"under {fields['category']}, paid by {fields['payment_medium']}. "
            f"Shall I save this?"
        )
        vaani_output(readback, user_lang_code, ui_queue)

        # Record and transcribe the yes/no confirmation
        push({"type": "state", "value": "Listening"})
        audio = record_until_silence()
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        try:
            sf.write(tmp.name, audio, SAMPLE_RATE)
            tmp.close()
            with open(tmp.name, "rb") as f:
                conf_query = sarvam.speech_to_text.transcribe(
                    file=("audio.wav", f, "audio/wav"),
                    model="saarika:v2.5",
                    language_code="unknown"
                )
        finally:
            os.unlink(tmp.name)

        conf_text = conf_query.transcript
        user_lang_code = conf_query.language_code  # re-follow language for confirmation reply
        if conf_query.language_code != "en-IN":
            translation = sarvam.text.translate(
                input=conf_text,
                source_language_code=conf_query.language_code,
                target_language_code="en-IN"
            )
            conf_text = translation.translated_text

        conf_text = conf_text.lower()
        print("Confirmation response:", conf_text)

        if any(phrase in conf_text for phrase in YES_PHRASES):
            # Step 6a: user confirmed — build payload and POST to the finance tracker
            api_payload = {
                "name": fields["name"],
                "amount": float(fields["amount"]),
                "category": fields["category"],
                "payment_medium": fields["payment_medium"],
            }
            if fields.get("payment_source"):
                api_payload["payment_source"] = fields["payment_source"]
            if fields.get("notes"):
                api_payload["notes"] = fields["notes"]

            push({"type": "state", "value": "Thinking"})
            post_transaction(api_payload)
            vaani_output(
                f"Done! I've logged {amount_str} rupees at {fields['name']} under {fields['category']}.",
                user_lang_code, ui_queue
            )
        else:
            # Step 6b: user said no or unclear — cancel safely
            vaani_output("No problem, I've cancelled that. What else can I help you with?", user_lang_code, ui_queue)

    except Exception as e:
        # Any failure inside the transaction flow — log it and return to listening.
        # We use a plain message here (not speak_error) because speak_error exits
        # the whole conversation, and a failed transaction log should not do that.
        print(f"[Transaction Error] {type(e).__name__}: {e}")
        try:
            vaani_output("I ran into a problem while logging that transaction. Let's continue our conversation.", user_lang_code, ui_queue)
        except Exception:
            pass

def run_conversation(chat_session, ui_queue=None):
    # Main conversation loop — runs on the calling thread (background thread in UI mode,
    # main thread in terminal mode). Pushes state/transcript dicts to ui_queue when provided;
    # ui_queue=None means terminal mode where all feedback is via print() only.

    def push(msg):
        if ui_queue is not None:
            ui_queue.put(msg)

    print("Vaani is ready. Start Speaking. To end conversation, say 'goodbye', 'bye', 'stop' or 'that's all for now'")

    error_exit = False
    user_query = None  # kept in scope for the goodbye step after the loop

    while True:
        push({"type": "state", "value": "Listening"})
        print("Listening....")
        audio = record_until_silence()
        print("Done recording. Sending to Sarvam STT...")

        # Save to temp WAV file
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, audio, SAMPLE_RATE)
        tmp.close()

        # Send to Sarvam STT
        try:
            with open(tmp.name, "rb") as f:
                user_query = sarvam.speech_to_text.transcribe(
                    file=("audio.wav", f, "audio/wav"),
                    model="saarika:v2.5",
                    language_code="unknown"
                )
        except Exception as e:
            os.unlink(tmp.name)
            speak_error(e, "en-IN", ui_queue)
            error_exit = True
            break

        os.unlink(tmp.name)

        print("User:", user_query.transcript)
        print("User spoke in ", user_query.language_code)

        # Translate to English before Gemini if user spoke another language
        if user_query.language_code != "en-IN":
            print("Detected Language is not English. Translating User query to English for improved reasoning")
            try:
                translation = sarvam.text.translate(
                    input=user_query.transcript,
                    source_language_code=user_query.language_code,
                    target_language_code="en-IN"
                )
                gemini_input = translation.translated_text
                print("User (in English): ", gemini_input)
            except Exception as e:
                # Inbound translation failed — speak error and exit
                speak_error(e, user_query.language_code, ui_queue)
                error_exit = True
                break
        else:
            gemini_input = user_query.transcript

        # Push User transcript: native text always shown; translated text shown only if non-English
        push({
            "type": "transcript", "speaker": "User",
            "text": user_query.transcript,
            "lang": user_query.language_code,
            "translated": gemini_input if user_query.language_code != "en-IN" else None
        })

        if any(phrase in gemini_input.lower() for phrase in EXIT_PHRASES):
            break
        elif any(phrase in gemini_input.lower() for phrase in TRANSACTION_TRIGGER_PHRASES):
            # Hand off to the transaction recording flow — returns to listening when done
            push({"type": "state", "value": "Thinking"})
            record_transaction(user_query.language_code, ui_queue)
        else:
            push({"type": "state", "value": "Thinking"})
            print("Vaani is thinking.....")
            try:
                # Gemini call — most likely failure point (429, 503, network errors)
                llm_response = get_llm_response(chat_session, gemini_input)
            except Exception as e:
                speak_error(e, user_query.language_code, ui_queue)
                error_exit = True
                break

            try:
                # Speak Vaani's reply — vaani_output pushes Speaking state + transcript
                vaani_output(llm_response, user_query.language_code, ui_queue)
            except Exception as e:
                speak_error(e, user_query.language_code, ui_queue)
                error_exit = True
                break

    # Only play the normal goodbye if the user said bye — error exits already spoke their own ending
    if not error_exit and user_query is not None:
        exit_output = "Bye! I'm always here whenever you need me"
        try:
            vaani_output(exit_output, user_query.language_code, ui_queue)
        except Exception as e:
            speak_error(e, user_query.language_code, ui_queue)

    # Signal the UI (if any) that this session has ended and the Start button can come back
    push({"type": "state", "value": "Idle"})


if __name__ == "__main__":
    # Terminal / developer mode: Tee stdout+stderr to a timestamped log file so every
    # print() and traceback lands in both the terminal and the session log.
    os.makedirs("logs", exist_ok=True)
    _session_ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    _log_file = open(os.path.join("logs", f"vaani_{_session_ts}.log"), "w", encoding="utf-8")
    sys.stdout = Tee(sys.__stdout__, _log_file)
    sys.stderr = Tee(sys.__stderr__, _log_file)
    atexit.register(_log_file.close)

    run_conversation(create_chat_session())        