// 自行車「後方來車」警示：ESP32 燈號、蜂鳴器、TFT 文字、DFPlayer 語音
//
// 電腦傳來的指令（每行一個，以換行結尾，最多 8 個字元）：
//   S1B25   狀態：S＋等級(0 安全／1 注意／2 危險)＋車種(M 機車／C 汽車／B 大型車／N 無)＋到達秒數×10
//   L0～L2  舊版狀態（只有等級），仍然可以用
//   P1～P9  播放語音：microSD 卡 01 資料夾的 001～009 號檔案
//   V0～V30 語音音量
// 電腦每 0.2 秒送一次狀態；超過 OFFLINE_MS 沒收到 → 離線（綠燈慢閃、TFT 顯示未連線）
//
// 開發板選「ESP32 Dev Module」
// 需要的程式庫（Arduino IDE 程式庫管理員）：Adafruit ST7735 and ST7789 Library、Adafruit GFX Library
// DFPlayer 直接用序列指令控制，不需要另外安裝程式庫
//
// 接線：
//   綠／黃／紅 LED：GPIO25／26／27（各串 220Ω 到 GND）；主動式蜂鳴器模組 I/O：GPIO14
//   ST7735 1.8 吋 TFT：SCK→GPIO18、SDA(MOSI)→GPIO23、CS→GPIO5、A0(DC)→GPIO21、RST→GPIO22、
//                      VCC→3V3、GND→GND、LED(背光)→3V3
//   DFPlayer Mini：VCC→5V(VIN)、GND→GND、RX←1kΩ←GPIO17、TX→GPIO16、SPK_1／SPK_2→3W 喇叭

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#include "tft_labels.h"

const int PIN_GREEN  = 25;
const int PIN_YELLOW = 26;
const int PIN_RED    = 27;
const int PIN_BUZZER = 14;   // 主動式蜂鳴器模組，HIGH＝響

const int TFT_CS  = 5;
const int TFT_DC  = 21;
const int TFT_RST = 22;
const int DF_RX = 16;        // ESP32 接收（接 DFPlayer 的 TX）
const int DF_TX = 17;        // ESP32 傳送（經 1kΩ 接 DFPlayer 的 RX）

const unsigned long OFFLINE_MS = 1500;
const unsigned long VOICE_QUIET_MS = 1200;   // 播放語音時，蜂鳴器暫停這麼久

// 顏色（RGB565）
const uint16_t C_BLACK  = 0x0000;
const uint16_t C_WHITE  = 0xFFFF;
const uint16_t C_GREEN  = 0x0400;
const uint16_t C_YELLOW = 0xFFE0;
const uint16_t C_RED    = 0xC000;   // 上方色塊（配白字）
const uint16_t C_RED_TX = 0xF800;   // 黑底上的紅字，亮一點才看得清楚
const uint16_t C_GRAY   = 0x4208;

Adafruit_ST7735 tft(TFT_CS, TFT_DC, TFT_RST);

int level = -1;              // -1＝離線
char vehicle = 'N';
int tenths = 0;
unsigned long lastMsg = 0;
unsigned long quietUntil = 0;
String line;

// 畫面上目前顯示的內容（有變才重畫，避免閃爍）
int shownLevel = -2;
char shownVehicle = '?';
int shownTenths = -1;

// ---------- DFPlayer ----------
void dfSend(uint8_t cmd, uint16_t param) {
  uint8_t buf[10] = {0x7E, 0xFF, 0x06, cmd, 0x00, (uint8_t)(param >> 8), (uint8_t)(param & 0xFF), 0, 0, 0xEF};
  uint16_t sum = 0;
  for (int i = 1; i < 7; i++) sum += buf[i];
  sum = 0 - sum;
  buf[7] = sum >> 8;
  buf[8] = sum & 0xFF;
  Serial2.write(buf, 10);
}

void dfPlay(int n) {           // 播放 01 資料夾的第 n 號檔案（001.mp3 或 001.wav）
  dfSend(0x0F, (1 << 8) | n);
}

void dfVolume(int v) {
  dfSend(0x06, constrain(v, 0, 30));
}

// ---------- TFT ----------
void drawLabel(const Label &lb, int cx, int top, int bandH, uint16_t fg, uint16_t bg) {
  int x = cx - lb.w / 2;
  int y = top + (bandH - lb.h) / 2;
  tft.drawBitmap(x, y, lb.data, lb.w, lb.h, fg, bg);
}

