import os
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

load_dotenv()

SAMPLE_RATE = 16000
#DURATION = 10
CHUNK_DURATION = 0.1
SILENCE_THRESHOLD = 0.005
SILENCE_CHUNKS = 20
EXIT_PHRASES = ["goodbye", "bye", "stop" , "that's all for now"]
#EXIT_PHRASES = ["bye"]


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

Numbers, dates, and currency should be spoken naturally. Say "three thirty in the afternoon" not "15:30". Say "twenty five thousand rupees" not "Rs. 25,000". """


sarvam = SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))

# llm_client: currently Gemini. Kept generic so swapping providers later
# (Claude, open source models) doesn't require renaming this throughout the file.
llm_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
chat_session = llm_client.chats.create(
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

def vaani_output(output, user_lang_code):
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

def speak_error(exception, user_lang_code):
    # Prints the full traceback to the terminal first so you can see the exact error,
    # then speaks a natural exit message in the user's language via vaani_output.
    # Falls back to a print if TTS itself also fails.
    error_text = str(exception).lower()

    # Always print the full stack trace to terminal before Vaani speaks
    traceback.print_exception(type(exception), exception, exception.__traceback__)

    # Gemini 429 / RESOURCE_EXHAUSTED — hard quota limits (RPM, TPM, or RPD)
    if "429" in error_text or "resource_exhausted" in error_text or "resourceexhausted" in error_text:
        if "requestsperday" in error_text or "daily" in error_text:
            # Daily quota exhausted — user cannot continue until tomorrow
            message = ("I apologize, but we've completely maxed out our daily quota. "
                       "I'm locked out for the rest of the day — I'll be fully refreshed "
                       "and ready to help you tomorrow morning. Signing off for now.")
        else:
            # Minute-based RPM or TPM limit — recoverable, but ending the session
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
        vaani_output(message, user_lang_code)
    except Exception as tts_err:
        # If TTS itself fails, just log — we're already exiting
        print(f"[speak_error] Could not speak error message: {tts_err}")

print("Vaani is ready. Start Speaking. To end conversation, say 'goodbye', 'bye', 'stop' or 'that's all for now'")

error_exit = False  # set to True when we exit due to an error rather than a user goodbye

while True:
    print("Listening....")
    audio = record_until_silence()
    print("Done recording. Sending to Sarvam STT...")

    # Save to temp WAV file
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sf.write(tmp.name, audio, SAMPLE_RATE)
    tmp.close()

    # Send to Sarvam
    with open(tmp.name, "rb") as f:
        user_query = sarvam.speech_to_text.transcribe(
            file=("audio.wav", f, "audio/wav"),
            model="saarika:v2.5",
            language_code="unknown"
        )

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
            speak_error(e, user_query.language_code)
            error_exit = True
            break
    else:
        gemini_input = user_query.transcript

    if any(phrase in gemini_input.lower() for phrase in EXIT_PHRASES):
        break
    else:
        print("Vaani is thinking.....")
        try:
            # Gemini call — most likely failure point (429, 503, network errors)
            llm_response = get_llm_response(chat_session, gemini_input)
        except Exception as e:
            speak_error(e, user_query.language_code)
            error_exit = True
            break

        try:
            # Speak Vaani's reply — can fail at outbound translation or TTS step
            vaani_output(llm_response, user_query.language_code)
        except Exception as e:
            speak_error(e, user_query.language_code)
            error_exit = True
            break

# Only play the normal goodbye if the user said bye — error exits already spoke their own ending
if not error_exit:
    exit_output = "Bye! I'm always here whenever you need me"
    try:
        vaani_output(exit_output, user_query.language_code)
    except Exception as e:
        speak_error(e, user_query.language_code)        