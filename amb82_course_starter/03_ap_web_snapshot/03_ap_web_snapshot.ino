/*
  第 3 節：AP 模式 ＋ 網頁看即時影像
  ------------------------------------------------
  板子自己變成一台 WiFi 基地台（AP），手機、筆電連上它，
  打開 http://192.168.1.1 就能看到即時畫面，還能開關板子上的 LED。
  現場沒有 WiFi、或學校網路擋東擋西時，這是最可靠的展示方式。

  網頁提供三個網址：
    /            首頁（每 0.7 秒自動換一張照片）
    /photo       回傳一張 JPEG
    /led?on=1    開燈；/led?on=0 關燈

  注意：AP 模式下板子沒有連到網際網路，Google、Telegram 這些功能要改用第 4、6 節的連線模式。
  官方範例：WiFi → CreateWiFiAP、Multimedia → CaptureJPEG → HTTPDisplayJPEG
*/
#include <WiFi.h>
#include "VideoStream.h"

// ====== 可以修改的設定 ======
char ap_ssid[] = "AMB82-Class";     // 基地台名稱（同一間教室不要重複，建議加座號）
char ap_pass[] = "12345678";        // 至少 8 碼
char ap_channel[] = "6";            // 1～13
#define CHANNEL 0
// ============================

VideoSetting config(VIDEO_HD, CAM_FPS, VIDEO_JPEG, 1);    // 1280x720 JPEG，手機看夠用又比較快
WiFiServer server(80);

uint32_t img_addr = 0;
uint32_t img_len = 0;
bool ledOn = false;

void setup()
{
    Serial.begin(115200);
    pinMode(LED_B, OUTPUT);
    Serial.println("\n[AMB82] 第 3 節：AP 模式網頁");

    int status = WL_IDLE_STATUS;
    while (status != WL_CONNECTED) {
        Serial.print("建立基地台：");
        Serial.println(ap_ssid);
        status = WiFi.apbegin(ap_ssid, ap_pass, ap_channel, 0);    // 0＝不隱藏 SSID
        delay(1000);
    }

    Camera.configVideoChannel(CHANNEL, config);
    Camera.videoInit();
    Camera.channelBegin(CHANNEL);
    server.begin();

    IPAddress ip = WiFi.localIP();
    Serial.print("[OK] 手機連上 ");
    Serial.print(ap_ssid);
    Serial.print(" 之後，打開 http://");
    Serial.println(ip);
}

void loop()
{
    WiFiClient client = server.available();
    if (!client) {
        return;
    }

    // 讀出第一行（例如 GET /photo HTTP/1.1），其餘標頭讀完丟掉
    String requestLine = "";
    String currentLine = "";
    unsigned long start = millis();
    while (client.connected() && (millis() - start < 3000)) {
        if (!client.available()) {
            continue;
        }
        char c = client.read();
        if (c == '\n') {
            if (requestLine.length() == 0) {
                requestLine = currentLine;
            }
            if (currentLine.length() == 0) {
                break;    // 空行＝標頭結束
            }
            currentLine = "";
        } else if (c != '\r') {
            currentLine += c;
        }
    }

    if (requestLine.indexOf("GET /photo") >= 0) {
        sendPhoto(client);
    } else if (requestLine.indexOf("GET /led") >= 0) {
        ledOn = (requestLine.indexOf("on=1") >= 0);
        digitalWrite(LED_B, ledOn ? HIGH : LOW);
        sendText(client, ledOn ? "LED ON" : "LED OFF");
    } else {
        sendPage(client);
    }

    delay(5);
    client.stop();
}

void sendPhoto(WiFiClient &client)
{
    Camera.getImage(CHANNEL, &img_addr, &img_len);
    char header[160];
    int n = snprintf(header, sizeof(header),
                     "HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\nContent-Length: %lu\r\n"
                     "Cache-Control: no-store\r\nConnection: close\r\n\r\n",
                     img_len);
    client.write((uint8_t *)header, n);
    client.write((uint8_t *)img_addr, img_len);
}

void sendText(WiFiClient &client, const char *text)
{
    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: text/plain; charset=utf-8");
    client.println("Connection: close");
    client.println();
    client.println(text);
}

void sendPage(WiFiClient &client)
{
    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: text/html; charset=utf-8");
    client.println("Connection: close");
    client.println();
    client.println("<!DOCTYPE html><html lang=\"zh-Hant-TW\"><head><meta charset=\"utf-8\">");
    client.println("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">");
    client.println("<title>AMB82-Mini 即時影像</title>");
    client.println("<style>body{font-family:sans-serif;background:#0f172a;color:#fff;text-align:center;margin:0;padding:12px}"
                   "img{width:100%;max-width:640px;border-radius:8px}"
                   "button{font-size:1rem;padding:8px 18px;margin:6px;border:0;border-radius:8px;background:#0369a1;color:#fff}</style>");
    client.println("</head><body><h2>AMB82-Mini 即時影像</h2>");
    client.println("<img id=\"v\" alt=\"即時影像\">");
    client.println("<p><button onclick=\"led(1)\">開燈</button><button onclick=\"led(0)\">關燈</button></p>");
    client.println("<p id=\"fps\"></p>");
    client.println("<script>");
    client.println("const img=document.getElementById('v');");
    client.println("let n=0,t0=Date.now();");
    client.println("function next(){img.src='/photo?t='+Date.now();}");
    client.println("img.onload=()=>{n++;document.getElementById('fps').textContent='已更新 '+n+' 張，約 '+(n/((Date.now()-t0)/1000)).toFixed(1)+' 張/秒';setTimeout(next,700);};");
    client.println("img.onerror=()=>setTimeout(next,1000);");
    client.println("function led(v){fetch('/led?on='+v);}");
    client.println("next();");
    client.println("</script></body></html>");
}
