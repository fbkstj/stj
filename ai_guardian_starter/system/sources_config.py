"""
影像來源設定 —— 要監看哪些攝影機都寫在這裡。

⚠️ 只能接「有授權」的影像來源:自己的攝影機、學校/單位同意介接的攝影機、
政府公開資料平台明文開放的即時影像。未經同意連線他人攝影機屬於《刑法》妨害電腦使用罪。

type 可用值:
  webcam         USB/筆電攝影機,src 填裝置編號(0、1…)
  rtsp           網路攝影機串流,src 填 rtsp://帳號:密碼@IP:554/stream2
  http_snapshot  定時抓一張 JPG 的公開快照網址,src 填網址,interval 為抓圖秒數
  video          錄影檔(會循環播放),測試用
  image          單張圖片,測試用
"""

SOURCES = [
    {"name": "本機攝影機", "type": "webcam", "src": 0},

    # --- 以下為範例,需要時取消註解並修改 ---
    # {"name": "校門口", "type": "rtsp",
    #  "src": "rtsp://帳號:密碼@192.168.68.100:554/stream2"},
    # {"name": "公開路口快照", "type": "http_snapshot",
    #  "src": "https://example.gov.tw/cctv/xxx.jpg", "interval": 2},
    # {"name": "測試影片", "type": "video",
    #  "src": r"C:\影片\test.mp4"},
]
