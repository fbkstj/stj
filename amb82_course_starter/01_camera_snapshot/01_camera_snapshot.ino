/*
  第 1 節：認識 AMB82-Mini —— 拍照存到 SD 卡
  ------------------------------------------------
  這支程式做三件事：
    1. 啟動鏡頭（JPEG 格式）
    2. 每隔幾秒拍一張，存到 SD 卡，檔名 img001.jpg、img002.jpg…
    3. 拍照時藍色 LED 閃一下，序列埠印出檔名與檔案大小

  準備：microSD 卡（FAT32 格式）插好再開機。
  序列埠監控視窗請設 115200。

  官方範例：Multimedia → CaptureJPEG → SDCardSaveJPEG
*/
#include "VideoStream.h"
#include "AmebaFatFS.h"

// ====== 可以修改的設定 ======
#define CHANNEL       0        // 鏡頭通道
#define SHOT_INTERVAL 5000     // 每隔幾毫秒拍一張
#define MAX_SHOTS     10       // 總共拍幾張（設 0 代表一直拍）
// ============================

VideoSetting config(VIDEO_FHD, CAM_FPS, VIDEO_JPEG, 1);    // 1920x1080 JPEG
AmebaFatFS fs;

uint32_t img_addr = 0;
uint32_t img_len = 0;
int shotCount = 0;

void setup()
{
    Serial.begin(115200);
    pinMode(LED_B, OUTPUT);

    Serial.println("\n[AMB82] 第 1 節：拍照存 SD 卡");

    // 啟動鏡頭
    Camera.configVideoChannel(CHANNEL, config);
    Camera.videoInit();
    Camera.channelBegin(CHANNEL);
    Camera.printInfo();

    // 掛載 SD 卡；失敗時多半是沒插卡或不是 FAT32
    if (!fs.begin()) {
        Serial.println("[錯誤] 讀不到 SD 卡：請確認已插卡，且格式為 FAT32");
        while (1) {
            digitalWrite(LED_B, HIGH);
            delay(150);
            digitalWrite(LED_B, LOW);
            delay(150);
        }
    }
    Serial.println("[OK] SD 卡已掛載");
    delay(2000);    // 等鏡頭自動曝光穩定，第一張才不會太暗
}

void loop()
{
    if (MAX_SHOTS > 0 && shotCount >= MAX_SHOTS) {
        Serial.println("拍攝完成，可以把 SD 卡拿到電腦看照片");
        delay(5000);
        return;
    }

    shotCount++;
    char filename[32];
    snprintf(filename, sizeof(filename), "img%03d.jpg", shotCount);

    Camera.getImage(CHANNEL, &img_addr, &img_len);    // 取得最新一張 JPEG 的位置與長度

    File file = fs.open(String(fs.getRootPath()) + String(filename));
    file.write((uint8_t *)img_addr, img_len);
    file.close();

    digitalWrite(LED_B, HIGH);
    delay(80);
    digitalWrite(LED_B, LOW);

    Serial.print("第 ");
    Serial.print(shotCount);
    Serial.print(" 張：");
    Serial.print(filename);
    Serial.print("　大小 ");
    Serial.print(img_len / 1024);
    Serial.println(" KB");

    delay(SHOT_INTERVAL);
}
