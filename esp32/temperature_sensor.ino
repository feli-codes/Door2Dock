#include <WiFi.h>
#include <HTTPClient.h>

const char* WIFI_SSID    = ""; //deleted for privacy
const char* WIFI_PASS    = ""; //deleted for privacy
const char* SUPABASE_URL = "https://ywoquxtqqzkoxakrxhfd.supabase.co";
const char* SUPABASE_KEY = ""; //deleted for privacy

const int ANALOG_PIN = 1;
const unsigned long INTERVAL_MS = 10000; // 10 seconds

// NTC thermistor parameters (KY-028)
const float B_COEFF   = 3950.0;
const float T_NOMINAL = 25.0;
const float R_NOMINAL = 10000.0;
const float R_SERIES  = 10000.0;

unsigned long lastSend = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  analogReadResolution(12); // 0-4095

  Serial.println("Connecting to WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected! IP: ");
  Serial.println(WiFi.localIP());
}

float adcToTempC(int adc) {
  if (adc == 0) return -999;
  float resistance = R_SERIES * (4095.0 - adc) / adc;

  float steinhart = log(resistance / R_NOMINAL);
  steinhart /= B_COEFF;
  steinhart += 1.0 / (T_NOMINAL + 273.15);
  steinhart = 1.0 / steinhart - 273.15;
  return steinhart;
}

void sendToSupabase(float tempC, int rawAdc) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected, reconnecting...");
    WiFi.reconnect();
    return;
  }

  HTTPClient http;
  String url = String(SUPABASE_URL)
             + "/rest/v1/temperature_readings";

  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("apikey", SUPABASE_KEY);
  http.addHeader("Authorization",
                 String("Bearer ") + SUPABASE_KEY);
  http.addHeader("Prefer", "return=minimal");

  String body = "{\"temperature_c\":" + String(tempC, 2)
              + ",\"raw_adc\":" + String(rawAdc) + "}";

  int code = http.POST(body);
  if (code == 201) {
    Serial.println("  -> Saved to Supabase");
  } else {
    Serial.print("  -> Error: ");
    Serial.println(code);
    Serial.println(http.getString());
  }
  http.end();
}

void loop() {
  if (millis() - lastSend >= INTERVAL_MS) {
    lastSend = millis();

    // Average 10 reads for stability
    long sum = 0;
    for (int i = 0; i < 10; i++) {
      sum += analogRead(ANALOG_PIN);
      delay(10);
    }
    int avgAdc = sum / 10;
    float tempC = adcToTempC(avgAdc);

    Serial.print("ADC: ");
    Serial.print(avgAdc);
    Serial.print(" | Temp: ");
    Serial.print(tempC, 2);
    Serial.println(" C");

    sendToSupabase(tempC, avgAdc);
  }
}