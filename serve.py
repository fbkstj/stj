import http.server, functools, os, json, fitz

DIR = os.path.dirname(os.path.abspath(__file__))

class CORSHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_POST(self):
        if self.path == "/api/generate_pdf":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                subject = data.get("subject", "1")
                cpld = data.get("cpld", "E")
                display = data.get("display", "N")
                station_start = int(data.get("station_start", 5))
                test_no_start = data.get("test_no_start", "07240001")
                candidate_count = int(data.get("candidate_count", 20))
                
                # 合併 PDF 生成邏輯
                final_doc = fitz.open()
                BASE_DIR = os.path.dirname(os.path.abspath(__file__))
                INPUT_PDF = os.path.join(BASE_DIR, "數位電子乙級術科測試評審表.pdf")
                PAGE2_PDF = os.path.join(BASE_DIR, "試題動作要求_排版.pdf")
                FONT_PATH = os.path.join(BASE_DIR, "DFT_YF3.ttf")
                
                # Checkbox 位置定義
                SUBJECT_BBOX = {
                    "1": [125.66, 106.5, 136.7, 117.54],
                    "2": [125.66, 123.18, 136.7, 134.22],
                }
                CPLD_BBOX = {
                    "A": [125.66, 140.34, 136.7, 151.38],
                    "B": [218.45, 140.34, 229.49, 151.38],
                    "C": [125.66, 157.02, 136.7, 168.06],
                    "D": [218.33, 157.02, 229.37, 168.06],
                    "E": [125.66, 173.82, 136.7, 184.86],
                }
                DISPLAY_BBOX = {
                    "J": [402.07, 140.34, 413.11, 151.38],
                    "K": [477.70, 140.34, 488.74, 151.38],
                    "L": [402.07, 157.02, 413.11, 168.06],
                    "M": [477.70, 157.02, 488.74, 168.06],
                    "N": [402.07, 173.82, 413.11, 184.86],
                }
                
                prefix = test_no_start[:4]
                start_num = int(test_no_start[4:])
                
                for i in range(candidate_count):
                    test_no = f"{prefix}{start_num + i:04d}"
                    station_val = station_start + i
                    while station_val > 20:
                        station_val -= 20
                    station_str = f"{station_val:02d}"
                    
                    candidate_doc = fitz.open(INPUT_PDF)
                    candidate_page = candidate_doc[0]
                    candidate_page.insert_font(fontname="yafeng", fontfile=FONT_PATH)
                    
                    # 填入文字
                    candidate_page.insert_text(fitz.Point(140, 96.0), test_no, fontname="helv", fontsize=13.0, color=(0,0,0))
                    candidate_page.insert_text(fitz.Point(370, 71.5), station_str, fontname="helv", fontsize=15.0, color=(0,0,0))
                    
                    # 填黑勾選框
                    s_rect = SUBJECT_BBOX.get(subject)
                    if s_rect:
                        candidate_page.draw_rect(fitz.Rect(*s_rect), color=(0,0,0), fill=(0,0,0), width=0)
                    c_rect = CPLD_BBOX.get(cpld)
                    if c_rect:
                        candidate_page.draw_rect(fitz.Rect(*c_rect), color=(0,0,0), fill=(0,0,0), width=0)
                    d_rect = DISPLAY_BBOX.get(display)
                    if d_rect:
                        candidate_page.draw_rect(fitz.Rect(*d_rect), color=(0,0,0), fill=(0,0,0), width=0)
                        
                    # 監評簽名「簡樹桐」置中
                    candidate_page.insert_text(fitz.Point(150, 738), "簡樹桐", fontname="yafeng", fontsize=26, color=(0,0,0))
                    
                    final_doc.insert_pdf(candidate_doc, from_page=0, to_page=0)
                    candidate_doc.close()
                    
                    req_doc = fitz.open(PAGE2_PDF)
                    final_doc.insert_pdf(req_doc)
                    req_doc.close()
                
                pdf_bytes = final_doc.write()
                final_doc.close()
                
                # 回傳 PDF 串流
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(pdf_bytes)))
                self.end_headers()
                self.wfile.write(pdf_bytes)
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(f"Error generating PDF: {str(e)}".encode('utf-8'))
        else:
            super().do_POST()

handler = functools.partial(CORSHandler, directory=DIR)
http.server.HTTPServer(("127.0.0.1", 18456), handler).serve_forever()
