#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s.h>
#include <BLEDevice.h>
#include <vector>

// CONFIG
#define I2S_SD   32
#define I2S_WS   25
#define I2S_SCK  14
// 16 kHz : doit rester aligné avec SAMPLE_RATE_SON du client UDP Python
// et avec la fréquence du dataset d'entraînement du modèle
#define SAMPLE_RATE 16000
#define BUFFER_LEN 128

// Trame son : 128 échantillons × 8 caractères max (",-262143") + en-tête.
// 1500 reste sous le MTU WiFi (pas de fragmentation UDP).
#define SOUND_MSG_SIZE 1500

const char* ssid = "lewifiduciel";
const char* password = "cielmonwifi";

// Destinataires UDP — ⚠️ IP DHCP du lycée : à vérifier avec ipconfig le jour J
const char* IP_NOA   = "172.21.1.197";  // PC Noa (client UDP Python) — relevée le 12/06
const int   PORT_NOA = 9091;

const char* IP_EGE   = "172.21.1.197";  // PC Ege
const int   PORT_EGE = 9092;

// IHM Qt : port dédié pour ne pas entrer en conflit avec le client UDP
// Python quand les deux tournent sur le même PC (un port = un consommateur)
const char* IP_IHM   = "172.21.1.197";  // PC qui fait tourner l'IHM
const int   PORT_IHM = 9093;

// Port d'écoute des commandes START/STOP.
// L'IHM Qt envoie sur 9092 (ESP32_PORT) : toute appli qui pilote
// l'acquisition doit envoyer ses commandes sur CE port.
const int   PORT_COMMANDE = 9092;

// Instance UDP unique — partagée entre loop() (trames SOUND) et le callback
// BLE notifyCB() (trames VIB) qui tourne sur une AUTRE tâche FreeRTOS.
// Le mutex empêche les deux envois de s'entremêler dans le même paquet
// (sans lui : échantillons corrompus type "-7116V" dans les CSV).
WiFiUDP udp;
SemaphoreHandle_t udpMutex;

// Flags
bool microActive = false;
bool vibActive   = false;

// BLE
String targetName = "WTVB01-BT50";
BLEUUID serviceUUID("0000ffe5-0000-1000-8000-00805f9a34fb");
BLEUUID dataUUID   ("0000ffe4-0000-1000-8000-00805f9a34fb");
BLEUUID cmdUUID    ("0000ffe9-0000-1000-8000-00805f9a34fb");

BLERemoteCharacteristic* cmdChar;
std::vector<uint8_t> vibFrame;

uint16_t read16(const std::vector<uint8_t>& b, int i) {
  return b[i] | (b[i+1] << 8);
}

