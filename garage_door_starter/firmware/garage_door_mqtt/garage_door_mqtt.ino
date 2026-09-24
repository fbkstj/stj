/*
 * 地下室鐵捲門 · ESP32 + MQTT 遠端控制
 * 對象：格來得 Gliderol G+ 主板（韌體 140512-V2011C）EXCON 綠色 7P 端子
 *
 * 接線（詳見 ESP32與格來得接線圖_列印白底版.svg）
 *   D25 → 繼電器 IN1 → NO1 → 格來得 PIN1 ▲ 開門
 *   D26 → 繼電器 IN2 → NO2 → 格來得 PIN2 ■ 停止
 *   D27 → 繼電器 IN3 → NO3 → 格來得 PIN3 ▼ 關門
 *   COM1+2+3 → 格來得 PIN7 GND
 *   D32 → 磁簧開關 → 另一腳接 ESP32 GND（門關到底導通 = LOW）
 *
 * 控制方式：繼電器脈衝 PULSE_MS 毫秒（等於按一下牆上按鈕），不是持續吸合。
 *
 * MQTT（三個動作各一個 topic，收到訊息就觸發，內容不拘）
 *   訂閱 <前綴>/open   ← 開門
 *   訂閱 <前綴>/close  ← 關門
 *   訂閱 <前綴>/pause  ← 停止
 *   發布 <前綴>/state  → open / closed （retain）
 *   發布 <前綴>/avail  → online / offline（retain，含遺囑）
 *
 * 防誤動作機制
 *   1. 開機時先 digitalWrite(RELAY_OFF=LOW) 再 pinMode(OUTPUT)，開機不會送出脈衝
 *   2. clean session，不接收離線期間累積的指令
 *   3. 連線後主動清掉 cmd topic 上的 retain 訊息，避免重連就自己開門
 *   4. 連線後 IGNORE_AFTER_CONNECT_MS 內不執行任何指令
 *   5. 同一指令 DEDUP_MS 內重複送達只執行一次
 *   6. 三路互鎖：startPulse() 先全放開再吸合，loop() 每圈再用 enforceInterlock()
 *      把不該吸合的腳位壓回去，任何時刻最多只有一路吸合
 *   7. WiFi 斷線期間強制全放開
 *
 * WiFi：依 secrets.h 的 WIFI_APS 順序嘗試（第一順位 → 第二順位），斷線後重新依序找。
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <time.h>
#include "secrets.h"

// ---------------- 腳位 ----------------
const int PIN_OPEN  = 25;
const int PIN_STOP  = 26;
const int PIN_CLOSE = 27;
const int PIN_REED  = 32;

/*
 * 高態觸發（High Level Trigger）模組
 *   閒置：輸出 LOW  → 繼電器放開（不吸）← 預設狀態
 *   觸發：輸出 HIGH → 繼電器吸合，PULSE_MS 毫秒後自動放回 LOW
 * 若日後換成低態觸發的模組，把下面兩行對調即可。
 */
const int RELAY_ON  = HIGH;   // 吸合
const int RELAY_OFF = LOW;    // 放開（預設狀態）

// ---------------- 參數 ----------------
const unsigned long PULSE_MS                 = 500;   // 脈衝長度（按一下的時間）
const unsigned long DEDUP_MS                 = 1500;  // 這段時間內的重複指令不執行
const unsigned long IGNORE_AFTER_CONNECT_MS  = 3000;  // 剛連上 Broker 先不接受指令
const unsigned long REED_DEBOUNCE_MS         = 300;   // 磁簧防彈跳
const unsigned long MQTT_RETRY_MS            = 5000;  // Broker 重連間隔
const unsigned long WIFI_TRY_MS               = 8000;  // 每組 WiFi 各試這麼久
const unsigned long WIFI_RETRY_MS             = 15000; // 全部連不上時，隔多久再掃一輪

WiFiClientSecure net;
PubSubClient mqtt(net);

int           activePin        = -1;      // 目前吸合中的腳位，-1 = 都放開
unsigned long pulseStartMs     = 0;
unsigned long lastCmdMs        = 0;
String        lastCmd          = "";
unsigned long mqttConnectedMs  = 0;
unsigned long lastMqttTryMs    = 0;
int           reedStable       = -1;
int           reedLastRead     = -1;
unsigned long reedChangedMs    = 0;
bool          timeSynced       = false;   // NTP 是否已校時成功（TLS 驗證憑證要用）
unsigned long lastWifiTryMs    = 0;
unsigned long lastNtpTryMs     = 0;

// ---------------- 繼電器 ----------------
const int RELAY_PINS[3] = { PIN_OPEN, PIN_STOP, PIN_CLOSE };

void relayOff(int pin) {
  digitalWrite(pin, RELAY_OFF);
}

