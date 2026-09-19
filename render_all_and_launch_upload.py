import os
import sys
import json
import time
import subprocess
from PIL import Image, ImageDraw, ImageFont

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

base_dir = r"d:\影片編輯\115-09-07-AI課程"
out_dir = os.path.join(base_dir, "output")
os.makedirs(out_dir, exist_ok=True)
os.makedirs(os.path.join(out_dir, "covers"), exist_ok=True)
os.makedirs(os.path.join(out_dir, "final_videos"), exist_ok=True)

font_path = r"C:\Windows\Fonts\msjh.ttc"

EPISODES = [
    {
        "ep_num": 1,
        "filename": "第01節課_45分鐘分段_000000至004500.mp4",
        "title": "【115-09-07 AI課程】第 01 節課：AI 概論與生成式模型基礎",
        "short_title": "第 01 節課：AI 概論與生成式模型基礎"
    },
    {
        "ep_num": 2,
        "filename": "第02節課_45分鐘分段_004500至013000.mp4",
        "title": "【115-09-07 AI課程】第 02 節課：ChatGPT 與提示詞工程 (Prompt Engineering)",
        "short_title": "第 02 節課：ChatGPT 與提示詞工程"
    },
    {
        "ep_num": 3,
        "filename": "第03節課_45分鐘分段_013000至021500.mp4",
        "title": "【115-09-07 AI課程】第 03 節課：LLM 大語言模型實作與應用案例",
        "short_title": "第 03 節課：LLM 大語言模型實作與應用案例"
    },
    {
        "ep_num": 4,
        "filename": "第04節課_45分鐘分段_021500至030000.mp4",
        "title": "【115-09-07 AI課程】第 04 節課：Python 與 AI 自動化腳本實用技能",
        "short_title": "第 04 節課：Python 與 AI 自動化腳本實用技能"
    },
    {
        "ep_num": 5,
        "filename": "第05節課_45分鐘分段_030000至034500.mp4",
        "title": "【115-09-07 AI課程】第 05 節課：AI 工具整合與工作流優化",
        "short_title": "第 05 節課：AI 工具整合與工作流優化"
    },
    {
        "ep_num": 6,
        "filename": "第06節課_45分鐘分段_034500至042950.mp4",
        "title": "【115-09-07 AI課程】第 06 節課：AI 專案成果總結與未來展望",
        "short_title": "第 06 節課：AI 專案成果總結與未來展望"
    }
]

def create_intro_covers():
    print("=" * 80)
    print("🎬 [Step 1] 產生 1080p HD 4 秒動態片頭圖卡...")
    print("=" * 80)
    font_title = ImageFont.truetype(font_path, 52)
    font_sub = ImageFont.truetype(font_path, 36)
    font_small = ImageFont.truetype(font_path, 26)

    for ep in EPISODES:
        cover_png = os.path.join(out_dir, "covers", f"ep{ep['ep_num']:02d}_cover.png")
        intro_mp4 = os.path.join(out_dir, "covers", f"ep{ep['ep_num']:02d}_intro.mp4")

        if True: # Always regenerate cover png with date 2026/09/07
            img = Image.new("RGB", (1920, 1080), color=(18, 28, 45))
            draw = ImageDraw.Draw(img)
            draw.rectangle([40, 40, 1880, 1040], outline=(60, 140, 230), width=6)
            draw.rectangle([52, 52, 1868, 1028], outline=(100, 180, 255), width=2)

            draw.rounded_rectangle([660, 120, 1260, 190], radius=15, fill=(60, 140, 230))
            draw.text((960, 155), "115-09-07 AI 應用與實務全輯課程", font=font_sub, fill=(255, 255, 255), anchor="mm")

            draw.text((960, 340), ep['title'], font=font_title, fill=(255, 230, 150), anchor="mm")

            draw.rounded_rectangle([300, 520, 1620, 880], radius=20, fill=(28, 40, 65), outline=(80, 120, 180), width=3)
            draw.text((960, 600), f"🏫 課程名稱：AI 應用與實務 (全 6 節課完整版)", font=font_sub, fill=(255, 255, 255), anchor="mm")
            draw.text((960, 690), f"📅 上課日期：2026 年 09 月 07 日", font=font_sub, fill=(212, 175, 55), anchor="mm")
            draw.text((960, 780), f"▶️ 即將開始播放 {ep['short_title']}...", font=font_sub, fill=(180, 210, 255), anchor="mm")

            draw.text((960, 970), "桃園市立楊梅高級中等學校 實習處 製作發行", font=font_small, fill=(160, 180, 210), anchor="mm")
            img.save(cover_png)

        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", cover_png,
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "libx264", "-t", "4.0", "-r", "30", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", intro_mp4
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ep['intro_mp4'] = intro_mp4

def encode_videos():
    print("\n" + "=" * 80)
    print("🔥 [Step 2] 全面壓製 1080p 內嵌單行舒適字幕 MP4 影片...")
    print("=" * 80)
    
    for ep in EPISODES:
        src_video = os.path.join(base_dir, ep['filename'])
        intro_mp4 = ep['intro_mp4']
        ass_path = os.path.join(out_dir, "subtitles", f"ep{ep['ep_num']:02d}.ass")
        final_mp4 = os.path.join(out_dir, "final_videos", f"ep{ep['ep_num']:02d}_final.mp4")

        clean_ass = ass_path.replace("\\", "/").replace(":", "\\:")

        print(f"   Encoding Ep {ep['ep_num']}: ep{ep['ep_num']:02d}_final.mp4...")
        t0 = time.time()
        cmd = [
            "ffmpeg", "-y",
            "-i", intro_mp4,
            "-i", src_video,
            "-filter_complex",
            f"[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[v0];"
            f"[1:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[v1];"
            f"[v0][0:a][v1][1:a]concat=n=2:v=1:a=1[vconcat][acontat];"
            f"[vconcat]ass='{clean_ass}'[outv]",
            "-map", "[outv]", "-map", "[acontat]",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "192k",
            final_mp4
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        dur_s = time.time() - t0
        mb_sz = os.path.getsize(final_mp4) / (1024 * 1024)
        print(f"   🎉 Done Ep {ep['ep_num']} in {dur_s:.1f}s ({mb_sz:.1f} MB)")

if __name__ == "__main__":
    create_intro_covers()
    encode_videos()
    print("\n✅ 所有影片壓製完成！即將觸發 YouTube 自動化批次上傳...")
