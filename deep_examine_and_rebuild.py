import os
import sys
import json
import time
import subprocess
import glob
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from faster_whisper import WhisperModel
import opencc

converter = opencc.OpenCC('s2twp')

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
        "filename": "第03節課_45分鐘分段_021500前.mp4", # check filename
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

def combine_into_natural_long_lines(segments, target_max_chars=22, min_duration=3.0):
    long_segments = []
    curr_text = ""
    curr_start = None
    curr_end = None

    for s in segments:
        text = s['text'].strip()
        if not text:
            continue

        # Filter out repetitive prompt hallucinations if any
        if "專有名詞：" in text or ("Antigravity" in text and len(text) > 40):
            continue

        if curr_start is None:
            curr_start = s['start']

        if len(curr_text) + len(text) <= target_max_chars:
            curr_text += text
            curr_end = s['end']
        else:
            if curr_text:
                long_segments.append({
                    "start": curr_start,
                    "end": max(curr_end, curr_start + min_duration),
                    "text": curr_text
                })
            curr_start = s['start']
            curr_text = text
            curr_end = s['end']

    if curr_text:
        long_segments.append({
            "start": curr_start,
            "end": max(curr_end, curr_start + min_duration),
            "text": curr_text
        })

    return long_segments

def retranscribe_all():
    print("=" * 80)
    print("🎙️ 正在進行 6 節課完整 Whisper CPU (int8) 語音辨識與校正...")
    print("=" * 80)
    
    print("[Whisper] Loading CPU int8 WhisperModel (medium)...")
    model = WhisperModel("medium", device="cpu", compute_type="int8")

    for ep in EPISODES:
        src_path = os.path.join(base_dir, ep['filename'])
        json_path = os.path.join(out_dir, "transcriptions", f"ep{ep['ep_num']:02d}_transcription.json")
        
        # We force re-transcribing ep04 because it was hallucinated earlier!
        if ep['ep_num'] == 4 or not os.path.exists(json_path):
            print(f"   Transcribing Ep {ep['ep_num']}: {ep['filename']}...")
            t0 = time.time()
            segments, info = model.transcribe(
                src_path,
                language="zh",
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
                if tw_text and "專有名詞：" not in tw_text:
                    segs_data.append({
                        "start": round(s.start, 2),
                        "end": round(s.end, 2),
                        "text": tw_text
                    })
                    
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(segs_data, f, ensure_ascii=False, indent=2)
            print(f"   Saved Ep {ep['ep_num']} JSON ({len(segs_data)} segments) in {time.time()-t0:.1f}s")
        else:
            print(f"   Using existing JSON for Ep {ep['ep_num']}")

def build_optimized_subtitles():
    print("\n[Phase 2] 重構繁體中文「單行長句 (15-25字) 舒適節奏 (3-6秒)」字幕檔...")
    for ep in EPISODES:
        ep_num = ep["ep_num"]
        json_path = os.path.join(out_dir, "transcriptions", f"ep{ep_num:02d}_transcription.json")
        
        with open(json_path, "r", encoding="utf-8") as f:
            raw_segs = json.load(f)
            
        natural_segs = combine_into_natural_long_lines(raw_segs, target_max_chars=22, min_duration=3.0)
        
        srt_lines = []
        ass_events = []
        
        for idx, s in enumerate(natural_segs, 1):
            st = s['start'] + 4.0 # +4s offset for HD cover card
            et = s['end'] + 4.0
            text = s['text']
            
            srt_lines.append(f"{idx}\n{format_srt_time(st)} --> {format_srt_time(et)}\n{text}\n")
            ass_events.append(f"Dialogue: 0,{format_ass_time(st)},{format_ass_time(et)},Default,,0,0,0,,{text}")
            
        srt_path = os.path.join(out_dir, "subtitles", f"ep{ep_num:02d}.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_lines))
            
        ass_header = f"""[Script Info]
Title: 115-09-07 AI Course Episode {ep_num}
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft JhengHei,46,&H00FFFFFF,&H000000FF,&H00181818,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,40,40,65,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        ass_path = os.path.join(out_dir, "subtitles", f"ep{ep_num:02d}.ass")
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_header + "\n".join(ass_events))
            
        print(f"   Ep {ep_num}: Re-chunked {len(raw_segs)} raw -> {len(natural_segs)} single-line long sentences (15-25 chars/line).")

if __name__ == "__main__":
    retranscribe_all()
    build_optimized_subtitles()
