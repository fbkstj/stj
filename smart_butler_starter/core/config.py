"""L1 設定中心：讀取 config/settings.yaml 與 .env。

- get_settings()：取得所有可調參數（字典）
- get_secret(name)：從 .env 讀金鑰；沒有設定時回傳空字串
- validate(data)：檢查設定，回傳中文錯誤清單（管理介面存檔前也用它）
- update_yaml_values()：只改數值、保留註解（管理介面存檔用）

單獨執行 python -m core.config 可以檢查設定檔。
"""
from __future__ import annotations

import copy
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "config" / "settings.yaml"
DEMO_PATH = ROOT / "config" / "demo_overrides.yaml"
ENV_PATH = ROOT / ".env"

MODULE_NAMES = ["care", "chat", "board", "camera", "meds", "daily", "sos", "routine"]
LEVELS = ["info", "warn", "urgent"]


class ConfigError(Exception):
    """設定有錯。errors 是中文錯誤訊息清單。"""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("設定檔有錯誤：\n  - " + "\n  - ".join(errors))


# ---------- 檢查規則 ----------
def _is_hhmm(v) -> bool:
    return isinstance(v, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v) is not None


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# 欄位路徑 → (檢查函式, 說明)
RULES: dict[str, tuple] = {
    "system.name": (lambda v: isinstance(v, str) and v, "要是文字"),
    "system.timezone": (lambda v: v == "Asia/Taipei", "目前只支援 Asia/Taipei"),
    "system.data_dir": (lambda v: isinstance(v, str) and v, "要是資料夾名稱"),
    "system.retention_days": (lambda v: isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 3650, "要是 1～3650 的整數"),
    "system.keep_events": (lambda v: isinstance(v, bool), "要是 true 或 false"),
    "system.privacy_mode": (lambda v: isinstance(v, bool), "要是 true 或 false"),
    "system.voice": (lambda v: isinstance(v, bool), "要是 true 或 false"),
    "system.module_check_sec": (lambda v: _num(v) and 1 <= v <= 600, "要是 1～600 的數字"),
    "system.health_interval_sec": (lambda v: _num(v) and 5 <= v <= 3600, "要是 5～3600 的數字"),
    "system.min_free_gb": (lambda v: _num(v) and v >= 0, "要是 0 以上的數字"),
    "system.cleanup_time": (_is_hhmm, "格式要像 \"03:00\""),
    "discord.dry_run": (lambda v: isinstance(v, bool), "要是 true 或 false"),
    "discord.channels.notify": (lambda v: isinstance(v, str) and v, "要是頻道名稱"),
    "discord.channels.board": (lambda v: isinstance(v, str) and v, "要是頻道名稱"),
    "discord.board_channel_id": (lambda v: isinstance(v, (str, int)), "要是頻道 ID 或空字串"),
    "discord.min_level": (lambda v: v in LEVELS, "只能是 info、warn、urgent"),
    "discord.skip_kinds": (lambda v: isinstance(v, list), "要是清單"),
    "discord.urgent_repeat_min": (lambda v: _num(v) and v > 0, "要是大於 0 的數字"),
    "discord.urgent_repeat_max": (lambda v: isinstance(v, int) and 1 <= v <= 20, "要是 1～20 的整數"),
    "discord.timeout_sec": (lambda v: _num(v) and v > 0, "要是大於 0 的數字"),
    "care.source": (lambda v: isinstance(v, (str, int)), "要是影片路徑或攝影機編號"),
    "care.loop": (lambda v: isinstance(v, bool), "要是 true 或 false"),
    "care.fall_sec": (lambda v: _num(v) and 0.5 <= v <= 60, "要是 0.5～60 的數字"),
    "care.inactive_min": (lambda v: _num(v) and v > 0, "要是大於 0 的數字"),
    "care.move_px": (lambda v: _num(v) and v > 0, "要是大於 0 的數字"),
    "care.activity_every_min": (lambda v: _num(v) and v > 0, "要是大於 0 的數字"),
    "camera.source": (lambda v: isinstance(v, (str, int)), "要是影片路徑或攝影機編號"),
    "camera.loop": (lambda v: isinstance(v, bool), "要是 true 或 false"),
    "camera.merge_gap_sec": (lambda v: _num(v) and v >= 0, "要是 0 以上的數字"),
    "camera.min_visit_sec": (lambda v: _num(v) and v >= 0, "要是 0 以上的數字"),
    "camera.night_start": (_is_hhmm, "格式要像 \"23:00\""),
    "camera.night_end": (_is_hhmm, "格式要像 \"05:00\""),
    "chat.ai_model": (lambda v: isinstance(v, str) and v, "要是模型名稱"),
    "chat.confirm_words": (lambda v: isinstance(v, list) and v, "要是清單"),
    "chat.devices": (lambda v: isinstance(v, list), "要是清單"),
    "meds.timeout_min": (lambda v: _num(v) and v > 0, "要是大於 0 的數字"),
    "meds.test_mode": (lambda v: isinstance(v, bool), "要是 true 或 false"),
    "meds.schedule": (lambda v: isinstance(v, list), "要是清單"),
    "daily.time": (_is_hhmm, "格式要像 \"20:00\""),
    "sos.key": (lambda v: isinstance(v, str) and v, "要是按鍵名稱，例如 F9"),
    "sos.keywords": (lambda v: isinstance(v, list) and v, "要是清單"),
    "sos.cooldown_sec": (lambda v: _num(v) and v >= 0, "要是 0 以上的數字"),
    "routine.days": (lambda v: isinstance(v, int) and 2 <= v <= 60, "要是 2～60 的整數"),
    "routine.wake_tolerance_min": (lambda v: _num(v) and v >= 0, "要是 0 以上的數字"),
    "routine.low_ratio": (lambda v: _num(v) and 0 < v < 1, "要是 0～1 之間的小數"),
    "routine.blocks": (lambda v: isinstance(v, list), "要是清單"),
    "routine.activity_kinds": (lambda v: isinstance(v, list), "要是清單"),
    "web.host": (lambda v: v == "127.0.0.1", "只能是 127.0.0.1（只允許本機連線）"),
    "web.port": (lambda v: isinstance(v, int) and 1024 <= v <= 65535, "要是 1024～65535 的整數"),
}
for _m in MODULE_NAMES:
    RULES[f"modules.{_m}"] = (lambda v: isinstance(v, bool), "要是 true 或 false")


