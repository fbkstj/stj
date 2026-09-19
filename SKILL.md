---
name: teaching-video-pipeline
description: >-
  專業教學影片全自動後製、高精度語音校正、純單行字幕生成（零漂移對齊）、
  專業插畫封面與4秒片頭生成、ASS 轉場卡片設計、FFmpeg 高畫質壓制，以及 YouTube API 自動發布技能。
---

# 教學影片全流程後製與 YouTube 自動發布技能 (Teaching Video Pipeline)

本技能提供一套標準化、高精度、防呆且「一次到位」的完整影片後製與發布流程。

---

## 🚀 核心工作流程與六大階段

```
[原始錄影素材 (.mp4)]
       │
       ▼
【階段一：高精度語音辨識】 ── Whisper Medium ＋ 台灣教學術語庫 ＋ Beam Search=5
       │
       ▼
【階段二：單行字幕校對與零漂移切分】 ── 同音字替換 ＋ 10~18字/行 ＋ `--offset 4.0`
       │
       ▼
【階段三：專業插畫首頁與 4 秒片頭生成】 ── PIL 繪製標題/章節 ＋ 嵌入教師插畫 ＋ 1080p 片頭
       │
       ▼
【階段四：ASS 視覺樣式與動態章節生成】 ── 頂部標題 ＋ 日期 ＋ 4.5s 轉場卡片（防雙重平移）
       │
       ▼
【階段五：FFmpeg 影片組合與字幕燒錄壓制】 ── 組合 4s 片頭 ＋ 課程影片 ＋ 渲染 ASS 字幕
       │
       ▼
【階段六：YouTube 自動發布與 CC 字幕掛載】 ── YouTube API 上傳 ＋ 章節時間軸 ＋ 獨立 CC 字幕軌
```

---

## 🛠️ 各階段標準命令與腳本調用規範

### 階段一：高精度語音辨識 (Transcription)
使用 `scripts/transcribe_domain.py` 進行語音捕捉：
```powershell
python teaching-video-pipeline/scripts/transcribe_domain.py `
  --video "第X集_主題.mp4" `
  --output "output/第X集_transcription.json" `
  --prompt "這是台灣高職電子電路實習課堂教學。專有名詞：KiCad、原理圖、PCB、電路圖、封裝、萬用洞洞板、接地 GND、VCC、CPLD、JTAG、Quartus II。"
```

### 階段二：單行字幕切分、零漂移對齊與智能無聲/低音量裁切 (Subtitle Chunking & Silence Trimming)
使用 `scripts/clean_and_chunk_singleline.py`：
```powershell
python teaching-video-pipeline/scripts/clean_and_chunk_singleline.py `
  --json "output/第X集_transcription.json" `
  --output "output/第X集_主題.srt" `
  --offset 4.0
```
> [!IMPORTANT]
> **雙重品質保證標準 (Dual Quality Assurance Standards)**：
> 1. **單行長句、快適閱讀 (Single-Line Natural Sentences)**：
>    * 畫面永遠只保持單行顯示（絕不疊加上下兩行）。
>    * 字幕長度按自然標點與語意切分為 15 ~ 25 字完整長句，留在畫面上 3 ~ 6 秒，徹底消除頻繁快閃切換感。
> 2. **智能無聲、低音量與空白刪除 (Smart Silence & Low-Volume Removal)**：
>    * 使用 FFmpeg `silencedetect` 與 VAD 音訊過濾，自動偵測並刪除「超過 1.5 秒無聲停頓」、「非上課/下課空白段落」與「音量過小無法辨識」之無效影片片段！

### 階段三：專業插畫首頁與 4 秒片頭生成 (Intro Cover Generation)
使用 `scripts/create_intro_card.py`：
```powershell
python teaching-video-pipeline/scripts/create_intro_card.py `
  --png "output/intro_cover_epX.png" `
  --mp4 "output/intro_clip_epX.mp4" `
  --title "【數位電子乙級】第一題 KiCad 電路板設計教學" `
  --ep "第 X 集：單元名稱" `
  --date "2026/03/25" `
  --duration 4.0 `
  --illustration "output/teacher_pcb_illustration.jpg"
```

### 階段四：ASS 視覺樣式與轉場生成 (ASS Style Generation)
使用 `scripts/generate_teaching_ass.py`：
```powershell
python teaching-video-pipeline/scripts/generate_teaching_ass.py `
  --srt "output/第X集_主題.srt" `
  --output "output/第X集_主題.ass" `
  --title "【數位電子乙級】第一題 KiCad 電路板設計教學（第 X 集：單元名稱）" `
  --date "2026/03/25" `
  --duration [影片時長秒數] `
  --config "output/epX_config.json" `
  --offset 4.0
```
> [!CAUTION]
> **避免雙重平移 (No Double Offset)**：
> SRT 檔案內的時間軸已經包含 `--offset 4.0`，因此 `generate_teaching_ass.py` 在讀取 SRT 的時間點時，**不可重複相加 offset**，確保畫面內崁字幕與獨立 CC 字幕 100% 毫秒級對齊！

### 階段五：FFmpeg 影片組合與字幕燒錄壓制 (Video Encoding)
```powershell
ffmpeg -y -i "output/intro_clip_epX.mp4" -i "第X集_主題.mp4" `
  -filter_complex "[0:v] scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2 [v0]; [1:v] scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2 [v1]; [v0][0:a][v1][1:a] concat=n=2:v=1:a=1 [vconcat][a0]; [vconcat] ass='output/第X集_主題.ass' [outv]" `
  -map "[outv]" -map "[a0]" -c:v libx264 -preset veryfast -crf 20 -c:a aac "output/第X集_主題_final.mp4"
```

### 階段六：YouTube 自動發布與 CC 字幕掛載 (YouTube Upload)
使用 `.agents/skills/youtube-uploader/scripts/upload.py`：
```powershell
python .agents/skills/youtube-uploader/scripts/upload.py `
  --video "output/第X集_主題_final.mp4" `
  --title "【數位電子乙級】第一題 KiCad 電路板設計教學（第 X 集：單元名稱）" `
  --desc-file "output/epX_description.txt" `
  --tags "數位電子乙級,KiCad,電路板設計,CPLD,電子實習" `
  --srt "output/第X集_主題.srt" `
  --privacy "unlisted"
```

---

## 📂 腳本庫一覽 (Scripts Directory)

- 🎙️ `scripts/transcribe_domain.py`：帶領域 Prompt 的高精度語音辨識腳本。
- ✍️ `scripts/clean_and_chunk_singleline.py`：純單行 SRT 切分器，內建同音字典與零漂移 `--offset` 對齊算法。
- 🖼️ `scripts/create_intro_card.py`：高清封面 PNG 與 4 秒 1080p 片頭 MP4 自動生成器（支持專業插畫嵌入）。
- 🎨 `scripts/generate_teaching_ass.py`：教學影片 ASS 標題、日期、動態步驟標籤、4.5s 轉場頁與字幕生成器。
- 🚀 `.agents/skills/youtube-uploader/scripts/upload.py`：YouTube API 自動發布、章節時間軸掛載與獨立 CC 字幕上傳工具。
