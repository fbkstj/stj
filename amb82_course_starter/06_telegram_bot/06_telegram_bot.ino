/*
  第 6 節：Telegram Bot 遠端控制
  ------------------------------------------------
  在手機的 Telegram 傳指令給自己的 Bot，板子收到就動作：
    /photo    拍一張照片傳回來
    /led on   開燈　　/led off　關燈
    /status   回報執行時間、WiFi 訊號、拍過幾張

  準備（上課前先做好）：
    1. Telegram 搜尋 @BotFather → /newbot → 取得 Bot Token
    2. 先傳一句話給自己的 Bot，再用電腦執行 tools/telegram_check.py 取得 chatID
    3. 把 Token 與 chatID 填進下面的設定

  安全提醒：
    - Token 等於 Bot 的密碼，不要上傳到 GitHub，也不要貼在報告或簡報裡（要截圖請遮起來）。
    - 程式只接受 ALLOWED_CHAT_ID 的指令，別人找到你的 Bot 也無法操控。

  官方範例：Http → HttpUploadImageTelegram
*/
#include <WiFi.h>
#include <WiFiSSLClient.h>
#include "VideoStream.h"

// ====== 可以修改的設定 ======
char ssid[] = "你的WiFi名稱";
char pass[] = "你的WiFi密碼";

String botToken = "123456789:請貼上你的BotToken";
String ALLOWED_CHAT_ID = "123456789";    // 只接受這個人的指令

#define CHANNEL      0
#define POLL_PERIOD  2000    // 每隔幾毫秒去問一次有沒有新訊息
// ============================

VideoSetting config(768, 768, CAM_FPS, VIDEO_JPEG, 1);
const char *host = "api.telegram.org";

WiFiSSLClient pollClient;
WiFiSSLClient sendClient;

uint32_t img_addr = 0;
uint32_t img_len = 0;
long lastUpdateId = 0;
unsigned long lastPoll = 0;
int photoCount = 0;
bool ledOn = false;

void setup()
{
    Serial.begin(115200);
    pinMode(LED_B, OUTPUT);
    Serial.println("\n[AMB82] 第 6 節：Telegram Bot");

    WiFi.begin(ssid, pass);
    while (WiFi.status() != WL_CONNECTED) {
        delay(400);
        Serial.print(".");
    }
    Serial.println("\n[OK] WiFi 已連線");

    config.setRotation(0);
    Camera.configVideoChannel(CHANNEL, config);
    Camera.videoInit();
    Camera.channelBegin(CHANNEL);
    delay(2000);

    sendMessage("AMB82-Mini 上線了，可以傳 /photo、/led on、/led off、/status");
    Serial.println("在 Telegram 傳 /photo 試試看");
}

void loop()
{
    if (millis() - lastPoll > POLL_PERIOD) {
        lastPoll = millis();
        checkMessages();
    }
}

/* ---------- 收訊息 ---------- */
void checkMessages()
{
    if (!pollClient.connect(host, 443)) {
        Serial.println("[錯誤] 連不上 Telegram（檢查網路或防火牆）");
        return;
    }
    String path = "/bot" + botToken + "/getUpdates?timeout=1&limit=1&offset=" + String(lastUpdateId + 1);
    pollClient.println("GET " + path + " HTTP/1.1");
    pollClient.println("Host: " + String(host));
    pollClient.println("Connection: close");
    pollClient.println();

    String body = readBody(pollClient, 8000);
    pollClient.stop();
    if (body.length() == 0) {
        return;
    }

    long updateId = valueOfLong(body, "\"update_id\":");
    if (updateId <= lastUpdateId) {
        return;
    }
    lastUpdateId = updateId;

    String chatId = valueOfString(body, "\"chat\":{\"id\":");
    String text = valueOfString(body, "\"text\":\"");
    text.toLowerCase();
    Serial.println("收到指令：" + text + "（來自 " + chatId + "）");

    if (chatId != ALLOWED_CHAT_ID) {
        Serial.println("[略過] 不是允許的使用者");
        return;
    }
    handleCommand(text);
}

void handleCommand(String text)
{
    if (text.startsWith("/photo")) {
        sendPhoto();
    } else if (text.startsWith("/led on")) {
        ledOn = true;
        digitalWrite(LED_B, HIGH);
        sendMessage("LED 已開啟");
    } else if (text.startsWith("/led off")) {
        ledOn = false;
        digitalWrite(LED_B, LOW);
        sendMessage("LED 已關閉");
    } else if (text.startsWith("/status")) {
        String msg = "執行時間：" + String(millis() / 1000) + " 秒\n";
        msg += "WiFi 訊號：" + String(WiFi.RSSI()) + " dBm\n";
        msg += "已拍照：" + String(photoCount) + " 張\n";
        msg += "LED：" + String(ledOn ? "開" : "關");
        sendMessage(msg);
    } else {
        sendMessage("看不懂這個指令，可以用：/photo、/led on、/led off、/status");
    }
}