def get_path(data: dict, dotted: str):
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(dotted)
        cur = cur[part]
    return cur


def validate(data) -> list[str]:
    """檢查設定內容，回傳錯誤清單（空清單代表沒問題）。"""
    if not isinstance(data, dict):
        return ["設定檔最外層要是「名稱: 值」的格式"]
    errors = []
    for key, (check, hint) in RULES.items():
        try:
            value = get_path(data, key)
        except KeyError:
            errors.append(f"缺少欄位 {key}")
            continue
        try:
            ok = bool(check(value))
        except Exception:
            ok = False
        if not ok:
            errors.append(f"{key} 的值 {value!r} 不正確：{hint}")
    errors += _check_lists(data)
    return errors


def _check_lists(data: dict) -> list[str]:
    errors = []
    devices = data.get("chat", {}).get("devices") or []
    names = set()
    for i, d in enumerate(devices, 1):
        if not isinstance(d, dict) or not d.get("name"):
            errors.append(f"chat.devices 第 {i} 個裝置缺少 name")
            continue
        if d["name"] in names:
            errors.append(f"chat.devices 的裝置名稱「{d['name']}」重複")
        names.add(d["name"])
        if not isinstance(d.get("dangerous", False), bool):
            errors.append(f"chat.devices「{d['name']}」的 dangerous 要是 true 或 false")
    for i, m in enumerate(data.get("meds", {}).get("schedule") or [], 1):
        if not isinstance(m, dict) or not _is_hhmm(m.get("time")) or not m.get("name"):
            errors.append(f"meds.schedule 第 {i} 筆要有 time（例如 \"08:00\"）與 name")
    for b in data.get("routine", {}).get("blocks") or []:
        mt = re.fullmatch(r"(\d{1,2})-(\d{1,2})", str(b))
        if not mt or not (0 <= int(mt[1]) < int(mt[2]) <= 24):
            errors.append(f"routine.blocks 的「{b}」格式要像 \"08-12\"")
    return errors


