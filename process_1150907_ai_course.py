import os
import sys
import json
import time
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Ensure UTF-8 output on Windows terminal
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from faster_whisper import WhisperModel
import opencc

converter = opencc.OpenCC('s2twp') # Simplified to Traditional Taiwan Phrases

base_dir = r"d:\影片編輯\115-09-07-AI課程"
out_dir = os.path.join(base_dir, "output")
os.makedirs(out_dir, exist_ok=True)
os.makedirs(os.path.join(out_dir, "transcriptions"), exist_ok=True)
os.makedirs(os.path.join(out_dir, "subtitles"), exist_ok=True)
os.makedirs(os.path.join(out_dir, "covers"), exist_ok=True)
os.makedirs(os.path.join(out_dir, "final_videos"), exist_ok=True)

font_path = r"C:\Windows\Fonts\msjh.ttc"

EPISODES = [
    {
        "ep_num": 1,
        "filename": "第01節課_45分鐘分段_000000至004500.mp4",
        "title": "【115-09-07 AI課程】第 01 節課：AI 概論與生成式模型基礎",
        "short_title": "第 01 節課：AI 概論與生成式模型基礎",
        "desc": "115-09-07 AI 應用與實務課程 - 第 01 節課：AI 概論與生成式模型基礎。"
    },
    {
        "ep_num": 2,
        "filename": "第02節課_45分鐘分段_004500至013000.mp4",
        "title": "【115-09-07 AI課程】第 02 節課：ChatGPT 與提示詞工程 (Prompt Engineering)",
        "short_title": "第 02 節課：ChatGPT 與提示詞工程",
        "desc": "115-09-07 AI 應用與實務課程 - 第 02 節課：ChatGPT 與提示詞工程 (Prompt Engineering)。"
    },
    {
        "ep_num": 3,
        "filename": "第03節課_45分鐘分段_013000至021500.mp4",
        "title": "【115-09-07 AI課程】第 03 節課：LLM 大語言模型實作與應用案例",
        "short_title": "第 03 節課：LLM 大語言模型實作與應用案例",
        "desc": "115-09-07 AI 應用與實務課程 - 第 03 節課：LLM 大語言模型實作與應用案例。"
    },
    {
        "ep_num": 4,
        "filename": "第04節課_45分鐘分段_021500至030000.mp4",
        "title": "【115-09-07 AI課程】第 04 節課：Python 與 AI 自動化腳本實用技能",
        "short_title": "第 04 節課：Python 與 AI 自動化腳本實用技能",
        "desc": "115-09-07 AI 應用與實務課程 - 第 04 節課：Python 與 AI 自動化腳本實用技能。"
    },
    {
        "ep_num": 5,
        "filename": "第05節課_45分鐘分段_030000至034500.mp4",
        "title": "【115-09-07 AI課程】第 05 節課：AI 工具整合與工作流優化",
        "short_title": "第 05 節課：AI 工具整合與工作流優化",
        "desc": "115-09-07 AI 應用與實務課程 - 第 05 節課：AI 工具整合與工作流優化。"
    },
    {
        "ep_num": 6,
        "filename": "第06節課_45分鐘分段_034500至042950.mp4",
        "title": "【115-09-07 AI課程】第 06 節課：AI 專案成果總結與未來展望",
        "short_title": "第 06 節課：AI 專案成果總結與未來展望",
        "desc": "115-09-07 AI 應用與實務課程 - 第 06 節課：AI 專案成果總結與未來展望。"
    }
]