/* ---------- 送訊息 ---------- */
void sendMessage(String text)
{
    if (!sendClient.connect(host, 443)) {
        Serial.println("[錯誤] 送訊息失敗");
        return;
    }
    String body = "chat_id=" + ALLOWED_CHAT_ID + "&text=" + urlencode(text);
    sendClient.println("POST /bot" + botToken + "/sendMessage HTTP/1.1");
    sendClient.println("Host: " + String(host));
    sendClient.println("Content-Type: application/x-www-form-urlencoded");
    sendClient.println("Content-Length: " + String(body.length()));
    sendClient.println("Connection: close");
    sendClient.println();
    sendClient.print(body);
    readBody(sendClient, 5000);
    sendClient.stop();
}

void sendPhoto()
{
    Camera.getImage(CHANNEL, &img_addr, &img_len);
    photoCount++;
    Serial.print("拍照上傳，大小 ");
    Serial.print(img_len / 1024);
    Serial.println(" KB");

    String boundary = "----AMB82Boundary";
    String head = "--" + boundary + "\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n" + ALLOWED_CHAT_ID + "\r\n";
    head += "--" + boundary + "\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n第 " + String(photoCount) + " 張\r\n";
    head += "--" + boundary + "\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"amb82.jpg\"\r\n";
    head += "Content-Type: image/jpeg\r\n\r\n";
    String tail = "\r\n--" + boundary + "--\r\n";

    if (!sendClient.connect(host, 443)) {
        Serial.println("[錯誤] 連不上 Telegram");
        return;
    }
    sendClient.println("POST /bot" + botToken + "/sendPhoto HTTP/1.1");
    sendClient.println("Host: " + String(host));
    sendClient.println("Content-Type: multipart/form-data; boundary=" + boundary);
    sendClient.println("Content-Length: " + String(head.length() + img_len + tail.length()));
    sendClient.println("Connection: close");
    sendClient.println();
    sendClient.print(head);
    // 影像分段送出，避免一次送太多
    uint8_t *buf = (uint8_t *)img_addr;
    for (uint32_t i = 0; i < img_len; i += 1024) {
        uint32_t n = (img_len - i) < 1024 ? (img_len - i) : 1024;
        sendClient.write(buf + i, n);
    }
    sendClient.print(tail);

    String body = readBody(sendClient, 15000);
    sendClient.stop();
    Serial.println(body.indexOf("\"ok\":true") >= 0 ? "[OK] 照片已送出" : "[注意] 送出失敗：" + body);
}

/* ---------- 小工具 ---------- */
String readBody(WiFiSSLClient &client, unsigned long timeout)
{
    String all = "", body = "";
    bool inBody = false;
    unsigned long start = millis();
    while (millis() - start < timeout) {
        while (client.available()) {
            char c = client.read();
            if (inBody) {
                body += c;
            } else if (c == '\n') {
                if (all.length() == 0) {
                    inBody = true;
                }
                all = "";
            } else if (c != '\r') {
                all += c;
            }
            start = millis();
        }
        if (body.length() > 0 && !client.connected()) {
            break;
        }
        delay(20);
    }
    return body;
}

long valueOfLong(String json, String key)
{
    int i = json.indexOf(key);
    if (i < 0) {
        return 0;
    }
    return json.substring(i + key.length()).toInt();
}

String valueOfString(String json, String key)
{
    int i = json.indexOf(key);
    if (i < 0) {
        return "";
    }
    i += key.length();
    int j = i;
    while (j < (int)json.length() && json[j] != '"' && json[j] != ',' && json[j] != '}') {
        j++;
    }
    return json.substring(i, j);
}

String urlencode(String str)
{
    const char *msg = str.c_str();
    const char *hex = "0123456789ABCDEF";
    String out = "";
    while (*msg != '\0') {
        if (('a' <= *msg && *msg <= 'z') || ('A' <= *msg && *msg <= 'Z') || ('0' <= *msg && *msg <= '9') || *msg == '-' || *msg == '_' || *msg == '.' || *msg == '~') {
            out += *msg;
        } else {
            out += '%';
            out += hex[(unsigned char)*msg >> 4];
            out += hex[*msg & 0xf];
        }
        msg++;
    }
    return out;
}