// BLE CALLBACK
void notifyCB(BLERemoteCharacteristic*, uint8_t* data, size_t len, bool) {
  if (!vibActive) return;

  if (len >= 2 && data[0] == 0x55 && data[1] == 0x61)
      vibFrame.clear();

  vibFrame.insert(vibFrame.end(), data, data + len);

  if (vibFrame.size() >= 28 && vibFrame[0] == 0x55 && vibFrame[1] == 0x61) {

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

    // Envois protégés par le mutex (cf. déclaration de udpMutex)
    xSemaphoreTake(udpMutex, portMAX_DELAY);

    // Envoi Noa
    udp.beginPacket(IP_NOA, PORT_NOA);
    udp.print(msg);
    udp.endPacket();

    // Envoi Ege
    udp.beginPacket(IP_EGE, PORT_EGE);
    udp.print(msg);
    udp.endPacket();

    // Envoi IHM
    udp.beginPacket(IP_IHM, PORT_IHM);
    udp.print(msg);
    udp.endPacket();

    xSemaphoreGive(udpMutex);

    Serial.println(msg);
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

  WiFi.begin(ssid, password);
  Serial.println("WiFi connecting...");
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(200);
  }
  Serial.println("\nWiFi CONNECTED");
  Serial.print("IP ESP32 : ");
  Serial.println(WiFi.localIP());

  // Mutex protégeant l'instance UDP partagée entre loop() et le callback BLE
  udpMutex = xSemaphoreCreateMutex();

  // Écoute des commandes START/STOP (port aligné sur l'IHM)
  udp.begin(PORT_COMMANDE);
  Serial.println("UDP READY");

  // BLE
  BLEDevice::init("");
  BLEScan* scan = BLEDevice::getScan();
  scan->setActiveScan(true);
  BLEScanResults* res = scan->start(5);

  BLEAdvertisedDevice* target = nullptr;
  for (int i = 0; i < res->getCount(); i++) {
    if (res->getDevice(i).getName() == targetName)
      target = new BLEAdvertisedDevice(res->getDevice(i));
  }

  if (!target) { Serial.println("ERROR: Capteur BLE introuvable !"); return; }

  BLEClient* client = BLEDevice::createClient();
  client->connect(target);
  client->setMTU(247);

  BLERemoteService* service = client->getService(serviceUUID);
  if (!service) { Serial.println("SERVICE FAIL"); return; }

  BLERemoteCharacteristic* dataChar = service->getCharacteristic(dataUUID);
  cmdChar = service->getCharacteristic(cmdUUID);
  if (!dataChar || !cmdChar) { Serial.println("CHAR FAIL"); return; }

  uint8_t startCmd[4] = {0x55,0x01,0x01,0xA7};
  cmdChar->writeValue(startCmd,4);

  dataChar->registerForNotify(notifyCB);
  Serial.println("NOTIFY READY");
}

// LOOP
void loop() {

  // Réception des commandes START/STOP
  int size = udp.parsePacket();
  if (size > 0) {
    char cmd[20];
    int len = udp.read(cmd, sizeof(cmd)-1);
    if (len < 0) len = 0;
    cmd[len] = '\0';

    if (String(cmd).startsWith("START")) {
      setupI2S();
      microActive = true;
      vibActive = true;
      vibFrame.clear();
      Serial.print("START depuis ");
      Serial.println(udp.remoteIP());
    }

    if (String(cmd).startsWith("STOP")) {
      microActive = false;
      vibActive = false;
      Serial.print("STOP depuis ");
      Serial.println(udp.remoteIP());
    }
  }

  // Envoi du son
  if (microActive) {
    int32_t samples[BUFFER_LEN];
    size_t bytesRead;

    i2s_read(I2S_NUM_0, samples, sizeof(samples), &bytesRead, portMAX_DELAY);

    static char msg[SOUND_MSG_SIZE];
    int p = snprintf(msg, sizeof(msg), "SOUND,%lu", millis());

    int n = bytesRead / sizeof(int32_t);
    for (int i = 0; i < n; i++) {
      int ecrit = snprintf(msg+p, sizeof(msg)-p, ",%ld", (long)(samples[i] >> 13));
      if (ecrit < 0 || p + ecrit >= (int)sizeof(msg)) break;
      p += ecrit;
    }

    // Envois protégés par le mutex (cf. déclaration de udpMutex)
    xSemaphoreTake(udpMutex, portMAX_DELAY);

    // Envoi Noa
    udp.beginPacket(IP_NOA, PORT_NOA);
    udp.write((uint8_t*)msg, p);
    udp.endPacket();

    // Envoi Ege
    udp.beginPacket(IP_EGE, PORT_EGE);
    udp.write((uint8_t*)msg, p);
    udp.endPacket();

    // Envoi IHM
    udp.beginPacket(IP_IHM, PORT_IHM);
    udp.write((uint8_t*)msg, p);
    udp.endPacket();

    xSemaphoreGive(udpMutex);

    // Pas de Serial.println(msg) ici : imprimer ~1 ko à 115200 bauds
    // prend ~90 ms et ferait chuter le débit de 125 paquets/s à ~10.
    // On loggue juste un battement toutes les ~2 s pour vérifier l'activité.
    static uint32_t paquetsEnvoyes = 0;
    paquetsEnvoyes++;
    if (paquetsEnvoyes % 250 == 0) {
      Serial.print("SOUND paquets envoyes : ");
      Serial.println(paquetsEnvoyes);
    }
  }
}
