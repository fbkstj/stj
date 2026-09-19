/*
  第 2 節：RTSP 影音串流
  ------------------------------------------------
  板子連上 WiFi 後，把鏡頭畫面用 RTSP 送出去，電腦用 VLC 就能看。
  序列埠會印出網址，例如 rtsp://192.168.1.50:554

  VLC 播放：媒體 → 開啟網路串流 → 貼上網址
  延遲太高時：VLC → 工具 → 偏好設定 → 輸入/編碼器 → 網路快取改成 200 毫秒

  三個名詞（報告會用到）：
    RTSP：控制播放（play / pause / teardown），像遙控器
    RTP ：真正把影音封包送出去的協定
    TCP/UDP：底層傳輸。UDP 快但會掉封包（畫面破格），TCP 穩定但延遲較高
             VLC 可在「網路串流」選項勾選 RTP over RTSP (TCP) 比較兩者差別

  官方範例：Multimedia → StreamRTSP → VideoOnly
*/
#include "WiFi.h"
#include "StreamIO.h"
#include "VideoStream.h"
#include "RTSP.h"

// ====== 可以修改的設定 ======
char ssid[] = "你的WiFi名稱";
char pass[] = "你的WiFi密碼";

#define CHANNEL 0    // 0：1920x1080 H264　1：1280x720 H264　2：1280x720 MJPEG
#define BITRATE (2 * 1024 * 1024)    // 2 Mbps；教室很多人同時串流時可以改成 1 Mbps
// ============================

VideoSetting config(CHANNEL);
RTSP rtsp;
StreamIO videoStreamer(1, 1);    // 1 個影像來源 → 1 個 RTSP 輸出
int status = WL_IDLE_STATUS;

void setup()
{
    Serial.begin(115200);
    pinMode(LED_B, OUTPUT);
    Serial.println("\n[AMB82] 第 2 節：RTSP 串流");

    while (status != WL_CONNECTED) {
        Serial.print("連線到 WiFi：");
        Serial.println(ssid);
        status = WiFi.begin(ssid, pass);
        delay(2000);
    }
    Serial.println("[OK] WiFi 已連線");

    // 鏡頭設定（解析度、格式）
    config.setBitrate(BITRATE);
    Camera.configVideoChannel(CHANNEL, config);
    Camera.videoInit();

    // RTSP 要用和鏡頭一樣的設定
    rtsp.configVideo(config);
    rtsp.begin();

    // 把鏡頭的資料流接到 RTSP
    videoStreamer.registerInput(Camera.getStream(CHANNEL));
    videoStreamer.registerOutput(rtsp);
    if (videoStreamer.begin() != 0) {
        Serial.println("[錯誤] StreamIO 連接失敗");
    }
    Camera.channelBegin(CHANNEL);

    delay(1000);
    printInfo();
    digitalWrite(LED_B, HIGH);    // 燈亮代表串流中
}

void loop()
{
    delay(1000);
}

void printInfo(void)
{
    Serial.println("------------------------------");
    Camera.printInfo();
    IPAddress ip = WiFi.localIP();
    Serial.println("- 用 VLC 打開這個網址 -");
    rtsp.printInfo(ip.get_address());
    Serial.println("------------------------------");
}
