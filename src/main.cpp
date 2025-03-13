#include "SPIFFS.h"

#define DAC_PIN 25  // Use GPIO25 (DAC1) or GPIO26 (DAC2)
#define WAV_HEADER_SIZE 44  // Standard WAV header size
#define AUDIO_BUFFER_SIZE 512  // Buffer size for reading file
#define SAMPLE_RATE 44100  
#define SAMPLE_DELAY_US (1000000 / SAMPLE_RATE)

File audioFile;
bool isPlaying = false;

void startPlayback(const char* filename) {
    if (audioFile) audioFile.close();  // Close previous file if open

    audioFile = SPIFFS.open(filename, "r");
    if (!audioFile) {
        Serial.println("Failed to open file!");
        return;
    }

    uint8_t header[WAV_HEADER_SIZE];
    audioFile.read(header, WAV_HEADER_SIZE);
    for (int i = 0; i < WAV_HEADER_SIZE; i++) {
        Serial.printf("%02X ", header[i]);
        if ((i + 1) % 16 == 0) Serial.println();
    }
    Serial.println();

    uint16_t audioFormat = header[20] | (header[21] << 8);
    Serial.printf("Audio Format: %04X\n", audioFormat);

    audioFile.seek(WAV_HEADER_SIZE);  // Skip WAV header
    isPlaying = true;
    Serial.println("Playback started!");
}

void playAudio() {

    static unsigned long lastSampleTime = 0;

    if (!isPlaying || !audioFile.available()) {
        isPlaying = false;
        Serial.println("Playback finished!");
        return;
    }

    uint8_t buffer[AUDIO_BUFFER_SIZE];
    int bytesRead = audioFile.read(buffer, AUDIO_BUFFER_SIZE);

    for (int i = 0; i < bytesRead; i++) {
        while (micros() - lastSampleTime < 23);
        lastSampleTime = micros();
        dacWrite(DAC_PIN, buffer[i]);  // Send PCM data to DAC
        // delayMicroseconds(SAMPLE_DELAY_US);  // Adjust based on sample rate (8kHz = 125µs per sample)
    }
}

void setup() {
    Serial.begin(115200);

    if (!SPIFFS.begin(true)) {
        Serial.println("SPIFFS Mount Failed!");
        return;
    }

    Serial.println("SPIFFS Mounted Successfully!");

    File root = SPIFFS.open("/");
    File file = root.openNextFile();
    while (file) {
        Serial.printf("File: %s, Size: %d\n", file.name(), file.size());
        file = root.openNextFile();
    }

    // Start playing the WAV file
    startPlayback("/Brightside.wav");
}

void loop() {
    playAudio();  // Continuously play audioa
}







