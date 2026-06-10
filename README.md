# Vaani

A voice assistant built on Sarvam AI's language stack (STT, translation, and TTS), with Google Gemini as the reasoning layer.

## Stack
- Speech-to-Text: Sarvam saarika:v2.5 (auto language detection: Hindi, Telugu, Kannada, and more)
- Translation: Sarvam speech_to_text.translate
- Reasoning: Google Gemini 2.5 Flash
- Text-to-Speech: Sarvam bulbul:v2
- Wake Word: OpenWakeWord (hey_jarvis)
- Audio I/O: sounddevice + soundfile

## Status
Work in progress. STT working and tested across Indian languages.

## Setup
1. Clone the repo
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with your keys:
    SARVAM_API_KEY=your_key_here
    GEMINI_API_KEY=your_key_here
4. Run: `python main.py`