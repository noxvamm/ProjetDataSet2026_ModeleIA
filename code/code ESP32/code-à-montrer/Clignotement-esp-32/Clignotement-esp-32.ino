#define LED 2// déclaration 

void setup() {
  pinMode(LED, OUTPUT);// fonction qui permet de configurer un pin ( output pour envoyer du courant )
â

void loop() {
  digitalWrite(LED, HIGH);// fonction pour faire clignoter la led ( grâce au high)
  delay(500);// arduino compte le temps en miliseconde
  digitalWrite(LED, LOW);
  delay(500);
}
