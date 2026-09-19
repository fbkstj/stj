"""把 TFT 要顯示的中文詞彙轉成點陣圖，存成 esp32_guard_alarm/tft_labels.h。

ESP32 的內建字型只有英文數字，所以中文先在電腦上用微軟正黑體畫好，
ESP32 只要用 drawBitmap() 貼上去即可。想改顯示的文字，修改下面的 LABELS 後重新執行，再上傳 ESP32。

用法：python make_tft_labels.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "esp32_guard_alarm", "tft_labels.h")
FONT_BOLD = "C:/Windows/Fonts/msjhbd.ttc"
FONT_REGULAR = "C:/Windows/Fonts/msjh.ttc"

# (程式裡的名稱, 文字, 字級, 粗體)
LABELS = [
    ("LBL_S0", "監控中", 26, True),
    ("LBL_S1", "注意", 26, True),
    ("LBL_S2", "警報", 26, True),
    ("LBL_S3", "已通報", 26, True),
    ("LBL_S4", "已取消", 26, True),
    ("LBL_OFF", "未連線", 26, True),
    ("LBL_KW", "疑似持械", 24, True),
    ("LBL_KR", "人群奔逃", 24, True),
    ("LBL_KF", "人員倒地", 24, True),
    ("LBL_KC", "異常聚集", 24, True),
    ("LBL_KN", "畫面正常", 24, True),
    ("LBL_AFTER", "秒後通報", 18, True),
    ("LBL_PRESS", "按鈕可取消誤報", 16, False),
    ("LBL_SENT", "已發送 LINE 通報", 18, False),
    ("LBL_FALSE", "已標記為誤報", 18, False),
    ("LBL_WATCH", "請留意監控畫面", 18, False),
    ("LBL_CHECK", "請檢查電腦連線", 18, False),
]


def render(text, size, bold):
    font = ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)
    left, top, right, bottom = font.getbbox(text)
    w, h = right - left, bottom - top
    img = Image.new("1", (w, h), 0)
    ImageDraw.Draw(img).text((-left, -top), text, font=font, fill=1)
    return img


def to_bytes(img):
    """Adafruit GFX 的 drawBitmap 格式：每列由左到右、高位元在前，不足 8 位元補 0。"""
    w, h = img.size
    px = img.load()
    out = []
    for y in range(h):
        byte, bits = 0, 0
        for x in range(w):
            byte = (byte << 1) | (1 if px[x, y] else 0)
            bits += 1
            if bits == 8:
                out.append(byte)
                byte, bits = 0, 0
        if bits:
            out.append(byte << (8 - bits))
    return out


def main():
    lines = [
        "// 由 make_tft_labels.py 自動產生，不要直接修改",
        "#pragma once",
        "#include <Arduino.h>",
        "",
        "struct Label {",
        "  uint16_t w;",
        "  uint16_t h;",
        "  const uint8_t *data;",
        "};",
        "",
    ]
    total = 0
    for name, text, size, bold in LABELS:
        img = render(text, size, bold)
        data = to_bytes(img)
        total += len(data)
        lines.append(f"// {text}（{img.width}×{img.height}）")
        lines.append(f"static const uint8_t {name}_DATA[] PROGMEM = {{")
        for i in range(0, len(data), 16):
            lines.append("  " + ", ".join(f"0x{b:02X}" for b in data[i:i + 16]) + ",")
        lines.append("};")
        lines.append(f"static const Label {name} = {{{img.width}, {img.height}, {name}_DATA}};")
        lines.append("")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"已產生 {OUT}（{len(LABELS)} 個詞，共 {total} 位元組）")


if __name__ == "__main__":
    main()
