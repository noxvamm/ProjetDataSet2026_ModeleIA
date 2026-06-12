#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s.h>
#include <BLEDevice.h>
#include <vector>

// CONFIG
#define I2S_SD   32
#define I2S_WS   25
#define I2S_SCK  14
#define SAMPLE_RATE 44000
#define BUFFER_LEN 128

const char* ssid = "lewifiduciel";
const char* password = "cielmonwifi";

// Deux destinataires UDP : Noa + Ege
const char* udpAddress1 = "172.21.1.69";   // Noa
const char* udpAddress2 = "172.21.1.87";   // Ege
const int   udpPort     = 9091;

WiFiUDP udp;
// Elles sont controlées par les commandes udp start et stop de l'application Dataset
bool microActive = false;// active ou coupe l’acquisition du micro I2S
bool vibActive   = false;// active ou coupe l'acquisition des vibrations BLE

// BLE
String targetName = "WTVB01-BT50";
BLEUUID serviceUUID("0000ffe5-0000-1000-8000-00805f9a34fb");// ouvre l service du capteur 
BLEUUID dataUUID   ("0000ffe4-0000-1000-8000-00805f9a34fb");// carac qui envoie les vibrations
BLEUUID cmdUUID    ("0000ffe9-0000-1000-8000-00805f9a34fb");// carac qui envoie les commandes

BLERemoteCharacteristic* cmdChar;// cette ligne démmarre l'envoie des vibrations ( pointeur pour stocker la caractéristique)

std::vector<uint8_t> vibFrame;// le capteur n'envoie pas tout d'un coup ( fragment BLE)

uint16_t read16(const std::vector<uint8_t>& b, int i) {// combine deux octet pour obtenir un valeur 16bits
  return b[i] | (b[i+1] << 8);
}

// BLE CALLBACK
void notifyCB(BLERemoteCharacteristic*, uint8_t* data, size_t len, bool) {
  if (!vibActive) return;

  if (len >= 2 && data[0] == 0x55 && data[1] == 0x61)
      vibFrame.clear();

  vibFrame.insert(vibFrame.end(), data, data + len);

  if (vibFrame.size() >= 28 && vibFrame[0] == 0x55 && vibFrame[1] == 0x61) {// condition si la trame fait 28 octet et la trame commence 0x55 et 0x61 on peut décoder

    uint16_t VX  = read16(vibFrame, 2);
    uint16_t VY  = read16(vibFrame, 4);
    uint16_t VZ  = read16(vibFrame, 6);
    uint16_t ADX = read16(vibFrame, 8);
    uint16_t ADY = read16(vibFrame,10);
    uint16_t ADZ = read16(vibFrame,12);
    float TEMP   = read16(vibFrame,14) / 100.0f;
    uint16_t DX  = read16(vibFrame,16);
    uint16_t DY  = read16(vibFrame,18);
    uint16_t DZ  = read16(vibFrame,20);
    uint16_t HZX = read16(vibFrame,22);
    uint16_t HZY = read16(vibFrame,24);
    uint16_t HZZ = read16(vibFrame,26);

    char msg[256];
    snprintf(msg, sizeof(msg),
      "VIB,%lu,%u,%u,%u,%u,%u,%u,%.2f,%u,%u,%u,%u,%u,%u",
      millis(),
      VX, VY, VZ, ADX, ADY, ADZ, TEMP,
      DX, DY, DZ, HZX, HZY, HZZ
    );
    // Envoi Noa
    udp.beginPacket(udpAddress1, udpPort);
    udp.print(msg);
    udp.endPacket();

    // Envoi Ege
    udp.beginPacket(udpAddress2, udpPort);
    udp.print(msg);
    udp.endPacket();

    Serial.println(msg);
    Serial.println();
    vibFrame.clear();
  }
}

// I2S
void setupI2S() {
  i2s_config_t config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S,
    .dma_buf_count = 4,
    .dma_buf_len = BUFFER_LEN
  };

  i2s_pin_config_t pins = {
    .bck_io_num = I2S_SCK,
    .ws_io_num  = I2S_WS,
    .data_out_num = -1,
    .data_in_num  = I2S_SD
  };

  i2s_driver_install(I2S_NUM_0, &config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);

  Serial.println("I2S READY");
}

