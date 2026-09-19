// 選配：ESP32 現場警示燈與蜂鳴器
// 電腦程式透過 USB 序列埠送出字元：A = 開始警示、C = 解除
// 接線：GPIO 2 → 220Ω → LED → GND；GPIO 4 → 主動式蜂鳴器（+）；蜂鳴器（-）→ GND
// 只使用 3.3V／5V 低壓元件，不要接市電。

const int LED_PIN = 2;
const int BUZZER_PIN = 4;
bool alerting = false;
unsigned long lastToggle = 0;
bool ledOn = false;

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
}

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == 'A') {
      alerting = true;
    } else if (c == 'C') {
      alerting = false;
      digitalWrite(LED_PIN, LOW);
      digitalWrite(BUZZER_PIN, LOW);
    }
  }

  // 警示時 LED 每 0.5 秒閃爍，蜂鳴器跟著短響
  if (alerting && millis() - lastToggle >= 500) {
    lastToggle = millis();
    ledOn = !ledOn;
    digitalWrite(LED_PIN, ledOn ? HIGH : LOW);
    digitalWrite(BUZZER_PIN, ledOn ? HIGH : LOW);
  }
}
