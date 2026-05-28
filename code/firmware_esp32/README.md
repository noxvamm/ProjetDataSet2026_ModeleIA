# Firmware ESP32

- `firmware_esp32_corrige.ino` — version corrigée (snprintf, APLL, buffers DMA agrandis).
- `code_esp32.txt` — copie texte du firmware pour consultation rapide.

## Compilation

Arduino IDE 2.x ou PlatformIO. Carte cible : ESP32 (esp32 by Espressif Systems).

Bibliothèques requises : `WiFi.h`, `WiFiUdp.h`, `driver/i2s.h`, `BLEDevice.h`.

## Configuration

Avant flash, remplacer dans le code :
```c
const char* ssid     = "<VOTRE_SSID_WIFI>";
const char* password = "<VOTRE_MOT_DE_PASSE>";
```
par votre réseau Wi-Fi. **Ne jamais committer de vrais identifiants.**
