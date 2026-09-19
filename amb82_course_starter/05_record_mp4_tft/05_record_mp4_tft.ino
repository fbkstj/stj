/*
  第 5 節：MP4 錄影 ＋ TFT 顯示狀態
  ------------------------------------------------
  按一下板子上的按鈕（PUSH_BTN）開始錄影，錄滿設定的秒數自動存檔；
  TFT 螢幕顯示「READY / REC 12s / SAVED」與檔名，不必盯著序列埠。

  沒有 TFT 也可以用：把下面的 USE_TFT 改成 0，只看序列埠訊息。

  螢幕用開發板套件內建的 ILI9341 函式庫（AmebaILI9341），不必另外安裝程式庫。
  （注意：Adafruit 的 ST7735 函式庫在這塊板子上編譯不過，請用 ILI9341 模組。）

  接線（ILI9341 SPI 介面）：
    SCK → SPI_SCLK   SDI(MOSI) → SPI_MOSI   CS → SPI_SS
    DC → 4 號腳       RESET → 5 號腳         VCC → 3V3   GND → GND   LED → 3V3
  ※ 腳位以講師現場提供的接線圖為準，不同就改下面的 TFT_DC、TFT_RESET。

  錄好的 MP4 存在 SD 卡根目錄，檔名為 設定名稱+編號.mp4。
  官方範例：Multimedia → RecordMP4 → VideoOnly
*/
#include "StreamIO.h"
#include "VideoStream.h"
#include "MP4Recording.h"

// ====== 可以修改的設定 ======
#define USE_TFT        1        // 沒有接 TFT 就改成 0
#define CHANNEL        0        // 0：1920x1080　1：1280x720
#define RECORD_SECONDS 15       // 一段影片錄幾秒
#define FILE_PREFIX    "class"  // 檔名開頭
#define TFT_DC         4        // 螢幕的 DC 腳接到板子第 4 腳
#define TFT_RESET      5        // 螢幕的 RESET 腳接到板子第 5 腳
// ============================

#if USE_TFT
#include "SPI.h"
#include "AmebaILI9341.h"
AmebaILI9341 tft = AmebaILI9341(SPI_SS, TFT_DC, TFT_RESET);
#endif

VideoSetting config(CHANNEL);
MP4Recording mp4;
StreamIO videoStreamer(1, 1);

bool recording = false;
unsigned long recordStart = 0;
int fileIndex = 0;
int lastShown = -1;

void setup()
{
    Serial.begin(115200);
    pinMode(LED_B, OUTPUT);
    pinMode(PUSH_BTN, INPUT);
    Serial.println("\n[AMB82] 第 5 節：MP4 錄影");

#if USE_TFT
    SPI.setDefaultFrequency(20000000);
    tft.begin();
    tft.setRotation(1);
    showStatus("READY", "press button", ILI9341_WHITE);
#endif

    Camera.configVideoChannel(CHANNEL, config);
    Camera.videoInit();

    mp4.configVideo(config);
    mp4.setRecordingDuration(RECORD_SECONDS);
    mp4.setRecordingFileCount(1);
    mp4.setRecordingDataType(STORAGE_VIDEO);    // 只錄影像；要收音改成 STORAGE_ALL

    videoStreamer.registerInput(Camera.getStream(CHANNEL));
    videoStreamer.registerOutput(mp4);
    if (videoStreamer.begin() != 0) {
        Serial.println("[錯誤] StreamIO 連接失敗");
    }
    Camera.channelBegin(CHANNEL);

    Serial.println("按下板子上的按鈕開始錄影");
}

void loop()
{
    // 按鈕按下（低電位）就開始錄影
    if (!recording && digitalRead(PUSH_BTN) == LOW) {
        startRecording();
        delay(300);    // 防彈跳
    }

    if (recording) {
        int elapsed = (millis() - recordStart) / 1000;
        if (elapsed != lastShown) {
            lastShown = elapsed;
            Serial.print("錄影中… ");
            Serial.print(elapsed);
            Serial.print(" / ");
            Serial.println(RECORD_SECONDS);
#if USE_TFT
            char line[24];
            snprintf(line, sizeof(line), "REC %d / %ds", elapsed, RECORD_SECONDS);
            showStatus(line, currentName().c_str(), ILI9341_RED);
#endif
        }
        if (elapsed >= RECORD_SECONDS + 1) {    // 多等 1 秒讓檔案寫完
            recording = false;
            digitalWrite(LED_B, LOW);
            Serial.println("[OK] 已存檔：" + currentName() + ".mp4");
#if USE_TFT
            showStatus("SAVED", currentName().c_str(), ILI9341_GREEN);
#endif
        }
    }
}

void startRecording()
{
    fileIndex++;
    mp4.setRecordingFileName(currentName());
    mp4.begin();
    recording = true;
    recordStart = millis();
    lastShown = -1;
    digitalWrite(LED_B, HIGH);
    Serial.println("開始錄影：" + currentName() + ".mp4");
}

String currentName()
{
    return String(FILE_PREFIX) + String(fileIndex);
}

#if USE_TFT
void showStatus(const char *title, const char *sub, uint16_t color)
{
    tft.fillScreen(ILI9341_BLACK);
    tft.setForeground(color);
    tft.setBackground(ILI9341_BLACK);
    tft.setFontSize(4);
    tft.setCursor(10, 30);
    tft.println(title);
    tft.setForeground(ILI9341_WHITE);
    tft.setFontSize(2);
    tft.setCursor(10, 100);
    tft.println(sub);
    tft.setCursor(10, 130);
    tft.println("AMB82-Mini");
}
#endif
