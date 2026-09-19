// AI 守望：現場警示盒（ESP32）——三色燈、蜂鳴器、TFT 文字、保全取消鈕
//
// 電腦傳來的指令（每行一個，以換行結尾）：
//   S<狀態><事件><秒數>   例：S2W4
//     狀態：0 監控中／1 注意／2 警報倒數／3 已通報／4 已取消
//     事件：W 持械／R 奔逃／F 倒地／C 聚集／N 無
//     秒數：警報倒數剩幾秒（0～9）
// 傳給電腦的訊息：
//   I,ready   開機完成
//   K         保全按下取消鈕（電腦會把倒數中的警報標記為誤報）
// 電腦每 0.2 秒送一次狀態；超過 OFFLINE_MS 沒收到 → 未連線（綠燈慢閃、TFT 顯示未連線）
//
// 開發板選「ESP32 Dev Module」
// 需要的程式庫（Arduino IDE 程式庫管理員）：Adafruit ST7735 and ST7789 Library、Adafruit GFX Library
//
// 接線：
//   綠／黃／紅 LED：GPIO25／26／27（各串 220Ω 到 GND）；主動式蜂鳴器模組 I/O：GPIO14
//   取消按鈕：一腳接 GPIO4，另一腳接 GND（使用內建上拉電阻，不必另外接電阻）
//   ST7735 1.8 吋 TFT：SCK→GPIO18、SDA(MOSI)→GPIO23、CS→GPIO5、A0(DC)→GPIO21、RST→GPIO22、
//                      VCC→3V3、GND→GND、LED(背光)→3V3

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>
#include "tft_labels.h"

const int PIN_GREEN  = 25;
const int PIN_YELLOW = 26;
const int PIN_RED    = 27;
const int PIN_BUZZER = 14;   // 主動式蜂鳴器模組，HIGH＝響
const int PIN_BUTTON = 4;    // 按下＝LOW

const int TFT_CS  = 5;
const int TFT_DC  = 21;
const int TFT_RST = 22;

const unsigned long OFFLINE_MS = 1500;
const unsigned long DEBOUNCE_MS = 50;
const unsigned long CLICK_BEEP_MS = 60;

// 顏色（RGB565）
const uint16_t C_BLACK  = 0x0000;
const uint16_t C_WHITE  = 0xFFFF;
const uint16_t C_GREEN  = 0x0400;
const uint16_t C_YELLOW = 0xFFE0;
const uint16_t C_RED    = 0xC000;   // 色塊（配白字）
const uint16_t C_RED_TX = 0xF800;   // 黑底上的紅字
const uint16_t C_BLUE   = 0x2A6F;   // 已取消
const uint16_t C_GRAY   = 0x4208;

Adafruit_ST7735 tft(TFT_CS, TFT_DC, TFT_RST);

int state = -1;              // -1＝未連線
char kind = 'N';
int seconds = 0;
unsigned long lastMsg = 0;
String line;

// 按鈕
bool lastRaw = HIGH;
bool stable = HIGH;
unsigned long rawChanged = 0;
unsigned long clickBeepUntil = 0;

// 畫面上目前顯示的內容（有變才重畫，避免閃爍）
int shownState = -2;
char shownKind = '?';
int shownSeconds = -1;

// ---------- TFT ----------
void drawLabel(const Label &lb, int cx, int top, int bandH, uint16_t fg, uint16_t bg) {
  int x = cx - lb.w / 2;
  int y = top + (bandH - lb.h) / 2;
  tft.drawBitmap(x, y, lb.data, lb.w, lb.h, fg, bg);
}

const Label &kindLabel(char k) {
  switch (k) {
    case 'W': return LBL_KW;
    case 'R': return LBL_KR;
    case 'F': return LBL_KF;
    case 'C': return LBL_KC;
    default:  return LBL_KN;
  }
}

