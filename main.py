import os
import tempfile
import numpy as np
import sounddevice as sd
import soundfile as sf
from sarvamai import SarvamAI
from dotenv import load_dotenv

load_dotenv()

SAMPLE_RATE = 16000
DURATION = 5

sarvam = SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))

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
    response = sarvam.speech_to_text.transcribe(
        file=("audio.wav", f, "audio/wav"),
        model="saarika:v2.5",
        language_code="unknown",
    )

os.unlink(tmp.name)

#print("Transcript:", response.transcript)
#print("Transcript:", response)
print("Transcript:", response.transcript)
print("Transcript language is:", response.language_code)