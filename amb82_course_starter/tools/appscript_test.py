"""第 4 節小工具：不用板子，先確認 Google Apps Script 接收端有沒有部署成功。

它會用電腦送一張測試圖片到你的 Apps Script 網址，流程和板子完全一樣。
成功的話，雲端硬碟會多一張圖、試算表會多一列（有設 LINE 的話手機也會收到）。

用法：
  python appscript_test.py https://script.google.com/macros/s/xxxx/exec
  python appscript_test.py https://script.google.com/macros/s/xxxx/exec --image 我的照片.jpg

網址只在你自己的電腦上使用，這支程式不會把它存起來。
"""
import argparse
import base64
import io
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def test_image_bytes():
    """沒有指定照片時，產生一張 320x240 的測試圖（純 Python，不需要額外套件）。"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    img = Image.new("RGB", (320, 240), (15, 23, 42))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 300, 220], outline=(56, 189, 248), width=3)
    d.text((40, 110), "AMB82 test upload", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Apps Script 的 /exec 網址")
    parser.add_argument("--image", help="要上傳的 JPG 檔；不給就自動產生一張測試圖")
    parser.add_argument("--folder", default="AMB82-Mini")
    parser.add_argument("--device", default="電腦測試")
    args = parser.parse_args()

    if not args.url.endswith("/exec"):
        print("注意：網址通常以 /exec 結尾，/dev 的網址只有自己登入時能用")

    if args.image:
        with open(args.image, "rb") as f:
            data = f.read()
    else:
        data = test_image_bytes()
        if data is None:
            print("沒有安裝 Pillow，無法產生測試圖。請改用 --image 指定一張 JPG，或先 pip install pillow")
            return 1

    payload = urllib.parse.urlencode({
        "myFoldername": args.folder,
        "myDevice": args.device,
        "myFilename": "test_from_pc.jpg",
        "myFile": "data:image/jpeg;base32," + base64.b64encode(data).decode(),
    }).encode()

    print(f"上傳 {len(data) // 1024} KB 到 Apps Script…")
    req = urllib.request.Request(args.url, data=payload,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode("utf-8", "ignore")
        print("回應：", body[:500])
        if '"ok":true' in body:
            print("成功：去雲端硬碟和試算表確認")
            return 0
        print("失敗：請檢查 Code.gs 是否有錯，或重新部署")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}：", e.read().decode("utf-8", "ignore")[:300])
        print("401／403：部署時「誰可以存取」要選『任何人』")
    except Exception as e:
        print("連線失敗：", e)
    return 1


if __name__ == "__main__":
    sys.exit(main())
