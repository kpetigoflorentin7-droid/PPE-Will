"""
Entraînement wakeword "Will" - Version corrigée
"""
import os
import glob
import numpy as np
import onnxruntime as ort
import wave
import pickle
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score

print("=" * 55)
print("  Entraînement wakeword 'Will' (version corrigée)")
print("=" * 55)

SAMPLES_DIR = "will_samples"
OUTPUT_DIR  = "will_model"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Trouve le modèle melspectrogram (meilleur pour l'audio) ──
import openwakeword
OWW_DIR = os.path.dirname(openwakeword.__file__)

# On utilise le modèle melspectrogram
MEL_MODEL = os.path.join(OWW_DIR, "resources", "models", "melspectrogram.onnx")

print(f"\n✅ Modèle : {MEL_MODEL}")

# ── Inspecte le modèle pour connaître la forme d'entrée ──────
sess        = ort.InferenceSession(MEL_MODEL)
input_info  = sess.get_inputs()[0]
output_info = sess.get_outputs()[0]
input_name  = input_info.name
output_name = output_info.name

print(f"   Input  : {input_name} → shape={input_info.shape}, type={input_info.type}")
print(f"   Output : {output_name} → shape={output_info.shape}")

# ── Lit un fichier WAV ────────────────────────────────────────
def read_wav(path, target_sr=16000):
    with wave.open(path, 'rb') as f:
        sr       = f.getframerate()
        n_frames = f.getnframes()
        raw      = f.readframes(n_frames)
        samples  = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if sr != target_sr:
        new_len = int(len(samples) * target_sr / sr)
        samples = np.interp(
            np.linspace(0, len(samples), new_len),
            np.arange(len(samples)), samples
        )
    return samples.astype(np.float32)

# ── Extrait les features via melspectrogram ───────────────────
def get_features(audio, target_len=16000):
    if len(audio) < target_len:
        audio = np.pad(audio, (0, target_len - len(audio)))
    else:
        audio = audio[:target_len]

    # Le modèle melspectrogram attend (batch, samples) = (1, 16000)
    audio_input = audio.reshape(1, -1).astype(np.float32)

    try:
        out = sess.run([output_name], {input_name: audio_input})[0]
        return out.flatten()
    except Exception as e:
        raise RuntimeError(f"Erreur ONNX : {e}\n  Input shape : {audio_input.shape}")

# ── Test sur un fichier pour valider la forme ─────────────────
print("\n⏳ Test de la forme d'entrée...")
test_files = glob.glob(os.path.join(SAMPLES_DIR, "*.wav"))
if test_files:
    test_audio = read_wav(test_files[0])
    test_feat  = get_features(test_audio)
    print(f"   ✅ Features shape : {test_feat.shape}")
else:
    print("❌ Aucun fichier WAV trouvé dans will_samples/")
    exit(1)

# ── Extraction des embeddings positifs ────────────────────────
print(f"\n⏳ Extraction des features ({len(test_files)} fichiers)...")
X_pos = []
for f in test_files:
    try:
        audio = read_wav(f)
        feat  = get_features(audio)
        X_pos.append(feat)
        print(f"   ✅ {os.path.basename(f)}")
    except Exception as e:
        print(f"   ⚠️ Erreur {os.path.basename(f)}: {e}")

print(f"\n✅ {len(X_pos)} embeddings positifs extraits")

if len(X_pos) == 0:
    print("❌ Impossible d'extraire les features. Arrêt.")
    exit(1)

# ── Génération des exemples négatifs ─────────────────────────
print(f"\n⏳ Génération des exemples négatifs...")
feat_size = len(X_pos[0])
np.random.seed(42)
X_neg = []

for i in range(len(X_pos) * 4):
    # Différents types de bruit
    if i % 3 == 0:
        noise = np.random.normal(0, 0.005, 16000).astype(np.float32)
    elif i % 3 == 1:
        noise = np.zeros(16000, dtype=np.float32)  # silence
    else:
        noise = np.random.uniform(-0.1, 0.1, 16000).astype(np.float32)
    try:
        feat = get_features(noise)
        X_neg.append(feat)
    except Exception:
        pass

print(f"✅ {len(X_neg)} exemples négatifs générés")

# ── Entraînement ──────────────────────────────────────────────
X = np.array(X_pos + X_neg)
y = np.array([1] * len(X_pos) + [0] * len(X_neg))

print(f"\n⏳ Entraînement... ({len(X_pos)} positifs + {len(X_neg)} négatifs)")

scaler   = StandardScaler()
X_scaled = scaler.fit_transform(X)

clf = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
clf.fit(X_scaled, y)

if len(np.unique(y)) > 1:
    scores = cross_val_score(clf, X_scaled, y, cv=min(3, len(X_pos)), scoring='accuracy')
    print(f"✅ Précision : {scores.mean():.1%}")

# ── Sauvegarde ────────────────────────────────────────────────
with open(os.path.join(OUTPUT_DIR, "will_classifier.pkl"), 'wb') as f:
    pickle.dump(clf, f)
with open(os.path.join(OUTPUT_DIR, "will_scaler.pkl"), 'wb') as f:
    pickle.dump(scaler, f)

# Sauvegarde aussi les infos du modèle
config = {
    "mel_model_path": MEL_MODEL,
    "input_name":     input_name,
    "output_name":    output_name,
    "target_sr":      16000,
    "target_len":     16000,
    "feat_size":      feat_size,
}
with open(os.path.join(OUTPUT_DIR, "config.pkl"), 'wb') as f:
    pickle.dump(config, f)

print(f"\n" + "=" * 55)
print(f"✅ Modèle sauvegardé dans '{OUTPUT_DIR}/'")
print(f"   will_classifier.pkl")
print(f"   will_scaler.pkl")
print(f"   config.pkl")
print(f"\nLance maintenant : python test_will.py")
print("=" * 55)