# ---------- 讀取 ----------
def _read_yaml(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError([f"找不到設定檔 {path}"])
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f"第 {mark.line + 1} 行" if mark else "某一行"
        problem = getattr(e, "problem", "") or ""
        raise ConfigError([f"{path.name} {where}格式錯誤（{problem}）；常見原因：冒號後面少了空白、縮排不一致、用了全形符號"])


def deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_settings(path: Path | None = None, demo: bool = False) -> dict:
    """讀取並檢查設定；有錯時丟出 ConfigError（含中文說明）。"""
    data = _read_yaml(Path(path) if path else SETTINGS_PATH)
    if demo and DEMO_PATH.exists():
        data = deep_merge(data, _read_yaml(DEMO_PATH))
    errors = validate(data)
    if errors:
        raise ConfigError(errors)
    return data


_cache: dict = {}


def get_settings(demo: bool = False, reload: bool = False) -> dict:
    key = "demo" if demo else "normal"
    if reload or key not in _cache:
        _cache[key] = load_settings(demo=demo)
    return _cache[key]


def _read_env(path: Path) -> dict:
    """讀取 .env（名稱=值）。有裝 python-dotenv 就用它，沒裝也能讀。"""
    if not path.exists():
        return {}
    try:
        from dotenv import dotenv_values
        return {k: (v or "") for k, v in dotenv_values(path, encoding="utf-8").items()}
    except ImportError:
        values = {}
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
        return values


def get_secret(name: str, env_path: Path | None = None) -> str:
    """讀取金鑰：先看 .env，再看系統環境變數；都沒有就回傳空字串。不會印出金鑰內容。"""
    value = _read_env(Path(env_path) if env_path else ENV_PATH).get(name) or os.environ.get(name, "")
    return value.strip()


def data_dir(settings: dict) -> Path:
    p = Path(settings["system"]["data_dir"])
    return p if p.is_absolute() else ROOT / p


# ---------- 管理介面存檔：只改值、保留註解 ----------
def _yaml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return '"' + str(value).replace('"', '\\"') + '"'


def update_yaml_values(text: str, changes: dict[str, object]) -> str:
    """把 settings.yaml 文字中指定欄位（例如 "care.fall_sec"）的值換掉，其他內容（含註解）不動。"""
    lines = text.splitlines(keepends=True)
    stack: list[tuple[int, str]] = []
    remaining = dict(changes)
    pat = re.compile(r"^(\s*)([A-Za-z_][\w]*):(\s*)([^#\n]*?)(\s*)(#.*)?(\r?\n)?$")
    for i, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith("#") or line.lstrip().startswith("-"):
            continue
        m = pat.match(line)
        if not m:
            continue
        indent = len(m[1])
        while stack and stack[-1][0] >= indent:
            stack.pop()
        path = ".".join([k for _, k in stack] + [m[2]])
        if m[4] == "":
            stack.append((indent, m[2]))
            continue
        if path in remaining:
            new_val = _yaml_scalar(remaining.pop(path))
            comment = m[6] or ""
            gap = m[5] if comment else ""
            lines[i] = f"{m[1]}{m[2]}:{m[3] or ' '}{new_val}{gap}{comment}{m[7] or ''}"
    if remaining:
        raise KeyError("設定檔裡找不到這些欄位：" + "、".join(remaining))
    return "".join(lines)


def save_changes(changes: dict[str, object], path: Path | None = None) -> list[str]:
    """先檢查再存檔。回傳錯誤清單；有錯就不存。"""
    path = Path(path) if path else SETTINGS_PATH
    text = path.read_text(encoding="utf-8")
    try:
        new_text = update_yaml_values(text, changes)
    except KeyError as e:
        return [str(e)]
    try:
        data = yaml.safe_load(new_text)
    except yaml.YAMLError as e:
        return [f"存檔後格式會壞掉：{e}"]
    errors = validate(data)
    if errors:
        return errors
    path.write_text(new_text, encoding="utf-8")
    _cache.clear()
    return []


if __name__ == "__main__":
    from core import console
    console.setup()
    try:
        s = load_settings(demo="--demo" in sys.argv)
    except ConfigError as e:
        print(e)
        sys.exit(1)
    on = [m for m in MODULE_NAMES if s["modules"][m]]
    print("設定檔檢查通過。開啟的模組：" + "、".join(on))
    for name in ["DISCORD_WEBHOOK_TEST", "DISCORD_WEBHOOK_BOARD", "DISCORD_BOT_TOKEN", "AI_API_KEY"]:
        print(f"  .env {name}：{'已設定' if get_secret(name) else '未設定'}")
