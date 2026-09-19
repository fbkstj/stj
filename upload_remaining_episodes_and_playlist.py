import os
import sys
import json
import subprocess
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

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

base_dir = r"d:\影片編輯\115-09-07-AI課程"
out_dir = os.path.join(base_dir, "output")
token_path = r"d:\影片編輯\yt_token.json"

EPISODES_TO_UPLOAD = [
    {
        "ep_num": 2,
        "video": os.path.join(out_dir, "final_videos", "ep02_final.mp4"),
        "srt": os.path.join(out_dir, "subtitles", "ep02.srt"),
        "title": "【115-09-07 AI課程】第 02 節課：ChatGPT 與提示詞工程 (Prompt Engineering)",
        "desc": "115-09-07 AI 應用與實務課程 - 第 02 節課：ChatGPT 與提示詞工程 (Prompt Engineering)。內建繁體中文字幕與 1080p 高清片頭圖卡。"
    },
    {
        "ep_num": 3,
        "video": os.path.join(out_dir, "final_videos", "ep03_final.mp4"),
        "srt": os.path.join(out_dir, "subtitles", "ep03.srt"),
        "title": "【115-09-07 AI課程】第 03 節課：LLM 大語言模型實作與應用案例",
        "desc": "115-09-07 AI 應用與實務課程 - 第 03 節課：LLM 大語言模型實作與應用案例。內建繁體中文字幕與 1080p 高清片頭圖卡。"
    },
    {
        "ep_num": 4,
        "video": os.path.join(out_dir, "final_videos", "ep04_final.mp4"),
        "srt": os.path.join(out_dir, "subtitles", "ep04.srt"),
        "title": "【115-09-07 AI課程】第 04 節課：Python 與 AI 自動化腳本實用技能",
        "desc": "115-09-07 AI 應用與實務課程 - 第 04 節課：Python 與 AI 自動化腳本實用技能。內建繁體中文字幕與 1080p 高清片頭圖卡。"
    },
    {
        "ep_num": 5,
        "video": os.path.join(out_dir, "final_videos", "ep05_final.mp4"),
        "srt": os.path.join(out_dir, "subtitles", "ep05.srt"),
        "title": "【115-09-07 AI課程】第 05 節課：AI 工具整合與工作流優化",
        "desc": "115-09-07 AI 應用與實務課程 - 第 05 節課：AI 工具整合與工作流優化。內建繁體中文字幕與 1080p 高清片頭圖卡。"
    },
    {
        "ep_num": 6,
        "video": os.path.join(out_dir, "final_videos", "ep06_final.mp4"),
        "srt": os.path.join(out_dir, "subtitles", "ep06.srt"),
        "title": "【115-09-07 AI課程】第 06 節課：AI 專案成果總結與未來展望",
        "desc": "115-09-07 AI 應用與實務課程 - 第 06 節課：AI 專案成果總結與未來展望。內建繁體中文字幕與 1080p 高清片頭圖卡。"
    }
]

def get_youtube_service():
    if not os.path.exists(token_path):
        raise FileNotFoundError(f"找不到 Token: {token_path}")
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def main():
    print("=" * 70)
    print("🚀 啟動背景全自動發布：【115-09-07 AI課程】第 02~06 節課與播放清單建置")
    print("=" * 70)
    
    youtube = get_youtube_service()
    
    # Already uploaded Ep 1 ID
    all_playlist_video_ids = ["rSP5i_iQf1A"]
    
    for item in EPISODES_TO_UPLOAD:
        v_path = item["video"]
        v_title = item["title"]
        v_desc = item["desc"]
        v_srt = item["srt"]
        
        file_size_mb = os.path.getsize(v_path) / (1024 * 1024)
        print(f"\n[上傳第 {item['ep_num']} 節課] {v_title} ({file_size_mb:.1f} MB)...")
        
        body = {
            "snippet": {
                "title": v_title,
                "description": v_desc,
                "tags": ["AI課程", "楊梅高中", "Python", "ChatGPT", "LLM", "生成式AI"],
                "categoryId": "27",
                "defaultLanguage": "zh-TW",
                "defaultAudioLanguage": "zh-TW"
            },
            "status": {
                "privacyStatus": "unlisted",
                "selfDeclaredMadeForKids": False
            }
        }
        
        media = MediaFileUpload(v_path, chunksize=10*1024*1024, resumable=True)
        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                bar = ("#" * (pct // 5)).ljust(20)
                print(f"\r  進度: [{bar}] {pct}%", end="", flush=True)
                
        print("\n")
        vid = response["id"]
        watch_url = f"https://youtu.be/{vid}"
        print(f"🎉 [SUCCESS] 第 {item['ep_num']} 節課上傳成功！ ID: {vid} | 連結: {watch_url}")
        all_playlist_video_ids.append(vid)
        
        # Upload Subtitle if available
        if v_srt and os.path.exists(v_srt):
            try:
                caption_media = MediaFileUpload(v_srt, mimetype="application/x-subrip")
                youtube.captions().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "videoId": vid,
                            "language": "zh-TW",
                            "name": "繁體中文 (精校版)",
                            "isDraft": False
                        }
                    },
                    media_body=caption_media
                ).execute()
                print("  💬 CC 字幕檔已成功掛載！")
            except Exception as e:
                print(f"  💬 CC 字幕提示: {e}")

    print("\n" + "="*70)
    print("📋 正在建置全輯 YouTube 專屬播放清單 (Playlist)...")
    print("="*70)
    
    playlist_body = {
        "snippet": {
            "title": "【AI 課程全輯】115-09-07 AI 應用與實務教學（全 6 節課完整版）",
            "description": "桃園市立楊梅高級中等學校 實習處 115-09-07 AI 應用與實務全輯課程（全 6 節課完整版）。內建繁體中文字幕與 1080p 高清片頭圖卡。",
            "defaultLanguage": "zh-TW"
        },
        "status": {
            "privacyStatus": "unlisted"
        }
    }
    
    playlist_response = youtube.playlists().insert(
        part="snippet,status",
        body=playlist_body
    ).execute()
    
    playlist_id = playlist_response["id"]
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    print(f"🎉 播放清單建立成功！ ID: {playlist_id}")
    print(f"🔗 播放清單連結: {playlist_url}")
    
    for vid_idx, vid_id in enumerate(all_playlist_video_ids):
        item_body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": vid_id
                },
                "position": vid_idx
            }
        }
        youtube.playlistItems().insert(part="snippet", body=item_body).execute()
        print(f"   已新增影片 #{vid_idx+1} ({vid_id}) 至播放清單")
        
    print("\n" + "="*70)
    print("🎉 ALL DONE! 【115-09-07 AI課程】全 6 節課 YouTube 播放清單發布完成！")
    print(f"🔗 播放清單總連結: {playlist_url}")
    print(f"🍿 第一集觀看連結 (含右側常駐選單): https://www.youtube.com/watch?v={all_playlist_video_ids[0]}&list={playlist_id}")
    print("="*70)

if __name__ == "__main__":
    main()
