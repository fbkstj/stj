/**
 * 第 4 節：Google Apps Script 接收端
 * ------------------------------------------------
 * 板子把照片 POST 過來，這支程式負責：
 *   1. 存成檔案，放進雲端硬碟指定資料夾（沒有就自動建立）
 *   2. 在試算表加一列：時間、裝置、檔名、檔案連結、大小
 *   3. （選用）推播到 LINE：要在「專案設定 → 指令碼屬性」加入 LINE_TOKEN 與 LINE_TO
 *
 * 部署步驟（每次改完程式都要「重新部署」才會生效）：
 *   1. script.google.com → 新增專案，把這份程式貼上
 *   2. 部署 → 新增部署作業 → 類型選「網頁應用程式」
 *   3. 執行身分：我；誰可以存取：「任何人」← 沒選這個，板子會收到 302 轉址後失敗
 *   4. 複製網址 https://script.google.com/macros/s/xxxxx/exec
 *      把 /macros/s/xxxxx/exec 貼進 04_cloud_upload.ino 的 scriptPath
 *
 * 安全提醒：這個網址等於「知道的人都能上傳」。課後可以改成「僅限自己」或刪除部署。
 */

// ====== 可以修改的設定 ======
var SHEET_NAME = 'AMB82 上傳紀錄';   // 試算表檔名（沒有就自動建立）
var SHARE_LINK = true;               // true＝取得「知道連結的人可檢視」的連結（LINE 推播需要）
// ============================

function doPost(e) {
  try {
    var folderName = e.parameter.myFoldername || 'AMB82-Mini';
    var fileName = e.parameter.myFilename || (new Date().getTime() + '.jpg');
    var device = e.parameter.myDevice || '未命名裝置';
    var raw = e.parameter.myFile || '';

    var base64 = raw.indexOf('base32,') >= 0 ? raw.split('base32,')[1] : raw;
    var bytes = Utilities.base64Decode(base64);
    var blob = Utilities.newBlob(bytes, 'image/jpeg', fileName);

    var folder = getOrCreateFolder(folderName);
    var file = folder.createFile(blob);
    if (SHARE_LINK) {
      file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
    }

    var id = file.getId();
    var url = 'https://drive.google.com/file/d/' + id + '/view';          // 給人點的連結
    var imageUrl = 'https://drive.google.com/thumbnail?id=' + id + '&sz=w1000';   // 給 LINE 顯示圖片用
    appendRow(device, fileName, url, Math.round(file.getSize() / 1024));
    pushToLine(device, imageUrl);

    return json({ ok: true, file: fileName, url: url });
  } catch (err) {
    return json({ ok: false, error: String(err) });
  }
}

/** 在瀏覽器直接開這個網址時，顯示一行字，方便確認部署成功 */
function doGet() {
  return ContentService.createTextOutput('AMB82 接收端運作中：請用 POST 上傳照片');
}

function getOrCreateFolder(name) {
  var it = DriveApp.getFoldersByName(name);
  return it.hasNext() ? it.next() : DriveApp.createFolder(name);
}

function appendRow(device, fileName, url, sizeKB) {
  var files = DriveApp.getFilesByName(SHEET_NAME);
  var ss = files.hasNext() ? SpreadsheetApp.open(files.next()) : SpreadsheetApp.create(SHEET_NAME);
  var sheet = ss.getSheets()[0];
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(['時間', '裝置', '檔名', '連結', '大小(KB)']);
  }
  var time = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyy-MM-dd HH:mm:ss');
  sheet.appendRow([time, device, fileName, url, sizeKB]);
}

/**
 * 選用：推播到 LINE（Messaging API）
 * LINE Notify 已於 2025 年停止服務，改用 Messaging API：
 *   1. LINE Developers 建立 Messaging API channel，取得 Channel access token
 *   2. 用官方帳號加自己好友，取得自己的 userId（或群組 id）
 *   3. 指令碼屬性加入 LINE_TOKEN、LINE_TO 兩個值；沒設定就自動略過
 *
 * LINE 只接受「公開的 HTTPS 圖片網址」，所以這裡用雲端硬碟的縮圖網址；
 * 檔案必須設成「知道連結的人可檢視」（SHARE_LINK = true）。
 * 如果 LINE 收到訊息卻沒有圖，先把那個網址貼到瀏覽器無痕視窗，看看是不是真的看得到圖。
 */
function pushToLine(device, imageUrl) {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('LINE_TOKEN');
  var to = props.getProperty('LINE_TO');
  if (!token || !to) {
    return;
  }
  var payload = {
    to: to,
    messages: [
      { type: 'text', text: device + ' 上傳了一張照片' },
      { type: 'image', originalContentUrl: imageUrl, previewImageUrl: imageUrl }
    ]
  };
  UrlFetchApp.fetch('https://api.line.me/v2/bot/message/push', {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });
}

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
