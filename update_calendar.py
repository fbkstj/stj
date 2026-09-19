import urllib.request
import re
import json
import ssl
from datetime import datetime, timedelta

def fetch_and_convert():
    calendar_ids = [
        "calendar@ymhs.tyc.edu.tw",
        "c_08u857sd2lpto61ipblurdgej8@group.calendar.google.com",
        "c_keqn8cl3cto6ua47odlrhs9qkc@group.calendar.google.com",
        "c_hscldi6ihja5u44matubm1ebi4@group.calendar.google.com",
        "c_csl9j3a43p3hcrs31q3tts21p0@group.calendar.google.com",
        "c_cf8505cff2fdee51a531c7c5e2e4ed7954db783cef6148cd756d0a020b650e22@group.calendar.google.com",
        "c_i0o701vhndfjuqia24d37002qo@group.calendar.google.com",
        "c_lbigaf9hd5kiqpvffs59tvmke8@group.calendar.google.com",
        "c_o68c8e40kufk9b0gjuq4tovc1g@group.calendar.google.com"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    context = ssl._create_unverified_context()
    
    all_events = []
    seen_events = set() # 用於防止多個日曆中出現完全重複的事件

    print(f"開始下載楊梅高中官方 Google 日曆 (共 {len(calendar_ids)} 個子處室日曆)...")
    
    for idx, cal_id in enumerate(calendar_ids, 1):
        # 對 ID 進行 URL 編碼
        encoded_id = urllib.parse.quote_plus(cal_id)
        ics_url = f"https://calendar.google.com/calendar/ical/{encoded_id}/public/basic.ics"
        
        print(f"[{idx}/{len(calendar_ids)}] 正在下載日曆: {cal_id} ...")
        req = urllib.request.Request(ics_url, headers=headers)
        
        try:
            with urllib.request.urlopen(req, context=context) as response:
                content = response.read().decode('utf-8')
        except Exception as e:
            print(f"下載 {cal_id} 失敗，可能該子日曆未公開，錯誤：", e)
            continue
            
        # 解析 VEVENT
        vevents = re.findall(r'BEGIN:VEVENT.*?END:VEVENT', content, re.DOTALL)
        parsed_count = 0
        
        for vevent in vevents:
            summary_m = re.search(r'SUMMARY:(.*?)\r?\n', vevent)
            dtstart_m = re.search(r'DTSTART(?:;VALUE=DATE)?:([0-9T]+)\r?\n', vevent)
            dtend_m = re.search(r'DTEND(?:;VALUE=DATE)?:([0-9T]+)\r?\n', vevent)
            desc_m = re.search(r'DESCRIPTION:(.*?)\r?\n', vevent)
            
            if not summary_m or not dtstart_m:
                continue
                
            summary = summary_m.group(1).strip()
            summary = summary.replace('\\,', ',').replace('\\;', ';').replace('\\n', '\n')
            
            start_str = dtstart_m.group(1).strip()
            end_str = dtend_m.group(1).strip() if dtend_m else start_str
            
            start_date_str = start_str[:8]
            end_date_str = end_str[:8]
            
            try:
                start_date = datetime.strptime(start_date_str, "%Y%m%d")
                end_date = datetime.strptime(end_date_str, "%Y%m%d")
                
                if len(end_str) == 8 or 'T' not in end_str:
                    if end_date > start_date:
                        end_date = end_date - timedelta(days=1)
                
                curr = start_date
                while curr <= end_date:
                    formatted_date = curr.strftime("%Y-%m-%d")
                    
                    # 建立去重的 key
                    event_key = (formatted_date, summary)
                    if event_key not in seen_events:
                        seen_events.add(event_key)
                        all_events.append({
                            "date": formatted_date,
                            "summary": summary,
                            "description": desc_m.group(1).strip() if desc_m else ""
                        })
                    curr += timedelta(days=1)
                    parsed_count += 1
            except Exception as ex:
                continue
        print(f"-> 成功解析出 {parsed_count} 筆事件點。")

    # 按日期排序
    all_events.sort(key=lambda x: x['date'])
    
    # 輸出成 JS 檔案 (繞過 file:/// 協議的 fetch CORS 限制)
    output_file = "ymhs_calendar.js"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("window.YMHS_CALENDAR_DATA = ")
        json.dump(all_events, f, ensure_ascii=False, indent=2)
        f.write(";")
        
    print(f"\n全部完成！共合併與去重解析出 {len(all_events)} 筆行事曆事件，並儲存至 {output_file}！")

if __name__ == "__main__":
    fetch_and_convert()
