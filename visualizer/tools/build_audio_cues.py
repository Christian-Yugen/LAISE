"""Generate visual attack cues from the actual T007 spatial stems, without editing audio.

Run from the repository root: python visualizer/tools/build_audio_cues.py
Requires NumPy and the project's installed FFmpeg. No browser-side stem playback.
"""
from pathlib import Path
import hashlib
import json
import math
import subprocess
import numpy as np

RATE = 16000
WINDOW = 512
HOP = 128
VISUALIZER = Path(__file__).resolve().parents[1]
PROJECT = VISUALIZER.parent / 'projects/tukana_02_a_mata_se_move'


def detect_attacks(audio, rate=RATE, percussive=True):
    """Return (seconds, absolute stereo RMS) for independent, unquantized attacks."""
    if audio.ndim == 1:
        audio = audio[:, None]
    padded = np.pad(audio, ((WINDOW // 2, WINDOW // 2), (0, 0)))
    frames = np.lib.stride_tricks.sliding_window_view(padded, WINDOW, axis=0)[::HOP]
    frames = frames.swapaxes(1, 2)
    flux = np.empty((len(frames), 4), dtype=np.float32)
    rms = np.empty(len(frames), dtype=np.float32)
    frequencies = np.fft.rfftfreq(WINDOW, 1 / rate)
    masks = [(frequencies >= low) & (frequencies < high)
             for low, high in [(30, 180), (180, 700), (700, 2600), (2600, 7900)]]
    previous = np.zeros(WINDOW // 2 + 1)
    window = np.hanning(WINDOW).astype(np.float32)
    for start in range(0, len(frames), 1024):
        chunk = frames[start:start + 1024]
        rms[start:start + len(chunk)] = np.sqrt(np.mean(chunk ** 2, axis=(1, 2)))
        spectrum = np.fft.rfft(chunk * window[None, :, None], axis=1)
        magnitude = np.sqrt(np.mean(np.abs(spectrum) ** 2, axis=2)) / WINDOW
        compressed = np.log1p(magnitude * 100)
        differences = np.maximum(0, np.diff(compressed, axis=0, prepend=previous[None, :]))
        previous = compressed[-1]
        for band, mask in enumerate(masks):
            flux[start:start + len(chunk), band] = np.mean(differences[:, mask], axis=1)
    candidates = []
    amplitude_floor = max(float(np.percentile(rms, 95)) * 0.02, 1e-7)
    for band in range(4):
        novelty = flux[:, band]
        neighborhood = np.lib.stride_tricks.sliding_window_view(np.pad(novelty, (31, 31)), 63)
        median = np.median(neighborhood, axis=1)
        deviation = np.median(np.abs(neighborhood - median[:, None]), axis=1)
        threshold = median + 1.5 * deviation + max(float(np.percentile(novelty, 95)) * 0.12, 1e-7)
        maxima = np.max(np.lib.stride_tricks.sliding_window_view(np.pad(novelty, (2, 2)), 5), axis=1)
        for index in np.flatnonzero((novelty >= maxima) & (novelty > threshold)):
            amplitude = float(np.max(rms[index:min(len(rms), index + 7)]))
            before = float(np.mean(rms[max(0, index - 6):max(1, index - 1)]))
            # Reject vibrato/spectral fluctuations without a new amplitude attack.
            rise_ratio = 1.10 if percussive else 1.22
            if amplitude > amplitude_floor and amplitude > before * rise_ratio:
                candidates.append((int(index), float(novelty[index] / (threshold[index] + 1e-9)), amplitude))
    # Merge frequency-band detections of the SAME stem attack, not different stems.
    # 64 ms separation retains rapid repeated hits that the old 220 ms gate lost.
    selected = []
    occupied = np.zeros(len(frames), dtype=bool)
    separation = max(1, round((0.064 if percussive else 0.12) * rate / HOP))
    for index, confidence, amplitude in sorted(candidates, key=lambda p: p[1], reverse=True):
        if not occupied[index]:
            selected.append((index * HOP / rate, amplitude))
            occupied[max(0, index - separation + 1):index + separation] = True
    return sorted(selected)


def interpolate(keyframes, time, name):
    # Last keyframe wins at section boundaries, matching the ordered automation.
    values = {}
    for key in keyframes:
        values[float(key['time_seconds'])] = float(key[name])
    times = sorted(values)
    return float(np.interp(time, times, [values[t] for t in times]))


def floor_position(role, time):
    azimuth = interpolate(role['keyframes'], time, 'azimuth_deg_unwrapped')
    elevation = interpolate(role['keyframes'], time, 'elevation_deg')
    distance = interpolate(role['distance_keyframes'], time, 'distance_m')
    az, el = math.radians(azimuth), math.radians(elevation)
    radius = 0.80 * distance / (distance + 0.7)
    # Top-down projection: normalized local X/Z; front is negative Z.
    return (radius * math.sin(az) * math.cos(el),
            -radius * math.cos(az) * math.cos(el), azimuth, elevation, distance)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    source = PROJECT / 'experiments/TUK2_T007'
    manifest_path = source / 'spatial_scenes/TUK2_T007_automation_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    delivery = json.loads((PROJECT / 'experiments/TUK2_T009/reports/TUK2_T009_delivery_validation.json').read_text(encoding='utf-8'))
    master = VISUALIZER / 'public/audio/TUKANA02_FINAL_MASTER_PCM24_48k.wav'
    master_hash = sha256(master)
    assert master_hash == delivery['artifacts']['wav_pcm24_48k']['sha256'], 'Master mismatch'
    duration = manifest['frames'] / manifest['rate']
    events, stems = [], []
    for role in manifest['roles']:
        name = role['source_id']
        path = source / f'spatial_stems/{name}_spatial_PCM24_48k.wav'
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-ar', str(RATE),
            '-ac', '2', '-f', 'f32le', '-'], check=True, capture_output=True).stdout
        samples = np.frombuffer(raw, dtype='<f4').reshape(-1, 2)
        assert abs(len(samples) / RATE - duration) <= 1 / RATE, name
        attacks = detect_attacks(samples, percussive=name in ['drums', 'bass', 'percussion'])
        for time, amplitude in attacks:
            if time >= duration:
                continue
            x, z, az, el, distance = floor_position(role, time)
            events.append({'time':round(time, 4), 'source':name, 'amplitude':amplitude,
                'x':round(x, 5), 'z':round(z, 5), 'azimuth':round(az, 3),
                'elevation':round(el, 3), 'distance':round(distance, 4),
                'width':0.64 if name in ['drums', 'bass', 'percussion'] else 0.80})
        stems.append({'id':name, 'sha256':sha256(path), 'attacks':len(attacks),
            'file':str(path.relative_to(VISUALIZER.parent)).replace('\\', '/')})
        print(f'{name}: {len(attacks)} attacks', flush=True)
        del samples, raw
    # One common reference preserves strength differences BETWEEN instruments.
    reference = float(np.percentile([e['amplitude'] for e in events], 99.5))
    events = [e for e in events if e['amplitude'] >= reference * 0.015]
    for event in events:
        event['strength'] = round(min(1.0, (event['amplitude'] / reference) ** 0.85), 5)
        event['amplitude'] = round(event['amplitude'], 8)
    events.sort(key=lambda e: (e['time'], e['source']))
    result = {'schema':'laise-stem-cues-v1', 'duration':duration,
        'master':{'url':'/audio/TUKANA02_FINAL_MASTER_PCM24_48k.wav', 'sha256':master_hash},
        'analysis':{'sampleRate':RATE, 'hopSamples':HOP, 'resolutionMs':HOP / RATE * 1000,
            'minimumSeparationMs':{'percussive':64,'harmonic':120}, 'amplitudeReferenceRms':reference,
            'method':'Per-stem multiband positive spectral flux, adaptive median/MAD threshold; absolute stereo RMS strength.',
            'spatialMethod':'Top-down projection of interpolated T007 azimuth/elevation/distance at attack time; not reconstruction from stereo.',
            'timing':'Aligned T007 spatial stems; compensated plugin latency, no additional pre-roll offset.',
            'manifestSha256':sha256(manifest_path)}, 'stems':stems, 'events':events}
    output = VISUALIZER / 'public/audio/tukana-stem-cues.json'
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'{len(events)} events -> {output} ({output.stat().st_size} bytes)', flush=True)


if __name__ == '__main__':
    main()