// 開機時先把電位設成「放開」再切輸出，開機瞬間不會有觸發脈衝。
// 寫三次是刻意的：切成 OUTPUT 前後都壓一次，確保任何順序下都不會冒出脈衝。
void relayInit(int pin) {
  digitalWrite(pin, RELAY_OFF);
  pinMode(pin, OUTPUT);
  digitalWrite(pin, RELAY_OFF);
  digitalWrite(pin, RELAY_OFF);
}

void allRelaysOff() {
  for (int i = 0; i < 3; i++) relayOff(RELAY_PINS[i]);
  activePin = -1;
}

/*
 * 硬性互鎖：每次 loop() 都呼叫。
 *   activePin == -1 → 三隻腳全部壓回放開
 *   activePin != -1 → 只留該腳，另外兩隻無條件壓回放開
 * 就算程式其他地方寫錯、或腳位被干擾拉起來，下一圈 loop 也會被壓回去，
 * 確保任何時刻最多只有一路吸合。
 */
void enforceInterlock() {
  for (int i = 0; i < 3; i++) {
    if (RELAY_PINS[i] != activePin) relayOff(RELAY_PINS[i]);
  }
}

// 開始一個脈衝。不使用 delay()，由 loop() 負責放開。
bool startPulse(int pin, const char *name) {
  if (activePin != -1) {
    Serial.printf("[略過] 上一個脈衝尚未結束：%s\n", name);
    return false;
  }
  allRelaysOff();                 // 互鎖：確保三路都是放開的
  delayMicroseconds(200);         // 讓另外兩路確實落下再吸合這一路
  digitalWrite(pin, RELAY_ON);    // 吸合
  activePin    = pin;
  pulseStartMs = millis();
  Serial.printf("[動作] %s 觸發 %lu ms\n", name, PULSE_MS);
  if (mqtt.connected()) mqtt.publish(TOPIC_LOG, name);
  return true;
}

// ---------------- MQTT ----------------
// 三個動作各有專屬 topic，收到訊息就觸發，不看內容（空訊息也算）。
void onMqttMessage(char *topic, byte *payload, unsigned int len) {
  String t(topic);
  String body;
  for (unsigned int i = 0; i < len && i < 32; i++) body += (char)payload[i];
  Serial.printf("[MQTT] 收到 %s（內容：%s）\n", topic, body.length() ? body.c_str() : "(空)");

  unsigned long now = millis();
  if (now - mqttConnectedMs < IGNORE_AFTER_CONNECT_MS) {
    Serial.println("[略過] 剛連上線，先不執行（可能是舊訊息）");
    return;
  }
  if (t == lastCmd && now - lastCmdMs < DEDUP_MS) {
    Serial.println("[略過] 短時間內重複的指令");
    return;
  }

  bool done = false;
  if      (t == TOPIC_OPEN)  done = startPulse(PIN_OPEN,  "OPEN");
  else if (t == TOPIC_PAUSE) done = startPulse(PIN_STOP,  "PAUSE");
  else if (t == TOPIC_CLOSE) done = startPulse(PIN_CLOSE, "CLOSE");
  else Serial.println("[略過] 不是控制用的 topic");

  if (done) { lastCmd = t; lastCmdMs = now; }
}

void publishState(bool force = false) {
  if (!mqtt.connected() || reedStable < 0) return;
  const char *s = (reedStable == LOW) ? "closed" : "open";
  mqtt.publish(TOPIC_STATE, s, true);
  Serial.printf("[狀態] 門目前是 %s%s\n", s, force ? "（重新發布）" : "");
}

void connectMqtt() {
  if (WiFi.status() != WL_CONNECTED) return;

  String clientId = "garage-b1-" + WiFi.macAddress();
  clientId.replace(":", "");
  Serial.printf("[MQTT] 連線 %s:%d ...\n", MQTT_HOST, MQTT_PORT);

  // 遺囑：ESP32 斷線時由 Broker 代發 offline
  if (mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASS,
                   TOPIC_AVAIL, 1, true, "offline", true /* clean session */)) {
    mqttConnectedMs = millis();
    Serial.println("[MQTT] 連線成功");
    mqtt.publish(TOPIC_AVAIL, "online", true);
    // 清掉三個控制 topic 上殘留的 retain 訊息，避免一重連就自己動作
    mqtt.publish(TOPIC_OPEN,  "", true);
    mqtt.publish(TOPIC_CLOSE, "", true);
    mqtt.publish(TOPIC_PAUSE, "", true);
    mqtt.subscribe(TOPIC_OPEN,  1);
    mqtt.subscribe(TOPIC_CLOSE, 1);
    mqtt.subscribe(TOPIC_PAUSE, 1);
    publishState(true);
  } else {
    Serial.printf("[MQTT] 連線失敗，rc=%d，%lu 秒後重試\n", mqtt.state(), MQTT_RETRY_MS / 1000);
  }
}

