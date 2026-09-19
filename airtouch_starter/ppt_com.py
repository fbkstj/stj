"""PowerPoint 程式介面（COM）：讀取頁碼與備忘稿、跳到指定頁或指定標題的投影片。

快捷鍵只能「按下一頁」，透過 PowerPoint 提供的程式介面，才能知道「現在第幾頁、總共幾頁」，
也能直接跳到標題含有某個詞的投影片。電腦要安裝 Microsoft PowerPoint（Office），
沒有安裝時這些功能會自動停用，快捷鍵照常可以用。

常用物件：
  Application.SlideShowWindows(1)        放映中的視窗
    .View.Slide.SlideIndex               目前是第幾張
    .View.GotoSlide(n)                   跳到第 n 張
    .Presentation.Slides.Count           總張數
  Slide.Shapes.Title.TextFrame.TextRange.Text     投影片標題
  Slide.NotesPage.Shapes                          備忘稿頁面（內文版面配置區的類型是 2）
"""
PP_PLACEHOLDER_BODY = 2


def _app():
    import win32com.client
    return win32com.client.GetActiveObject("PowerPoint.Application")


def slide_title(slide):
    try:
        if slide.Shapes.HasTitle:
            text = slide.Shapes.Title.TextFrame.TextRange.Text.strip()
            if text:
                return text
        for shape in slide.Shapes:
            if shape.HasTextFrame and shape.TextFrame.HasText:
                return shape.TextFrame.TextRange.Text.strip().splitlines()[0]
    except Exception:
        pass
    return ""


def slide_notes(slide):
    try:
        for shape in slide.NotesPage.Shapes:
            if shape.Type == 14 and shape.PlaceholderFormat.Type == PP_PLACEHOLDER_BODY:   # 14＝版面配置區
                return shape.TextFrame.TextRange.Text.strip()
    except Exception:
        pass
    return ""


def find_slide(presentation, keyword):
    """先找標題含有關鍵詞的投影片，找不到再找內文；回傳頁碼或 None。"""
    key = keyword.strip().lower()
    slides = presentation.Slides
    for i in range(1, slides.Count + 1):
        if key in slide_title(slides(i)).lower():
            return i
    for i in range(1, slides.Count + 1):
        for shape in slides(i).Shapes:
            try:
                if shape.HasTextFrame and key in shape.TextFrame.TextRange.Text.lower():
                    return i
            except Exception:
                continue
    return None


def _current(app):
    """回傳 (presentation, view, 目前頁碼, 是否放映中)。"""
    if app.SlideShowWindows.Count > 0:
        win = app.SlideShowWindows(1)
        view = win.View
        try:
            index = view.Slide.SlideIndex
        except Exception:                 # 放映結束後的黑畫面沒有 Slide
            index = view.CurrentShowPosition
        return win.Presentation, view, index, True
    if app.Presentations.Count > 0:
        view = app.ActiveWindow.View
        return app.ActivePresentation, view, view.Slide.SlideIndex, False
    return None, None, 0, False


def state():
    """回傳 dict(index, total, title, notes, show) 或 None（沒有開啟 PowerPoint）。"""
    try:
        app = _app()
        pres, _, index, show = _current(app)
        if pres is None:
            return None
        slide = pres.Slides(index)
        return {"index": index, "total": pres.Slides.Count, "title": slide_title(slide),
                "notes": slide_notes(slide), "show": show}
    except Exception:
        return None


def goto(n):
    """跳到第 n 張，回傳 (是否成功, 訊息)；沒有 PowerPoint 時回傳 (None, 原因)，讓呼叫端改用按鍵。"""
    try:
        app = _app()
        pres, view, _, show = _current(app)
    except Exception as e:
        return None, f"無法連到 PowerPoint：{e}"
    if pres is None:
        return None, "PowerPoint 沒有開啟簡報"
    total = pres.Slides.Count
    if not 1 <= n <= total:
        return False, f"沒有第 {n} 頁（共 {total} 頁）"
    view.GotoSlide(n)
    return True, f"跳到第 {n}／{total} 頁" + ("" if show else "（編輯畫面）")


def goto_title(keyword):
    try:
        app = _app()
        pres, _, _, _ = _current(app)
    except Exception as e:
        return False, f"無法連到 PowerPoint：{e}"
    if pres is None:
        return False, "PowerPoint 沒有開啟簡報"
    n = find_slide(pres, keyword)
    if n is None:
        return False, f"找不到含有「{keyword}」的投影片"
    ok, msg = goto(n)
    return bool(ok), f"「{keyword}」→ {msg}"
