import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.1
TOTAL_DURATION = 10  # seconds, then auto-stops

num_chunks = int(TOTAL_DURATION / CHUNK_DURATION)

print(f"Recording for {TOTAL_DURATION} seconds. Talk, then go silent.\n")

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32') as stream:
    for _ in range(num_chunks):
        chunk, _ = stream.read(int(CHUNK_DURATION * SAMPLE_RATE))
        volume = np.abs(chunk).mean()
        bar = "#" * int(volume * 1000)
        print(f"{volume:.5f} {bar}")

print("\nDone.")