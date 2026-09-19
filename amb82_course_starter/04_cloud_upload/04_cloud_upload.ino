/*
  第 4 節：拍照上傳 Google 雲端硬碟＋試算表（可再推播到 LINE）
  ------------------------------------------------
  流程：板子拍照 → 轉成 Base64 → POST 給 Google Apps Script 網頁應用程式
        → Apps Script 存檔到雲端硬碟、在試算表加一列、（選用）推播 LINE

  上傳前要先完成 apps_script/Code.gs 的部署，取得像這樣的網址：
    https://script.google.com/macros/s/AKfycbx.....abcd/exec
  把其中「/macros/s/……/exec」這一段填進下面的 scriptPath。

  注意：Apps Script 網址等於一個「誰知道誰就能上傳」的入口，不要貼到公開的地方。
  官方範例：Http → HttpUploadImageGoogleDrv
*/
#include <WiFi.h>
#include <WiFiSSLClient.h>
#include <WiFiUdp.h>
#include <NTPClient.h>
#include "VideoStream.h"
#include "Base64.h"

// ====== 可以修改的設定 ======
char ssid[] = "你的WiFi名稱";
char pass[] = "你的WiFi密碼";

String scriptPath = "/macros/s/請貼上你的部署ID/exec";    // Apps Script 網址的後半段
String folderName = "AMB82-Mini";                        // 雲端硬碟資料夾名稱
String deviceName = "座號01";                            // 會寫進試算表，方便分辨是哪一台

#define CHANNEL       0
#define UPLOAD_PERIOD 60000    // 每隔幾毫秒上傳一張（60000＝1 分鐘）
#define MAX_UPLOAD    5        // 上傳幾張後停止（設 0 代表一直上傳）
// ============================

VideoSetting config(768, 768, CAM_FPS, VIDEO_JPEG, 1);    // 768x768，上傳比較快
const char *host = "script.google.com";

WiFiSSLClient client;
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP);

uint32_t img_addr = 0;
uint32_t img_len = 0;
int uploadCount = 0;

void setup()
{
    Serial.begin(115200);
    pinMode(LED_B, OUTPUT);
    Serial.println("\n[AMB82] 第 4 節：上傳 Google 雲端硬碟");

    WiFi.begin(ssid, pass);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\n[OK] WiFi 已連線");

    config.setRotation(0);
    Camera.configVideoChannel(CHANNEL, config);
    Camera.videoInit();
    Camera.channelBegin(CHANNEL);

    timeClient.begin();
    timeClient.update();
    delay(3000);    // 等鏡頭曝光穩定
}

void loop()
{
    if (MAX_UPLOAD > 0 && uploadCount >= MAX_UPLOAD) {
        delay(5000);
        return;
    }
    uploadCount++;
    Camera.getImage(CHANNEL, &img_addr, &img_len);
    Serial.print("第 ");
    Serial.print(uploadCount);
    Serial.print(" 張，大小 ");
    Serial.print(img_len / 1024);
    Serial.println(" KB，開始上傳…");
    uploadToDrive();
    delay(UPLOAD_PERIOD);
}

void uploadToDrive()
{
    digitalWrite(LED_B, HIGH);

    // 影像轉 Base64，再做網址編碼（一次 3 個位元組）
    char *input = (char *)img_addr;
    char output[base64_enc_len(3)];
    String imageFile = "data:image/jpeg;base32,";
    for (uint32_t i = 0; i < img_len; i++) {
        base64_encode(output, (input++), 3);
        if (i % 3 == 0) {
            imageFile += urlencode(String(output));
        }
    }

    String filename = deviceName + "_" + getTimestamp() + ".jpg";
    String data = "&myFoldername=" + urlencode(folderName) + "&myDevice=" + urlencode(deviceName) + "&myFilename=" + urlencode(filename) + "&myFile=";

    Serial.println("連線 " + String(host));
    if (!client.connect(host, 443)) {
        Serial.println("[錯誤] 連不上 Google，檢查網路或防火牆");
        digitalWrite(LED_B, LOW);
        return;
    }

    client.println("POST " + scriptPath + " HTTP/1.1");
    client.println("Host: " + String(host));
    client.println("Content-Length: " + String(data.length() + imageFile.length()));
    client.println("Content-Type: application/x-www-form-urlencoded");
    client.println("Connection: keep-alive");
    client.println();
    client.print(data);
    for (unsigned int i = 0; i < imageFile.length(); i += 1000) {
        client.print(imageFile.substring(i, i + 1000));
    }

    // 讀回應（Apps Script 會先回 302 轉址，再回 JSON，所以看到 302 是正常的）
    String getAll = "", getBody = "";
    bool inBody = false;
    unsigned long startTime = millis();
    while (millis() - startTime < 15000) {
        delay(100);
        while (client.available()) {
            char c = client.read();
            if (inBody) {
                getBody += String(c);
            }
            if (c == '\n') {
                if (getAll.length() == 0) {
                    inBody = true;
                }
                getAll = "";
            } else if (c != '\r') {
                getAll += String(c);
            }
            startTime = millis();
        }
        if (getBody.length() > 0) {
            break;
        }
    }
    client.stop();
    digitalWrite(LED_B, LOW);

    Serial.println("Apps Script 回應：" + getBody);
    if (getBody.indexOf("\"ok\":true") >= 0) {
        Serial.println("[OK] 上傳成功，去雲端硬碟與試算表看看");
    } else {
        Serial.println("[注意] 沒有看到成功訊息：多半是部署權限沒設成「任何人」，或網址貼錯");
    }
}

String getTimestamp()
{
    char buf[32];
    timeClient.update();
    sprintf(buf, "%04d%02d%02d_%02d%02d%02d", timeClient.getYear(), timeClient.getMonth(), timeClient.getMonthDay(), timeClient.getHours(), timeClient.getMinutes(), timeClient.getSeconds());
    return String(buf);
}

String urlencode(String str)
{
    const char *msg = str.c_str();
    const char *hex = "0123456789ABCDEF";
    String encodedMsg = "";
    while (*msg != '\0') {
        if (('a' <= *msg && *msg <= 'z') || ('A' <= *msg && *msg <= 'Z') || ('0' <= *msg && *msg <= '9') || *msg == '-' || *msg == '_' || *msg == '.' || *msg == '~') {
            encodedMsg += *msg;
        } else {
            encodedMsg += '%';
            encodedMsg += hex[(unsigned char)*msg >> 4];
            encodedMsg += hex[*msg & 0xf];
        }
        msg++;
    }
    return encodedMsg;
}