void drawScreen() {
  int w = tft.width();   // 160
  bool levelChanged = level != shownLevel;

  // 上方色塊：等級
  if (levelChanged) {
    uint16_t bg = C_GRAY;
    uint16_t fg = C_WHITE;
    const Label *lb = &LBL_OFFLINE;
    if (level == 0) { bg = C_GREEN; lb = &LBL_SAFE; }
    if (level == 1) { bg = C_YELLOW; fg = C_BLACK; lb = &LBL_CAUTION; }
    if (level == 2) { bg = C_RED; lb = &LBL_DANGER; }
    tft.fillRect(0, 0, w, 40, bg);
    drawLabel(*lb, w / 2, 0, 40, fg, bg);
  }

  // 中間：車種
  char v = (level > 0) ? vehicle : 'N';
  if (levelChanged || v != shownVehicle) {
    tft.fillRect(0, 44, w, 36, C_BLACK);
    uint16_t fg = (level == 2) ? C_RED_TX : (level == 1 ? C_YELLOW : C_WHITE);
    if (level < 0) {
      drawLabel(LBL_CHECK, w / 2, 44, 36, C_WHITE, C_BLACK);
    } else if (v == 'M') {
      drawLabel(LBL_MOTO, w / 2, 44, 36, fg, C_BLACK);
    } else if (v == 'C') {
      drawLabel(LBL_CAR, w / 2, 44, 36, fg, C_BLACK);
    } else if (v == 'B') {
      drawLabel(LBL_BIG, w / 2, 44, 36, fg, C_BLACK);
    } else {
      drawLabel(LBL_NONE, w / 2, 44, 36, C_WHITE, C_BLACK);
    }
    shownVehicle = v;
  }

  // 下方：到達秒數（安全與離線時不顯示）
  int t = (level > 0) ? tenths : -1;
  if (levelChanged || t != shownTenths) {
    if (t < 0) {
      tft.fillRect(0, 84, w, 44, C_BLACK);
    } else {
      if (shownTenths < 0) {
        tft.fillRect(0, 84, w, 44, C_BLACK);
        drawLabel(LBL_ARRIVE, 124, 96, 24, C_WHITE, C_BLACK);
      }
      char buf[8];
      snprintf(buf, sizeof(buf), "%d.%d", t / 10, t % 10);   // 固定 3 個字元寬：0.0～9.9
      tft.setTextSize(3);
      tft.setTextColor(C_WHITE, C_BLACK);                     // 帶背景色，覆蓋舊數字不閃爍
      tft.setCursor(14, 96);
      tft.print(buf);
    }
    shownTenths = t;
  }
  shownLevel = level;
}

// ---------- 燈號與蜂鳴器 ----------
void setOutputs(bool g, bool y, bool r, bool buzz) {
  digitalWrite(PIN_GREEN, g);
  digitalWrite(PIN_YELLOW, y);
  digitalWrite(PIN_RED, r);
  digitalWrite(PIN_BUZZER, buzz && millis() >= quietUntil);
}

// ---------- 指令 ----------
void handleLine(const String &s) {
  unsigned long now = millis();
  if (s.length() == 2 && s[0] == 'L' && s[1] >= '0' && s[1] <= '2') {
    level = s[1] - '0';
    vehicle = 'N';
    tenths = 0;
    lastMsg = now;
  } else if (s.length() == 5 && s[0] == 'S' && s[1] >= '0' && s[1] <= '2' && isDigit(s[3]) && isDigit(s[4])) {
    level = s[1] - '0';
    vehicle = s[2];
    tenths = (s[3] - '0') * 10 + (s[4] - '0');
    lastMsg = now;
  } else if (s.length() == 2 && s[0] == 'P' && s[1] >= '1' && s[1] <= '9') {
    dfPlay(s[1] - '0');
    quietUntil = now + VOICE_QUIET_MS;
  } else if (s.length() >= 2 && s.length() <= 3 && s[0] == 'V') {
    dfVolume(s.substring(1).toInt());
  }
}

void readSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      handleLine(line);
      line = "";
    } else if (c != '\r' && line.length() < 8) {
      line += c;
    }
  }
  while (Serial2.available()) Serial2.read();   // DFPlayer 的回應用不到，讀掉即可
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(9600, SERIAL_8N1, DF_RX, DF_TX);
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_YELLOW, OUTPUT);
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  tft.initR(INITR_BLACKTAB);     // 顏色或邊緣不對時，改成 INITR_GREENTAB 或 INITR_REDTAB
  tft.setRotation(1);            // 橫向 160×128
  tft.fillScreen(C_BLACK);

  // 開機自我測試：三個燈與蜂鳴器依序動作（同時等 DFPlayer 開機）
  setOutputs(true, false, false, false);  delay(250);
  setOutputs(false, true, false, false);  delay(250);
  setOutputs(false, false, true, true);   delay(150);
  setOutputs(false, false, false, false);
  delay(800);
  dfVolume(22);
  drawScreen();
  Serial.println("I,ready");
}

void loop() {
  readSerial();
  unsigned long now = millis();
  if (level >= 0 && now - lastMsg > OFFLINE_MS) {
    level = -1;
  }

  switch (level) {
    case 0:   // 安全：綠燈恆亮
      setOutputs(true, false, false, false);
      break;
    case 1:   // 注意：黃燈每 0.25 秒切換，每秒短嗶一次
      setOutputs(false, (now / 250) % 2, false, (now % 1000) < 60);
      break;
    case 2: { // 危險：紅燈快閃，嗶聲 0.1 秒響、0.1 秒停
      bool on = (now / 100) % 2;
      setOutputs(false, false, on, on);
      break;
    }
    default:  // 離線：綠燈每 2 秒閃一下
      setOutputs((now % 2000) < 150, false, false, false);
  }
  drawScreen();
  delay(10);
}
