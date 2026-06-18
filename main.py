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

If you do not know something or are not confident, say "I don't know" plainly. Do not guess or make things up. You do not have access to live information from the internet, so for questions about current events, prices, or anything recent, say you don't have live information on that.

Numbers, dates, and currency should be spoken naturally. Say "three thirty in the afternoon" not "15:30". Say "twenty five thousand rupees" not "Rs. 25,000". """


sarvam = SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))

# llm_client: currently Gemini. Kept generic so swapping providers later
# (Claude, open source models) doesn't require renaming this throughout the file.
llm_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
chat_session = llm_client.chats.create(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(system_instruction = SYSTEM_PROMPT)
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
            target_language_code=user_query.language_code
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
        
print("Vaani is ready. Start Speaking. To end conversation, say 'goodbye', 'bye', 'stop' or 'that's all for now'")

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
        translation = sarvam.text.translate(
            input=user_query.transcript,
            source_language_code=user_query.language_code,
            target_language_code="en-IN"
        )
        gemini_input = translation.translated_text
        print("User (in English): ", gemini_input)
    else:
        gemini_input = user_query.transcript

    if any(phrase in gemini_input.lower() for phrase in EXIT_PHRASES):
        break
    else:
        print("Vaani is thinking.....")
        llm_response = get_llm_response(chat_session, gemini_input)

        vaani_output(llm_response, user_query.language_code)

exit_output = "Bye! I'm always here whenever you need me" 
vaani_output(exit_output, user_query.language_code)        