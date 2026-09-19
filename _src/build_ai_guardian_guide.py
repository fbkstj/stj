"""產生 ai_guardian_project_guide.html：把程式包裡的 .py 內容嵌進模板的 {{路徑}}。

改手冊文字 → 改 ai_guardian_guide_template.html；改程式 → 改 ai_guardian_starter/ 裡的檔案。
兩種都要重新執行：python _src/build_ai_guardian_guide.py
"""
import html
import pathlib
import re

src = pathlib.Path(__file__).resolve().parent
site = src.parent
pack = site / "ai_guardian_starter"

tpl = (src / "ai_guardian_guide_template.html").read_text(encoding="utf-8")


def embed(m):
    code = (pack / m.group(1)).read_text(encoding="utf-8").rstrip()
    return html.escape(code, quote=False)


page = re.sub(r"\{\{([\w./]+)\}\}", embed, tpl)
assert "{{" not in page
(site / "ai_guardian_project_guide.html").write_text(page, encoding="utf-8")
print("ai_guardian_project_guide.html", len(page))
