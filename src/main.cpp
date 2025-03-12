#include <Arduino.h>

// #define MINIMP3_IMPLEMENTATION
// #include "minimp3.h"
#include "SPIFFS.h"
// #include "driver/dac.h"  // or use dacWrite() if using Arduino functions


// mp3dec_t mp3d;
// mp3dec_frame_info_t info;

// const int BUFFER_SIZE = 512;
// uint8_t mp3Buffer[BUFFER_SIZE];
// int16_t pcmBuffer[1152];  // Maximum samples per frame

// File mp3File;


void listSPIFFSFiles() {
    File root = SPIFFS.open("/");
    File file = root.openNextFile();
    
    Serial.println("SPIFFS Files:");
    while (file) {
        Serial.printf("  File: %s, Size: %d bytes\n", file.name(), file.size());
        file = root.openNextFile();
    }
}

void setup() {
    Serial.begin(115200);
    if (!SPIFFS.begin(true)) {
        Serial.println("SPIFFS Mount Failed!");
        return;
    }

    Serial.println("SPIFFS Mounted Successfully!");
    listSPIFFSFiles();  // List the files on SPIFFS
}


void loop() {

}






