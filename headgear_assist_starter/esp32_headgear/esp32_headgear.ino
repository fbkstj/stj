// 頭部障礙物警示帽：ESP32 韌體
// 功能：
//   1. 讀取左前、右前兩顆 VL53L1X 雷射測距模組
//   2. 距離越近，對應那一側的震動馬達震得越快（不需要等電腦，反應最快）
//   3. 每 0.1 秒把距離傳給筆電：D,左距離mm,右距離mm   （量不到時送 -1）
//   4. 按下帽子上的按鈕，送出：B   （請筆電描述前方）
//   5. 收到筆電送來的 T，兩顆馬達各震一下（測試用）
//
// 需要的程式庫：Arduino IDE → 程式庫管理員 → 搜尋「VL53L1X」→ 安裝 Pololu 版
//
// 接線（ESP32 DevKit，全部使用 3.3V）：
//   VL53L1X 左、右：VIN→3V3、GND→GND、SDA→GPIO21、SCL→GPIO22
//                   左 XSHUT→GPIO16、右 XSHUT→GPIO17
//   震動馬達模組 左：IN→GPIO25；右：IN→GPIO26；VCC→3V3、GND→GND
//   按鈕：一腳接 GPIO27，另一腳接 GND
// 只使用低壓元件；不要把震動馬達直接接在 GPIO 上（電流太大），請用有驅動電晶體的模組。

#include <Wire.h>
#include <VL53L1X.h>

const int PIN_XSHUT_L = 16;
const int PIN_XSHUT_R = 17;
const int PIN_MOTOR_L = 25;
const int PIN_MOTOR_R = 26;
const int PIN_BUTTON = 27;

// 警示距離（公釐）：越近震動越急
const int DIST_NEAR = 600;    // 小於這個距離：持續震動
const int DIST_MID = 1000;    // 小於這個距離：快速短震
const int DIST_FAR = 1600;    // 小於這個距離：慢速短震；超過就不震

VL53L1X sensorL;
VL53L1X sensorR;
bool okL = false;
bool okR = false;
int distL = -1;
int distR = -1;

unsigned long lastSend = 0;
unsigned long testUntil = 0;
bool lastButton = HIGH;
unsigned long lastButtonChange = 0;

bool initSensor(VL53L1X &s, int xshutPin, uint8_t address) {
  digitalWrite(xshutPin, HIGH);  // 喚醒這一顆
  delay(20);
  s.setTimeout(100);
  if (!s.init()) {
    return false;
  }
  s.setAddress(address);         // 兩顆預設位址相同，要改成不同位址
  s.setDistanceMode(VL53L1X::Long);
  s.setMeasurementTimingBudget(50000);
  s.startContinuous(50);
  return true;
}

int readSensor(VL53L1X &s, bool ok) {
  if (!ok || !s.dataReady()) {
    return -2;                   // -2：這次沒有新資料，沿用上一次
  }
  int mm = s.read(false);
  if (s.timeoutOccurred() || s.ranging_data.range_status != VL53L1X::RangeValid) {
    return -1;                   // -1：量不到（太遠或反光不足）
  }
  return mm;
}

// 依距離決定這一刻馬達要不要開（用開關節奏表示遠近，不需要 PWM）
bool motorOn(int mm, unsigned long now) {
  if (mm < 0 || mm >= DIST_FAR) return false;
  if (mm < DIST_NEAR) return true;
  unsigned long period = (mm < DIST_MID) ? 200 : 500;
  return (now % period) < 100;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_XSHUT_L, OUTPUT);
  pinMode(PIN_XSHUT_R, OUTPUT);
  pinMode(PIN_MOTOR_L, OUTPUT);
  pinMode(PIN_MOTOR_R, OUTPUT);
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  digitalWrite(PIN_MOTOR_L, LOW);
  digitalWrite(PIN_MOTOR_R, LOW);

  // 先讓兩顆都關機，再一顆一顆開機並設定不同位址
  digitalWrite(PIN_XSHUT_L, LOW);
  digitalWrite(PIN_XSHUT_R, LOW);
  delay(20);
  Wire.begin(21, 22);
  Wire.setClock(400000);
  okL = initSensor(sensorL, PIN_XSHUT_L, 0x30);
  okR = initSensor(sensorR, PIN_XSHUT_R, 0x31);
  Serial.printf("I,left=%s,right=%s\n", okL ? "ok" : "fail", okR ? "ok" : "fail");
}

void loop() {
  unsigned long now = millis();

  int v = readSensor(sensorL, okL);
  if (v != -2) distL = v;
  v = readSensor(sensorR, okR);
  if (v != -2) distR = v;

  // 電腦送來的指令
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == 'T') testUntil = now + 600;
  }

  bool test = now < testUntil;
  digitalWrite(PIN_MOTOR_L, (test || motorOn(distL, now)) ? HIGH : LOW);
  digitalWrite(PIN_MOTOR_R, (test || motorOn(distR, now)) ? HIGH : LOW);

  // 按鈕（含防彈跳）
  bool b = digitalRead(PIN_BUTTON);
  if (b != lastButton && now - lastButtonChange > 50) {
    lastButtonChange = now;
    lastButton = b;
    if (b == LOW) Serial.println("B");
  }

  if (now - lastSend >= 100) {
    lastSend = now;
    Serial.printf("D,%d,%d\n", distL, distR);
  }
}
