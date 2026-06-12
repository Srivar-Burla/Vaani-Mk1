import os
import tempfile
import numpy as np
import sounddevice as sd
import soundfile as sf
from sarvamai import SarvamAI
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

SAMPLE_RATE = 16000
DURATION = 5


SYSTEM_PROMPT = """You are Vaani, a voice assistant. You are talking to your user through earphones. They are often walking, commuting, or doing something with their hands while talking to you.
Your personality: you are a capable personal assistant. Warm, direct, and honest. If you disagree with the user or think they are wrong about something, say so politely. Never just tell the user what they want to hear.
Everything you say will be spoken aloud by a text to speech system. Follow these rules strictly:
Keep responses short. Two to four sentences for most answers. This is a voice conversation, not an essay.
Never use bullet points, numbered lists, headings, or any markdown formatting. Use connective language instead, like first, then, finally.
For longer explanations, structure your response sequentially and break it at natural boundaries, like after completing one concept and before starting the next. At these points, check in with the user before continuing. Vary how you ask: "should I go on?", "are you following me so far?", "any questions before I continue?". Never break midway through a single idea or thought, as this disrupts the user's understanding.
Avoid abbreviations and acronyms that sound wrong when spoken. Say "as soon as possible" not ASAP. If an acronym is widely spoken aloud, like API or UPI, it is fine to use.
Be decisive. Give a clear answer first, then offer to elaborate. Do not front-load your uncertainty with hedges.
If you do not know something or are not confident, say "I don't know" plainly. Do not guess or make things up. You do not have access to live information from the internet, so for questions about current events, prices, or anything recent, say you don't have live information on that.
Numbers, dates, and currency should be spoken naturally. Say "three thirty in the afternoon" not "15:30". Say "twenty five thousand rupees" not "Rs. 25,000"."""


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

print("Recording for 5 seconds... speak a sentence!")
audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype='float32'
)
sd.wait()
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
        language_code="unknown",
    )

os.unlink(tmp.name)

llm_response = get_llm_response(chat_session, user_query.transcript)

#print("Transcript:", response.transcript)
#print("Transcript:", response)
print("User:", user_query.transcript)
print("User spoke in:", user_query.language_code)
print("Vaani: ", llm_response)