// ---------------- WiFi（多組，依 secrets.h 的順序嘗試） ----------------
// 逐一嘗試 WIFI_APS，每組最多等 WIFI_TRY_MS。連上就回傳 true。
bool connectWifi() {
  WiFi.mode(WIFI_STA);
  for (int i = 0; i < WIFI_AP_COUNT; i++) {
    Serial.printf("[WiFi] 嘗試第 %d 組：%s", i + 1, WIFI_APS[i].ssid);
    WiFi.begin(WIFI_APS[i].ssid, WIFI_APS[i].pass);
    unsigned long t0 = millis();
    while (millis() - t0 < WIFI_TRY_MS) {
      if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WiFi] 已連線 %s，IP = %s，訊號 %d dBm\n",
                      WIFI_APS[i].ssid, WiFi.localIP().toString().c_str(), WiFi.RSSI());
        WiFi.setAutoReconnect(true);   // 同一台分享器短暫斷線時自動接回
        return true;
      }
      delay(250);
      Serial.print(".");
      enforceInterlock();              // 連線期間也持續壓住繼電器
    }
    Serial.println(" 失敗");
    WiFi.disconnect(true);
    delay(100);
  }
  Serial.println("[WiFi] 全部都連不上，稍後重試");
  return false;
}

// ---------------- 時間（TLS 驗證憑證需要正確時間） ----------------
void syncTime() {
  configTime(8 * 3600, 0, "time.google.com", "tw.pool.ntp.org", "pool.ntp.org");
  Serial.print("[NTP] 校時中");
  time_t now = 0;
  for (int i = 0; i < 40 && now < 1700000000; i++) {   // 最多等 20 秒
    delay(500);
    Serial.print(".");
    time(&now);
  }
  Serial.println();
  if (now < 1700000000) {
    Serial.println("[NTP] 校時失敗，TLS 可能無法驗證憑證，稍後重試");
  } else {
    timeSynced = true;
    struct tm tm_now;
    localtime_r(&now, &tm_now);
    Serial.printf("[NTP] 目前時間 %04d-%02d-%02d %02d:%02d:%02d\n",
                  tm_now.tm_year + 1900, tm_now.tm_mon + 1, tm_now.tm_mday,
                  tm_now.tm_hour, tm_now.tm_min, tm_now.tm_sec);
  }
}

// ---------------- setup / loop ----------------
void setup() {
  relayInit(PIN_OPEN);
  relayInit(PIN_STOP);
  relayInit(PIN_CLOSE);
  pinMode(PIN_REED, INPUT_PULLUP);

  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== 地下室鐵捲門 ESP32 · MQTT 控制 ===");
  Serial.println("繼電器全部放開，開始連線");

  if (connectWifi()) syncTime();
  lastWifiTryMs = millis();

  net.setCACert(MQTT_ROOT_CA);        // 驗證 Broker 憑證（Let's Encrypt）
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  mqtt.setKeepAlive(30);
  mqtt.setBufferSize(512);

  reedLastRead  = digitalRead(PIN_REED);
  reedStable    = reedLastRead;
  reedChangedMs = millis();
}

void loop() {
  unsigned long now = millis();

  // 1. 脈衝時間到就放開（不用 delay，MQTT 才不會卡住）
  if (activePin != -1 && now - pulseStartMs >= PULSE_MS) {
    allRelaysOff();
    Serial.println("[動作] 繼電器已放開");
  }

  // 1b. 硬性互鎖：每一圈都把不該吸合的腳位壓回放開
  enforceInterlock();

  // 2. WiFi／MQTT 維持連線
  if (WiFi.status() != WL_CONNECTED) {
    allRelaysOff();                         // 沒網路時一律保持全放開
    if (now - lastWifiTryMs > WIFI_RETRY_MS) {
      Serial.println("[WiFi] 斷線，重新依序嘗試各組 WiFi");
      connectWifi();
      lastWifiTryMs = millis();
    }
  } else if (!timeSynced && (lastNtpTryMs == 0 || now - lastNtpTryMs > 30000)) {
    lastNtpTryMs = now;
    // 停電復電時分享器往往比 ESP32 慢開機，開機當下沒校到時這裡補做一次，
    // 否則 TLS 會因為時間不對而永遠驗證失敗，門就再也遙控不了。
    syncTime();
  } else if (!mqtt.connected()) {
    if (now - lastMqttTryMs > MQTT_RETRY_MS) { lastMqttTryMs = now; connectMqtt(); }
  } else {
    mqtt.loop();
  }

  // 3. 磁簧門況（防彈跳後才發布）
  int r = digitalRead(PIN_REED);
  if (r != reedLastRead) { reedLastRead = r; reedChangedMs = now; }
  if (r != reedStable && now - reedChangedMs > REED_DEBOUNCE_MS) {
    reedStable = r;
    publishState();
  }
}
