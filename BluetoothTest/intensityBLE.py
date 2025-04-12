import asyncio
import subprocess
import time
import wave
import numpy as np
from scipy.signal import butter, lfilter
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
BASS_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

def butter_bandpass(lowcut, highcut, fs, order=2):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def bandpass_filter(data, lowcut, highcut, fs, order=2):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    return lfilter(b, a, data)

def extract_peak_envelope(audio, sample_rate, window_ms=50):
    window_size = int(sample_rate * window_ms / 1000)
    n_windows = len(audio) // window_size 
    peaks = []
    for i in range(n_windows):
        start = i * window_size
        window = audio[start : start + window_size]
        peak = np.max(np.abs(window))
        peaks.append(peak)
    return np.array(peaks)

async def stream_bass_envelope(wav_file):
    print("Processing WAV file to extract envelope values...")
    wf = wave.open(wav_file, "rb")
    fs = wf.getframerate()
    sampwidth = wf.getsampwidth()
    num_frames = wf.getnframes()
    raw_data = wf.readframes(num_frames)
    wf.close()
    
    #This is GPT code lol
    # Convert raw audio data to float and normalize based on sample width.
    if sampwidth == 1:
        # 8-bit PCM: unsigned [0,255] -> convert to [-1,1]
        audio = np.frombuffer(raw_data, dtype=np.uint8).astype(np.float32)
        audio = (audio - 128.0) / 127.0
    elif sampwidth == 2:
        # 16-bit PCM: signed [-32768,32767] -> normalize to [-1,1]
        audio = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
        audio = audio / 32768.0
    else:
        print("Unsupported sample width:", sampwidth)
        return []
    
    print("Audio min, max:", audio.min(), audio.max())
    
    # isolate bass by bandpass filters
    bass_audio = bandpass_filter(audio, lowcut=20, highcut=200, fs=fs, order=2)
    bass_audio = np.nan_to_num(bass_audio)
    print("Bass audio min, max:", bass_audio.min(), bass_audio.max())
    
    # extract peak in 50ms windows
    envelope = extract_peak_envelope(bass_audio, fs, window_ms=50)
    print("Raw envelope values:", envelope)
    
    # apply gain
    gain = 100.0
    envelope = envelope * gain
    
    # use square-root scaling to enhance difference
    envelope_sqrt = np.sqrt(np.abs(envelope))
    
    # normalize square-root values to range (0-255)
    # need to refine for better playback
    min_val = envelope_sqrt.min()
    max_val = envelope_sqrt.max()
    if max_val - min_val > 0:
        envelope_norm = np.clip((envelope_sqrt - min_val) / (max_val - min_val) * 255, 0, 255).astype(np.uint8)
    else:
        envelope_norm = np.zeros_like(envelope_sqrt, dtype=np.uint8)
    
    print("Normalized envelope values:", envelope_norm)
    return envelope_norm

async def send_envelope_values(envelope_values, playback_event):
    print("Scanning for ESP32...")
    devices = await BleakScanner.discover()
    target = None
    for d in devices:
        if d.name and "ESP32" in d.name:
            target = d
            break
    if not target:
        print("ESP32 device not found!")
        return

    async with BleakClient(target.address) as client:
        print(f"Connected to {target.name}")
        # signal that BLE connected and ready
        playback_event.set()
        interval = 0.05  # 50 ms per envelope value
        start_time = asyncio.get_event_loop().time()
        for i, intensity in enumerate(envelope_values):
            scheduled_time = start_time + i * interval
            now = asyncio.get_event_loop().time()
            sleep_time = scheduled_time - now
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            print("Sending intensity:", intensity)
            # write (don't wait for response to keep timing right)
            await client.write_gatt_char(BASS_CHAR_UUID, bytes([intensity]), response=False)
        # wait for end
        total_duration = len(envelope_values) * interval
        final_time = start_time + total_duration
        now = asyncio.get_event_loop().time()
        if final_time - now > 0:
            await asyncio.sleep(final_time - now)
        # send 0 to stop motor
        print("Finished envelope; sending final stop command.")
        await client.write_gatt_char(BASS_CHAR_UUID, bytes([0]), response=False)
        print("Audio streaming complete.")

async def play_audio_file(wav_file, playback_event):
    # wait for BLE connection
    await playback_event.wait()
    # play on speakers when starting
    print("Starting local audio playback...")
    subprocess.Popen(["afplay", wav_file])

async def main():
    playback_event = asyncio.Event()
    wav_file = "Brightside.wav"
    envelope_values = await stream_bass_envelope(wav_file)
    if len(envelope_values) > 0:
        await asyncio.gather(
            send_envelope_values(envelope_values, playback_event),
            play_audio_file(wav_file, playback_event)
        )
    print("Done sending envelope values.")


asyncio.run(main())
