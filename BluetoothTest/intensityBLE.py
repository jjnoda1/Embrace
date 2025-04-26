import asyncio
import subprocess
import time
import wave
import numpy as np
from scipy.signal import butter, lfilter, savgol_filter
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
BASS_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

def butter_bandpass(lowcut, highcut, fs, order=2):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    return butter(order, [low, high], btype='band')

def bandpass_filter(data, lowcut, highcut, fs, order=2):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    return lfilter(b, a, data)

def extract_rms_envelope(audio, sample_rate, window_ms=250):
    window_size = int(sample_rate * window_ms / 1000)
    n_windows = len(audio) // window_size
    rms_vals = []
    for i in range(n_windows):
        start = i * window_size
        w = audio[start:start+window_size]
        rms_vals.append(np.sqrt(np.mean(w**2)))
    return np.array(rms_vals)

async def stream_bass_envelope(wav_file):
    print("Processing WAV file…")
    wf = wave.open(wav_file, "rb")
    fs = wf.getframerate()
    nch = wf.getnchannels()
    sampw = wf.getsampwidth()
    n_frames = wf.getnframes()
    data = wf.readframes(n_frames)
    wf.close()

    if sampw == 1:
        audio = np.frombuffer(data, dtype=np.uint8).astype(np.float32)
        audio = (audio - 128.0) / 127.0
    elif sampw == 2:
        audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        print("Unsupported sample width:", sampw)
        return np.array([])

    if nch > 1:
        audio = audio.reshape(-1, nch).mean(axis=1)

    print(f"Rate: {fs}Hz, Channels: {nch}, Samples: {len(audio)}")

    bass = bandpass_filter(audio, 20, 200, fs, order=2)
    bass = np.nan_to_num(bass)

    env = extract_rms_envelope(bass, fs, window_ms=250)
    print("Raw RMS envelope:", env)

    gain = 10.0
    env_s = np.sqrt(env * gain)
    mn, mx = env_s.min(), env_s.max()
    if mx > mn:
        norm = ((env_s - mn) / (mx - mn) * 255).clip(0,255).astype(np.uint8)
    else:
        norm = np.zeros_like(env_s, dtype=np.uint8)

    if len(norm) >= 7:
        smooth1 = savgol_filter(norm, 7, 2).astype(np.uint8)
    else:
        smooth1 = norm

    alpha = 0.2
    smooth2 = np.zeros_like(smooth1, dtype=np.float32)
    smooth2[0] = smooth1[0]
    for i in range(1, len(smooth1)):
        smooth2[i] = alpha * smooth1[i] + (1-alpha) * smooth2[i-1]

    final_env = smooth2.clip(0,255).astype(np.uint8)

    final_env -= 50
    print("Final smoothed envelope:", final_env)
    return final_env

async def send_envelope_values(env_vals, playback_event):
    print("Scanning for ESP32…")
    devices = await BleakScanner.discover()
    target  = next((d for d in devices if d.name and "ESP32" in d.name), None)
    if not target:
        print("ESP32 not found")
        return

    async with BleakClient(target.address) as client:
        print("Connected to", target.name)
        playback_event.set()
        interval = 0.25
        start = asyncio.get_event_loop().time()

        for i, val in enumerate(env_vals):
            sched = start + i*interval
            now = asyncio.get_event_loop().time()
            if sched > now:
                await asyncio.sleep(sched - now)
            print("Send:", val)
            await client.write_gatt_char(BASS_CHAR_UUID, bytes([val]), response=False)

        # ensure we waited
        total = len(env_vals) * interval
        endt = start + total
        now = asyncio.get_event_loop().time()
        if endt > now:
            await asyncio.sleep(endt - now)

        # final stop command
        print("Stopping motor")
        # send the zero twice with a small pause to ensure delivery
        await client.write_gatt_char(BASS_CHAR_UUID, bytes([0]), response=False)
        await asyncio.sleep(0.1)
        await client.write_gatt_char(BASS_CHAR_UUID, bytes([0]), response=False)
        print("Done streaming")

async def play_audio_file(wav_file, playback_event):
    await playback_event.wait()
    print("Playing audio…")
    subprocess.Popen(["afplay", wav_file])

async def main():
    playback_event = asyncio.Event()
    wav_file = "waves.wav"

    env_vals = await stream_bass_envelope(wav_file)
    if env_vals.size == 0:
        return

    t0 = time.monotonic()
    await asyncio.gather(
        send_envelope_values(env_vals, playback_event),
        play_audio_file(wav_file, playback_event)
    )
    t1 = time.monotonic()
    print(f"Session time: {t1-t0:.3f}s")

asyncio.run(main())

