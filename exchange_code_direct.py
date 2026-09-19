import os
import sys
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl"
]

secret_path = r"d:\影片編輯\client_secrets.json"
token_path = r"d:\影片編輯\yt_token.json"

def exchange_url(full_url):
    print("=" * 70)
    print("🔑 正在從瀏覽器網址列提取 Code 並與 Google 換取授權權杖...")
    print("=" * 70)
    
    flow = InstalledAppFlow.from_client_secrets_file(
        secret_path,
        scopes=SCOPES,
        redirect_uri="http://127.0.0.1:8080/"
    )
    
    flow.fetch_token(authorization_response=full_url)
    creds = flow.credentials
    
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
        
    print(f"\n[SUCCESS] 🎉 全新憑證已成功儲存至: {token_path}")
    
    youtube = build("youtube", "v3", credentials=creds)
    response = youtube.channels().list(part="snippet,statistics", mine=True).execute()
    items = response.get("items", [])
    
    if items:
        channel = items[0]
        title = channel["snippet"]["title"]
        print("=" * 70)
        print(f"🎉 頻道綁定成功！目前 YouTube 頻道：【{title}】")
        print("=" * 70)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        exchange_url(sys.argv[1])
    else:
        print("請提供瀏覽器網址列的完整 URL。")
