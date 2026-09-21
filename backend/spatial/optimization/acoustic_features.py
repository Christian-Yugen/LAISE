from __future__ import annotations
import math
import numpy as np

EPS = 1e-12

def rms(x):
    return float(np.sqrt(np.mean(np.square(x))))

def spectral_centroid(x, sr):
    mag = np.abs(np.fft.rfft(x))
    freqs = np.fft.rfftfreq(len(x), 1.0/sr)
    denom = float(np.sum(mag)) + EPS
    return float(np.sum(freqs * mag) / denom)

def high_frequency_ratio(x, sr, cutoff=4000.0):
    spec = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1.0/sr)
    total = float(np.sum(spec)) + EPS
    return float(np.sum(spec[freqs >= cutoff]) / total)

def estimate_itd_us(left, right, sr, max_ms=1.0):
    max_lag = int(sr * max_ms / 1000.0)
    # FFT-free bounded correlation is enough for the current 5 s test.
    best_lag, best = 0, -np.inf
    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            a, b = left[-lag:], right[:lag]
        elif lag > 0:
            a, b = left[:-lag], right[lag:]
        else:
            a, b = left, right
        v = float(np.dot(a, b))
        if v > best:
            best, best_lag = v, lag
    return float(best_lag * 1e6 / sr)

def extract_features(audio, sr):
    audio = np.asarray(audio, dtype=np.float32)
    left, right = audio[0], audio[1]
    lr, rr = rms(left), rms(right)
    mono = 0.5 * (left + right)
    side = 0.5 * (left - right)
    peak = float(np.max(np.abs(audio)))
    corr = float(np.corrcoef(left, right)[0, 1])
    ild = float(20.0 * math.log10((lr + EPS)/(rr + EPS)))
    return {
        "peak": peak,
        "rms": rms(audio),
        "left_rms": lr,
        "right_rms": rr,
        "ild_db": ild,
        "itd_us": estimate_itd_us(left, right, sr),
        "lr_correlation": corr,
        "mid_rms": rms(mono),
        "side_rms": rms(side),
        "side_mid_ratio": float(rms(side)/(rms(mono)+EPS)),
        "spectral_centroid_hz": spectral_centroid(mono, sr),
        "hf_ratio_above_4khz": high_frequency_ratio(mono, sr),
        "finite": bool(np.all(np.isfinite(audio))),
        "no_clipping": bool(peak < 1.0),
    }
