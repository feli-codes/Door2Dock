#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID   = ""; //deleted for privacy
const char* WIFI_PASS   = ""; //deleted for privacy
const char* HEROKU_URL  = "https://smart-commute-imperial-0cac549c4dd9.herokuapp.com";

const int PIR_PIN = 13;
const unsigned long COOLDOWN_MS = 60000; // ignore re-triggers for 60s

unsigned long lastTrigger = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  pinMode(PIR_PIN, INPUT);

  Serial.println("Connecting to WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected! IP: ");
  Serial.println(WiFi.localIP());

  // Let PIR sensor stabilise (takes ~30-60s)
  Serial.println("Waiting for PIR to stabilise...");
  delay(30000);
  Serial.println("Ready.");
}

void sendDeparture() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected, reconnecting...");
    WiFi.reconnect();
    return;
  }

  HTTPClient http;
  String url = String(HEROKU_URL) + "/api/sensor-event";

  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  String body = "{\"event_type\":\"departure\",\"confidence\":1.0}";

  int code = http.POST(body);
  if (code == 200 || code == 201) {
    Serial.println("  -> Departure event sent to Heroku");
  } else {
    Serial.print("  -> Error: ");
    Serial.println(code);
    Serial.println(http.getString());
  }
  http.end();
}

void loop() {
  if (digitalRead(PIR_PIN) == HIGH) {
    if (millis() - lastTrigger >= COOLDOWN_MS) {
      lastTrigger = millis();
      Serial.println("Motion detected! Sending departure event...");
      sendDeparture();
    }
  }
  delay(200);
}