// SETUP
void setup() {
  Serial.begin(115200);
  Serial.println("BOOT OK");

  // WiFi
  WiFi.begin(ssid, password);
  Serial.println("WiFi connecting...");
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(200);
  }
  Serial.println("\nWiFi CONNECTED");
  Serial.print("IP ESP32 : ");
  Serial.println(WiFi.localIP());

  udp.begin(udpPort);
  Serial.println("UDP READY");

  // BLE
  Serial.println("BLE init...");
  BLEDevice::init("");

  BLEScan* scan = BLEDevice::getScan();
  scan->setActiveScan(true);
  Serial.println("Scanning BLE...");
  BLEScanResults* res = scan->start(5);

  BLEAdvertisedDevice* target = nullptr;
  for (int i = 0; i < res->getCount(); i++) {
    if (res->getDevice(i).getName() == targetName)
      target = new BLEAdvertisedDevice(res->getDevice(i));
  }

  if (!target) {
    Serial.println("ERROR: Capteur BLE introuvable !");
    return;
  }
  Serial.println("Capteur BLE trouvé !");

  BLEClient* client = BLEDevice::createClient();
  Serial.println("Connexion BLE...");
  client->connect(target);
  Serial.println("BLE CONNECTED");

  client->setMTU(247);

  BLERemoteService* service = client->getService(serviceUUID);
  if (!service) { Serial.println("SERVICE FAIL"); return; }
  Serial.println("SERVICE OK");// L’ESP32 a trouvé le service BLE du capteur.

  BLERemoteCharacteristic* dataChar = service->getCharacteristic(dataUUID);
  cmdChar = service->getCharacteristic(cmdUUID);
  if (!dataChar || !cmdChar) { Serial.println("CHAR FAIL"); return; }
  Serial.println("CHAR OK");// ’ESP32 a trouvé les characteristics 

  uint8_t startCmd[4] = {0x55,0x01,0x01,0xA7};
  cmdChar->writeValue(startCmd,4);
  delay(100);

  // IMPORTANT : bascule le capteur en MODE VIBRATION.
  // Sans cette commande, les trames 0x55 0x61 arrivent bien mais les valeurs
  // (VX, VY, VZ, ...) restent à 0.
  uint8_t modeVib[4] = {0x55,0x02,0x01,0xA8};
  cmdChar->writeValue(modeVib,4);
  delay(100);

  // Règle le débit d'envoi des trames
  uint8_t rrate[4] = {0x55,0x03,0x14,0x6C};
  cmdChar->writeValue(rrate,4);
  delay(100);

  Serial.println("CMD SENT");// L''ESP32 à envoyer la commande start

  dataChar->registerForNotify(notifyCB);
  Serial.println("NOTIFY READY");
}

// LOOP
void loop() {

  int size = udp.parsePacket();
  if (size > 0) {
    char cmd[20];
    int len = udp.read(cmd, sizeof(cmd)-1);
    cmd[len] = '\0';  // FIN DE CHAINE → évite les bugs

    if (String(cmd).startsWith("START")) {// débute l'acquisition 
      setupI2S();// initialise le micro I2S
      microActive = true;// active l'envoi du son
      vibActive   = true;// active l'envoi des vibrations
      vibFrame.clear();   // IMPORTANT, on vide la trame BLE 
      Serial.println("START RECEIVED");
    }

    if (String(cmd).startsWith("STOP")) {// on coupe l'envoie des acquisitions
      microActive = false;// on coupe l'envoie du micro
      vibActive   = false;// on coupe l'envoie des vibrationq
      Serial.println("STOP RECEIVED");
    }
  }

  if (microActive) {
    int32_t samples[BUFFER_LEN];
    size_t bytesRead;

    i2s_read(I2S_NUM_0, samples, sizeof(samples), &bytesRead, portMAX_DELAY);

    char msg[300];
    int p = snprintf(msg, sizeof(msg), "SOUND,%lu", millis());

    int n = bytesRead / sizeof(int32_t);
    for (int i = 0; i < n; i++)
      p += snprintf(msg+p, sizeof(msg)-p, ",%ld", samples[i] >> 13);

    // Envoi Noa
    udp.beginPacket(udpAddress1, udpPort);
    udp.write((uint8_t*)msg, p);
    udp.endPacket();
    
    // Envoi Ege
    udp.beginPacket(udpAddress2, udpPort);
    udp.write((uint8_t*)msg, p);
    udp.endPacket();

    Serial.println();
    Serial.println(msg);
  }
}