void drawScreen() {
  int w = tft.width();   // 160
  bool stateChanged = state != shownState;

  // 上方色塊：狀態
  if (stateChanged) {
    uint16_t bg = C_GRAY, fg = C_WHITE;
    const Label *lb = &LBL_OFF;
    switch (state) {
      case 0: bg = C_GREEN;  lb = &LBL_S0; break;
      case 1: bg = C_YELLOW; fg = C_BLACK; lb = &LBL_S1; break;
      case 2: bg = C_RED;    lb = &LBL_S2; break;
      case 3: bg = C_RED;    lb = &LBL_S3; break;
      case 4: bg = C_BLUE;   lb = &LBL_S4; break;
    }
    tft.fillRect(0, 0, w, 38, bg);
    drawLabel(*lb, w / 2, 0, 38, fg, bg);
  }

  // 中間：事件種類
  char k = (state > 0) ? kind : 'N';
  if (stateChanged || k != shownKind) {
    tft.fillRect(0, 40, w, 34, C_BLACK);
    uint16_t fg = C_WHITE;
    if (state == 1) fg = C_YELLOW;
    if (state == 2 || state == 3) fg = C_RED_TX;
    if (state >= 0) drawLabel(kindLabel(k), w / 2, 40, 34, fg, C_BLACK);
    shownKind = k;
  }

  // 下方：依狀態顯示說明；警報倒數時顯示大數字
  if (stateChanged) {
    tft.fillRect(0, 76, w, 52, C_BLACK);
    switch (state) {
      case -1: drawLabel(LBL_CHECK, w / 2, 76, 52, C_WHITE, C_BLACK); break;
      case 1:  drawLabel(LBL_WATCH, w / 2, 76, 52, C_WHITE, C_BLACK); break;
      case 2:
        drawLabel(LBL_AFTER, 104, 78, 30, C_WHITE, C_BLACK);
        drawLabel(LBL_PRESS, w / 2, 108, 20, C_YELLOW, C_BLACK);
        break;
      case 3:  drawLabel(LBL_SENT, w / 2, 76, 52, C_WHITE, C_BLACK); break;
      case 4:  drawLabel(LBL_FALSE, w / 2, 76, 52, C_WHITE, C_BLACK); break;
    }
    shownSeconds = -1;
  }
  if (state == 2 && seconds != shownSeconds) {
    tft.setTextSize(4);                       // 24×32 像素的數字
    tft.setTextColor(C_WHITE, C_BLACK);       // 帶背景色，覆蓋舊數字不閃爍
    tft.setCursor(22, 78);
    tft.print(seconds);
    shownSeconds = seconds;
  }
  shownState = state;
}

// ---------- 燈號與蜂鳴器 ----------
void setOutputs(bool g, bool y, bool r, bool buzz) {
  digitalWrite(PIN_GREEN, g);
  digitalWrite(PIN_YELLOW, y);
  digitalWrite(PIN_RED, r);
  digitalWrite(PIN_BUZZER, buzz || millis() < clickBeepUntil);
}

// ---------- 取消按鈕 ----------
void readButton() {
  unsigned long now = millis();
  bool raw = digitalRead(PIN_BUTTON);
  if (raw != lastRaw) {
    lastRaw = raw;
    rawChanged = now;
  }
  if (now - rawChanged > DEBOUNCE_MS && raw != stable) {
    stable = raw;
    if (stable == LOW) {            // 剛按下
      Serial.println("K");
      clickBeepUntil = now + CLICK_BEEP_MS;
    }
  }
}

// ---------- 指令 ----------
void handleLine(const String &s) {
  if (s.length() == 4 && s[0] == 'S' && s[1] >= '0' && s[1] <= '4' && isDigit(s[3])) {
    state = s[1] - '0';
    kind = s[2];
    seconds = s[3] - '0';
    lastMsg = millis();
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
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_GREEN, OUTPUT);
  pinMode(PIN_YELLOW, OUTPUT);
  pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_BUTTON, INPUT_PULLUP);

  tft.initR(INITR_BLACKTAB);     // 顏色或邊緣不對時，改成 INITR_GREENTAB 或 INITR_REDTAB
  tft.setRotation(1);            // 橫向 160×128
  tft.fillScreen(C_BLACK);

  // 開機自我測試：三個燈與蜂鳴器依序動作
  setOutputs(true, false, false, false);  delay(250);
  setOutputs(false, true, false, false);  delay(250);
  setOutputs(false, false, true, true);   delay(150);
  setOutputs(false, false, false, false);
  drawScreen();
  Serial.println("I,ready");
}

void loop() {
  readSerial();
  readButton();
  unsigned long now = millis();
  if (state >= 0 && now - lastMsg > OFFLINE_MS) {
    state = -1;
  }

  switch (state) {
    case 0:   // 監控中：綠燈恆亮
      setOutputs(true, false, false, false);
      break;
    case 1:   // 注意：黃燈恆亮，不響（中、低風險事件已直接通報或記錄）
      setOutputs(false, true, false, false);
      break;
    case 2: { // 警報倒數：紅燈快閃，蜂鳴器 0.1 秒響、0.1 秒停
      bool on = (now / 100) % 2;
      setOutputs(false, false, on, on);
      break;
    }
    case 3:   // 已通報：紅燈恆亮，每 2 秒短嗶提醒現場
      setOutputs(false, false, true, (now % 2000) < 80);
      break;
    case 4:   // 已取消：綠燈快閃
      setOutputs((now / 250) % 2, false, false, false);
      break;
    default:  // 未連線：綠燈每 2 秒閃一下
      setOutputs((now % 2000) < 150, false, false, false);
  }
  drawScreen();
  delay(10);
}
