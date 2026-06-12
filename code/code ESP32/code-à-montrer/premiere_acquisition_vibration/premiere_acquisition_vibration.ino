#include <BLEDevice.h>

String targetName = "WTVB01-BT50";
// variable, type et le nom de variable 
static BLEUUID serviceUUID("0000ffe5-0000-1000-8000-00805f9a34fb");// ou sont stocker les infos de vibrations 
static BLEUUID dataUUID("0000ffe4-0000-1000-8000-00805f9a34fb");   // NOTIFY identifie les caractériques qui envoie les vibrations
static BLEUUID cmdUUID ("0000ffe9-0000-1000-8000-00805f9a34fb");   // WRITE identifie ma caractéristique qui reçoit les comandes 
// uint= type de donnée : entier non signé
std::vector<uint8_t> frameBuffer; // petite mémoire temporaire où l'ESP32 stocke les morceaux de trames BLE

uint16_t read16(const std::vector<uint8_t>& buf, int index) {
  return buf[index] | (buf[index + 1] << 8);
} //  on combine deux octets pour une valeur 16bits car le capteur envoie ses valeurs en petit morceaux (otcets)

void decodeFrame(const std::vector<uint8_t>& buf) { // cette fonction lit la trame complète 28 octets
  Serial.println("\n=== TRAME DECODEE ===");

  int d = 2;  // après 55 61

  Serial.printf("VX  = %u\n", read16(buf, d)); d+=2;// on lit 2 octets en avançant de 2
  Serial.printf("VY  = %u\n", read16(buf, d)); d+=2;
  Serial.printf("VZ  = %u\n", read16(buf, d)); d+=2;

  Serial.printf("ADX = %u\n", read16(buf, d)); d+=2;
  Serial.printf("ADY = %u\n", read16(buf, d)); d+=2;
  Serial.printf("ADZ = %u\n", read16(buf, d)); d+=2;

  Serial.printf("TEMP = %u (%.2f°C)\n", read16(buf, d), read16(buf, d)/100.0); d+=2;

  Serial.printf("DX  = %u\n", read16(buf, d)); d+=2;
  Serial.printf("DY  = %u\n", read16(buf, d)); d+=2;
  Serial.printf("DZ  = %u\n", read16(buf, d)); d+=2;

  Serial.printf("HZX = %u\n", read16(buf, d)); d+=2;
  Serial.printf("HZY = %u\n", read16(buf, d)); d+=2;
  Serial.printf("HZZ = %u\n", read16(buf, d)); d+=2;
}

void notifyCallback(BLERemoteCharacteristic* c, uint8_t* data, size_t length, bool isNotify) {// fonction appelée automatiquement pour recevoir les morceaux de trames du capteur

  if (length >= 2 && data[0] == 0x55 && data[1] == 0x61) {// en tête d'une trame vibration
    frameBuffer.clear();// on vide le buffer 
  }
  frameBuffer.insert(frameBuffer.end(), data, data + length);// ajoute les octets dans le buffer car BLE envoie plusieurs octets

  if (frameBuffer.size() >= 32) { // on accumule les octets jusqu'à 32 octets
    Serial.println(">> TRAME COMPLÈTE !");
    decodeFrame(frameBuffer); // pour décoder la trame 
    frameBuffer.clear(); // on la vide
  }
}// on vide la trame pour ne pas mélanger les données avec la trame suivante 

void setup() {
  Serial.begin(115200); // vitesse communication entre L'ESP32 et mon pc 
  Serial.println("Scan BLE...");

  BLEDevice::init("");//l ’ESP32 active le Bluetooth Low Energy et prépare un scan actif.
  BLEScan* scan = BLEDevice::getScan();// l’ESP32 envoie des requêtes BLE pour obtenir plus d’informations des appareils autour.
  scan->setActiveScan(true);

  BLEScanResults* results = scan->start(5);// recherche du capture  pendant 5s

  BLEAdvertisedDevice* target = nullptr;

  for (int i = 0; i < results->getCount(); i++) {// ici on parcourt tous les appreils BLE 
    BLEAdvertisedDevice dev = results->getDevice(i);// ici c'est l'appareil BLE trouvé
    if (dev.getName() == targetName) {// on regarde si on c'est bien son som nom 
      target = new BLEAdvertisedDevice(dev);// on sauvegarde cette appareil pour pouvoir s'y connecté
      break;// boucle arrété 
    }
  }

  if (!target) {
    Serial.println("Capteur non trouvé.");
    return;
  }

  Serial.println("Capteur trouvé !");
  BLEClient* client = BLEDevice::createClient();// peut crée un client BLE pour me connecter au capteur
  client->connect(target);// connexion BLE directe
  client->setMTU(64);// pour recevoir des trames plus grandes 

  BLERemoteService* service = client->getService(serviceUUID);// ESP 32 -> rentre dans le service BLE

  BLERemoteCharacteristic* dataChar = service->getCharacteristic(dataUUID);// ce qui permet à l'ESP32 de recevoir les trames de vibrations
  BLERemoteCharacteristic* cmdChar  = service->getCharacteristic(cmdUUID);//L'ESP32 peut envoyer des commandes au capteur ( fréquence , démarer l'envoie ou stopper)

  Serial.println("Activation du capteur...");
//uint8_t pour stocker les octets 
  uint8_t startStream[4] = {0x55, 0x01, 0x01, 0xA7};
  cmdChar->writeValue(startStream, 4, false);// méthode dynamique qui démarre le streaming 
  delay(100);
// 4 octets pour la commande BLE qui fait 4 octets
  uint8_t modeVib[4] = {0x55, 0x02, 0x01, 0xA8};
  cmdChar->writeValue(modeVib, 4, false);
  delay(100);// le capteur envoie les données 

  uint8_t rrate[4] = {0x55, 0x03, 0x0A, 0xB2};
  cmdChar->writeValue(rrate, 4, false);
  delay(100);// On règle la fréquence d'envoie 

  Serial.println("Commandes envoyées.");
  dataChar->registerForNotify(notifyCallback);// permet de recevoir les trames 

  Serial.println("Réception des trames...");
}

void loop() {}