def format_srt_time(sec_float):
    hrs = int(sec_float // 3600)
    rem = sec_float % 3600
    mins = int(rem // 60)
    secs = int(rem % 60)
    milli = int((rem - int(rem)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{milli:03d}"

def format_ass_time(sec_float):
    hrs = int(sec_float // 3600)
    rem = sec_float % 3600
    mins = int(rem // 60)
    secs = int(rem % 60)
    milli = int((rem - int(rem)) * 100)
    return f"{hrs}:{mins:02d}:{secs:02d}.{milli:02d}"

def load_whisper_model():
    print("[Whisper] Initializing Faster-Whisper Model (medium)...")
    try:
        model = WhisperModel("medium", device="cuda", compute_type="float16")
        print("   Using CUDA GPU acceleration.")
    except Exception as e:
        print(f"   Fallback to CPU mode: {e}")
        model = WhisperModel("medium", device="cpu", compute_type="int8")
    return model

def transcribe_episodes(model):
    print("\n[Phase 1] Transcribing 6 Episodes with Domain Prompt & VAD...")
    domain_prompt = "這是台灣高職 AI 應用與實務課堂教學。專有名詞：AI、Python、ChatGPT、提示詞 Prompt、LLM、生成式AI、模型、Gemini、Antigravity、自動化。"
    
    for ep in EPISODES:
        src_path = os.path.join(base_dir, ep['filename'])
        json_path = os.path.join(out_dir, "transcriptions", f"ep{ep['ep_num']:02d}_transcription.json")
        
        if not os.path.exists(json_path):
            print(f"   Transcribing Episode {ep['ep_num']}: {ep['filename']}...")
            t0 = time.time()
            segments, info = model.transcribe(
                src_path,
                language="zh",
                initial_prompt=domain_prompt,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=1500,
                    speech_pad_ms=400
                )
            )
            
            segs_data = []
            for s in segments:
                tw_text = converter.convert(s.text.strip())
                if tw_text:
                    segs_data.append({
                        "start": round(s.start, 2),
                        "end": round(s.end, 2),
                        "text": tw_text
                    })
                    
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(segs_data, f, ensure_ascii=False, indent=2)
            print(f"   Saved Episode {ep['ep_num']} JSON ({len(segs_data)} segments) in {time.time()-t0:.1f}s")
        else:
            print(f"   Cached JSON found: ep{ep['ep_num']:02d}_transcription.json")
            
        ep['json_path'] = json_path

def generate_srt_and_ass():
    print("\n[Phase 2] Generating Traditional Chinese Single-Line SRT & ASS Subtitles...")
    for ep in EPISODES:
        with open(ep['json_path'], "r", encoding="utf-8") as f:
            segs = json.load(f)
            
        srt_lines = []
        ass_events = []
        srt_idx = 1
        
        for s in segs:
            st = s['start'] + 4.0  # 4-second offset for 4s intro clip
            et = s['end'] + 4.0
            text = s['text']
            
            # Split long lines into 12-18 chars per line
            if len(text) > 20:
                mid = len(text) // 2
                lines = [text[:mid], text[mid:]]
                dur_half = (et - st) / 2
                
                # Line 1
                srt_lines.append(f"{srt_idx}\n{format_srt_time(st)} --> {format_srt_time(st+dur_half)}\n{lines[0]}\n")
                ass_events.append(f"Dialogue: 0,{format_ass_time(st)},{format_ass_time(st+dur_half)},Default,,0,0,0,,{lines[0]}")
                srt_idx += 1
                
                # Line 2
                srt_lines.append(f"{srt_idx}\n{format_srt_time(st+dur_half)} --> {format_srt_time(et)}\n{lines[1]}\n")
                ass_events.append(f"Dialogue: 0,{format_ass_time(st+dur_half)},{format_ass_time(et)},Default,,0,0,0,,{lines[1]}")
                srt_idx += 1
            else:
                srt_lines.append(f"{srt_idx}\n{format_srt_time(st)} --> {format_srt_time(et)}\n{text}\n")
                ass_events.append(f"Dialogue: 0,{format_ass_time(st)},{format_ass_time(et)},Default,,0,0,0,,{text}")
                srt_idx += 1
                
        srt_path = os.path.join(out_dir, "subtitles", f"ep{ep['ep_num']:02d}.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
        ep['srt_path'] = srt_path
        
        ass_header = f"""[Script Info]
Title: 115-09-07 AI Course Episode {ep['ep_num']}
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft JhengHei,46,&H00FFFFFF,&H000000FF,&H00181818,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,40,40,65,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        ass_path = os.path.join(out_dir, "subtitles", f"ep{ep['ep_num']:02d}.ass")
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_header + "\n".join(ass_events))
        ep['ass_path'] = ass_path

def create_intro_covers():
    print("\n[Phase 3] Generating 1080p HD Intro Cover Cards & 4-second Clips...")
    font_title = ImageFont.truetype(font_path, 52)
    font_sub = ImageFont.truetype(font_path, 36)
    font_small = ImageFont.truetype(font_path, 26)
    
    for ep in EPISODES:
        cover_png = os.path.join(out_dir, "covers", f"ep{ep['ep_num']:02d}_cover.png")
        intro_mp4 = os.path.join(out_dir, "covers", f"ep{ep['ep_num']:02d}_intro.mp4")
        
        if not os.path.exists(cover_png):
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
            
        if not os.path.exists(intro_mp4):
            cmd = [
                "ffmpeg", "-y", "-loop", "1", "-i", cover_png,
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-c:v", "libx264", "-t", "4.0", "-r", "30", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "44100", "-ac", "2", intro_mp4
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        ep['intro_mp4'] = intro_mp4

def encode_final_videos():
    print("\n[Phase 4 & 5] Concatenating 4s Intro & Burning Traditional Chinese Subtitles...")
    batch_queue = []
    
    for ep in EPISODES:
        src_video = os.path.join(base_dir, ep['filename'])
        intro_mp4 = ep['intro_mp4']
        ass_path = ep['ass_path']
        final_mp4 = os.path.join(out_dir, "final_videos", f"ep{ep['ep_num']:02d}_final.mp4")
        
        clean_ass = ass_path.replace("\\", "/").replace(":", "\\:")
        
        if not os.path.exists(final_mp4):
            print(f"   Encoding & Burning Subtitles for Episode {ep['ep_num']}...")
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
            print(f"   Finished: ep{ep['ep_num']:02d}_final.mp4")
        else:
            print(f"   Cached Video Found: ep{ep['ep_num']:02d}_final.mp4")
            
        ep['final_mp4'] = final_mp4
        
        batch_queue.append({
            "video": final_mp4,
            "title": ep['title'],
            "desc": ep['desc'],
            "srt": ep['srt_path'],
            "tags": ["AI課程", "楊梅高中", "Python", "ChatGPT", "LLM", "生成式AI", "提示詞工程"],
            "privacy": "unlisted"
        })
        
    batch_json = os.path.join(out_dir, "ai_course_batch_upload_queue.json")
    with open(batch_json, "w", encoding="utf-8") as f:
        json.dump(batch_queue, f, ensure_ascii=False, indent=2)
    return batch_json

def main():
    model = load_whisper_model()
    transcribe_episodes(model)
    generate_srt_and_ass()
    create_intro_covers()
    batch_json = encode_final_videos()
    print(f"\n[SUCCESS] All 6 Episodes rendered & encoded! Batch Upload JSON: {batch_json}")

if __name__ == "__main__":
    main()
