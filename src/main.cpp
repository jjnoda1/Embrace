#include <Arduino.h>

#define MINIMP3_IMPLEMENTATION
#include "minimp3.h"
#include "SPIFFS.h"
#include "driver/dac.h"  // or use dacWrite() if using Arduino functions


mp3dec_t mp3d;
mp3dec_frame_info_t info;

const int BUFFER_SIZE = 512;
uint8_t mp3Buffer[BUFFER_SIZE];
int16_t pcmBuffer[1152];  // Maximum samples per frame

File mp3File;

void setup() {
    Serial.begin(115200);
    Serial.println("Starting setup...");

    if (!SPIFFS.begin(true)) {
        Serial.println("SPIFFS Mount Failed");
        while (1);
    }
    Serial.println("SPIFFS Mounted");

    // Open MP3 file
    mp3File = SPIFFS.open("/Brightside.mp3", "r");
    if (!mp3File) {
        Serial.println("Failed to open MP3 file");
        while (1);
    }
    Serial.println("MP3 file opened");

    // Initialize the MP3 decoder
    mp3dec_init(&mp3d);
    Serial.println("MP3 decoder initialized");
}

void loop() {
    // Add a debug message for each loop iteration
    Serial.println("Loop iteration...");

    // Check if we have reached the end of the file
    if (!mp3File.available()) {
        Serial.println("End of file reached, looping...");
        mp3File.seek(0, SeekSet);
        mp3dec_init(&mp3d); // Reinitialize the decoder if needed
    }

    // Read a chunk of MP3 data from the file
    int bytesRead = mp3File.read(mp3Buffer, BUFFER_SIZE);
    Serial.print("Bytes read: ");
    Serial.println(bytesRead);
    if (bytesRead <= 0) {
        return; // Wait for next loop iteration
    }

    // Decode the MP3 frame; samplesDecoded is the number of PCM samples output
    int samplesDecoded = mp3dec_decode_frame(&mp3d, mp3Buffer, bytesRead, pcmBuffer, &info);
    Serial.print("Samples decoded: ");
    Serial.println(samplesDecoded);

    // If samples were decoded, output them to the DAC
    if (samplesDecoded > 0) {
        for (int i = 0; i < samplesDecoded; i++) {
            uint8_t dacValue = (uint8_t)((pcmBuffer[i] + 32768) >> 8);
            dacWrite(25, dacValue);
            delayMicroseconds(23);
        }
    }
}






