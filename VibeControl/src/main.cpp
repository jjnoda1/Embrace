#include <Arduino.h>
#include <Wire.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <Sparkfun_DRV2605L.h>

#define SERVICE_UUID    "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
#define BASS_CHAR_UUID  "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

// create instance for driver
SFE_HMD_DRV2605L drv;

// holds most recent intensity
volatile uint8_t latestIntensity = 0;

// restart advertising on disconnect
class MyServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *pServer) override {
    Serial.println("BLE client connected.");
  }
  void onDisconnect(BLEServer *pServer) override {
    Serial.println("BLE client disconnected; restarting advertising.");
    // restart advertising for new connections
    BLEDevice::getAdvertising()->start();
  }
};

// update intensity when a new value is written.
class BassIntensityCallback : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *pCharacteristic) override {
    std::string value = pCharacteristic->getValue();
    if (!value.empty()) {
      latestIntensity = (uint8_t)value[0];
      Serial.print("Received intensity: ");
      Serial.println(latestIntensity);
    }
  }
};

BLECharacteristic *pBassCharacteristic;

void setup() {
  Serial.begin(115200);
  Wire.begin();
  
  // initialize driver
  if (!drv.begin()) {
    Serial.println("DRV2605L not found. Check wiring!");
    while(1);
  }
  drv.Library(1);  // library A
  drv.Mode(5);     // set to RTP

  // initialize BLE
  BLEDevice::init("ESP32_HapticReceiver");
  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());
  
  BLEService *pService = pServer->createService(SERVICE_UUID);
  pBassCharacteristic = pService->createCharacteristic(
      BASS_CHAR_UUID,
      BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR
  );
  pBassCharacteristic->setCallbacks(new BassIntensityCallback());
  pBassCharacteristic->addDescriptor(new BLE2902());
  
  pService->start();
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->start();
  
  Serial.println("BLE advertising started for haptic intensity streaming.");
}

void loop() {
  // update the register w/ latest intensity.
  drv.RTP(latestIntensity);
  delay(50); // update every 50 ms
}
