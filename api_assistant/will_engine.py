"""
Endpoint Django pour la détection du wakeword Will
et le traitement des commandes vocales
"""
import numpy as np
import pickle
import onnxruntime as ort
import os
import base64
import struct
import wave
import io
from mistralai import Mistral

# ── Chemin vers le modèle Will ────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR     = os.path.join(BASE_DIR, "will_model")
CONFIG_PATH   = os.path.join(MODEL_DIR, "config.pkl")
CLF_PATH      = os.path.join(MODEL_DIR, "will_classifier.pkl")
SCALER_PATH   = os.path.join(MODEL_DIR, "will_scaler.pkl")

# ── Charge le modèle Will au démarrage ───────────────────────
_will_loaded = False
_clf = _scaler = _sess = _input_name = _output_name = None

def _load_will_model():
    global _will_loaded, _clf, _scaler, _sess, _input_name, _output_name
    if _will_loaded:
        return True
    try:
        with open(CLF_PATH,    'rb') as f: _clf    = pickle.load(f)
        with open(SCALER_PATH, 'rb') as f: _scaler = pickle.load(f)
        with open(CONFIG_PATH, 'rb') as f: config  = pickle.load(f)

        _sess        = ort.InferenceSession(config["mel_model_path"])
        _input_name  = config["input_name"]
        _output_name = config["output_name"]
        _will_loaded = True
        print("✅ Modèle Will chargé avec succès")
        return True
    except Exception as e:
        print(f"❌ Erreur chargement modèle Will : {e}")
        return False

# ── Décode l'audio base64 → numpy ────────────────────────────
def decode_audio(audio_b64: str, target_sr=16000) -> np.ndarray:
    raw = base64.b64decode(audio_b64)
    with wave.open(io.BytesIO(raw), 'rb') as f:
        sr       = f.getframerate()
        n_frames = f.getnframes()
        data     = f.readframes(n_frames)
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
    if sr != target_sr:
        new_len = int(len(samples) * target_sr / sr)
        samples = np.interp(
            np.linspace(0, len(samples), new_len),
            np.arange(len(samples)), samples
        )
    return samples.astype(np.float32)

# ── Extrait les features ──────────────────────────────────────
def get_features(audio: np.ndarray, target_len=16000) -> np.ndarray:
    if len(audio) < target_len:
        audio = np.pad(audio, (0, target_len - len(audio)))
    else:
        audio = audio[:target_len]
    audio_input = audio.reshape(1, -1).astype(np.float32)
    out = _sess.run([_output_name], {_input_name: audio_input})[0]
    return out.flatten()

# ── Détecte si "Will" est dans l'audio ───────────────────────
def detect_will(audio: np.ndarray, threshold=0.92) -> tuple:
    feat    = get_features(audio)
    feat_sc = _scaler.transform([feat])
    proba   = _clf.predict_proba(feat_sc)[0][1]
    return proba >= threshold, float(proba)