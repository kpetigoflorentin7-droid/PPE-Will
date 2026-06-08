import pyaudio
import wave
import os

# ── Config ──────────────────────────────────────
OUTPUT_DIR  = "will_samples"
SAMPLE_RATE = 16000
CHANNELS    = 1
CHUNK       = 1024
DURATION    = 1.5   
FORMAT      = pyaudio.paInt16
TOTAL       = 50    

os.makedirs(OUTPUT_DIR, exist_ok=True)
p = pyaudio.PyAudio()

# ✅ CORRECTION 1 : On ouvre le flux UNE SEULE FOIS ici (Micro toujours prêt)
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=SAMPLE_RATE,
    input=True,
    frames_per_buffer=CHUNK,
)

print("=" * 50)
print("  Enregistrement SILENCIEUX des échantillons 'Will'")
print("=" * 50)

try:
    for i in range(1, TOTAL + 1):
        input(f"[{i}/{TOTAL}] Prépare-toi... Appuie sur ENTRÉE et dis 'Will' immédiatement")

        frames = []
        # ✅ CORRECTION 2 : On vide le buffer avant de commencer pour éviter les vieux sons
        stream.read(stream.get_read_available(), exception_on_overflow=False)

        print("  🎙️  Écoute en cours...")
        for _ in range(int(SAMPLE_RATE / CHUNK * DURATION)):
            data = stream.read(CHUNK)
            frames.append(data)

        filename = os.path.join(OUTPUT_DIR, f"will_{i:03d}.wav")
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(frames))

        print(f"  ✅ Enregistré proprement : {filename}\n")

finally:
    # On ferme proprement à la toute fin
    stream.stop_stream()
    stream.close()
    p.terminate()

print("=" * 50)
print("Terminé ! Tes échantillons sont propres et sans bruits d'initialisation.")