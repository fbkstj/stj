import sys
import os
import base64

def save_certificate(b64_string, filename="研習證明書.pdf"):
    """將 Base64 編碼的二進制 PDF 儲存至本機與 Downloads"""
    pdf_bytes = base64.b64decode(b64_string)
    
    # 儲存至當前工作目錄
    local_path = os.path.abspath(filename)
    with open(local_path, "wb") as f:
        f.write(pdf_bytes)
        
    # 同步儲存至使用者「下載」資料夾
    downloads_dir = os.path.join(os.environ.get("USERPROFILE", "."), "Downloads")
    dl_path = os.path.join(downloads_dir, filename)
    with open(dl_path, "wb") as f:
        f.write(pdf_bytes)
        
    print(f"✅ 證書成功儲存 ({len(pdf_bytes)} 位元組):")
    print(f"   本機路徑: {local_path}")
    print(f"   下載路徑: {dl_path}")

if __name__ == "__main__":
    if len(sys.argv) > 2:
        save_certificate(sys.argv[1], sys.argv[2])
    elif len(sys.argv) > 1:
        save_certificate(sys.argv[1])
    else:
        print("用法: python save_pdf.py <base64_string> [filename.pdf]")
