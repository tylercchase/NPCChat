import whisper
# from pydub import AudioSegment

# test_speech = AudioSegment.from_ogg("test.ogg")


# test_speech.export("test_export.mp3", format="mp3")
model = whisper.load_model("base")
result = model.transcribe("test.ogg")
print(result["text"])