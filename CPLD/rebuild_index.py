import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HTML = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>數位乙級 CPLD Quartus 操作教學</title>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&amp;display=swap" rel="stylesheet">
  <style>
    :root{--bg:#0f1117;--sf:#1a1d27;--sf2:#22263a;--bd:#2e3350;--a1:#6c63ff;--a2:#00d4aa;--tx:#e8eaf0;--mu:#8b92a8;}
    *{margin:0;padding:0;box-sizing:border-box;}
    body{font-family:"Noto Sans TC","Microsoft JhengHei",sans-serif;background:var(--bg);color:var(--tx);min-height:100vh;}
    header{background:linear-gradient(135deg,#1a1d27,#12152a);border-bottom:1px solid var(--bd);padding:0 2rem;display:flex;align-items:center;justify-content:space-between;height:64px;position:sticky;top:0;z-index:100;}
    .logo{display:flex;align-items:center;gap:12px;}
    .logo-icon{width:38px;height:38px;background:linear-gradient(135deg,#6c63ff,#00d4aa);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px;}
    .logo-text{font-size:1.1rem;font-weight:700;}
    .logo-sub{font-size:.72rem;color:var(--mu);margin-top:2px;}
    .back-btn{color:var(--mu);text-decoration:none;font-size:.9rem;font-weight:500;padding:8px 14px;border-radius:8px;border:1px solid var(--bd);transition:all .2s;}
    .back-btn:hover{color:var(--tx);background:var(--sf2);border-color:var(--a1);}
    .hero{background:linear-gradient(160deg,#12152a,#1a1d27,#0f1117);padding:60px 2rem 50px;text-align:center;position:relative;overflow:hidden;}
    .hero::before{content:"";position:absolute;top:-120px;left:50%;transform:translateX(-50%);width:600px;height:600px;background:radial-gradient(circle,rgba(108,99,255,.12),transparent 70%);pointer-events:none;}
    .hero-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(108,99,255,.15);border:1px solid rgba(108,99,255,.4);color:#a89fff;border-radius:50px;padding:5px 14px;font-size:.8rem;font-weight:600;margin-bottom:20px;}
    .hero h1{font-size:clamp(1.8rem,4vw,2.8rem);font-weight:900;background:linear-gradient(135deg,#fff 30%,#a89fff 70%,#00d4aa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.2;margin-bottom:16px;}
    .hero p{color:var(--mu);font-size:1rem;max-width:560px;margin:0 auto 32px;line-height:1.7;}
    .hero-stats{display:flex;justify-content:center;gap:32px;flex-wrap:wrap;}
    .stat-num{font-size:1.6rem;font-weight:900;color:var(--a2);text-align:center;}
    .stat-lbl{font-size:.75rem;color:var(--mu);margin-top:2px;text-align:center;}
    .nav-tabs{display:flex;justify-content:center;gap:12px;padding:28px 2rem 0;border-bottom:1px solid var(--bd);}
    .tab-btn{padding:10px 28px;border:none;cursor:pointer;background:transparent;color:var(--mu);font-size:1rem;font-weight:600;font-family:inherit;border-bottom:3px solid transparent;margin-bottom:-1px;transition:all .2s;display:flex;align-items:center;gap:8px;}
    .tab-btn:hover{color:var(--tx);}
    .tab-btn.active{color:var(--a1);border-bottom-color:var(--a1);}
    .tab-indicator{font-size:.72rem;background:var(--a1);color:#fff;border-radius:50px;padding:2px 8px;font-weight:700;}
    .tab-indicator2{background:var(--a2);color:#0f1117;}
    main{max-width:1100px;margin:0 auto;padding:40px 2rem 80px;}
    .topic-section{display:none;}
    .topic-section.active{display:block;}
    .section-header{display:flex;align-items:center;gap:16px;margin-bottom:32px;}
    .section-num{width:52px;height:52px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:1.5rem;font-weight:900;flex-shrink:0;}
    .section-title{font-size:1.5rem;font-weight:800;}
    .section-sub{color:var(--mu);font-size:.88rem;margin-top:4px;}
    .video-card{background:var(--sf);border:1px solid var(--bd);border-radius:16px;overflow:hidden;margin-bottom:28px;box-shadow:0 8px 32px rgba(0,0,0,.4);}
    .video-card-header{padding:16px 20px;border-bottom:1px solid var(--bd);display:flex;align-items:center;gap:10px;}
    .video-icon{width:32px;height:32px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;}
    .video-card-title{font-weight:700;font-size:1rem;}
    .video-card-meta{color:var(--mu);font-size:.8rem;margin-top:2px;}
    video{width:100%;display:block;background:#000;max-height:520px;}
    .video-footer{padding:12px 20px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;}
    .tag{font-size:.75rem;font-weight:600;padding:3px 10px;border-radius:50px;}
    .tag-purple{background:rgba(108,99,255,.15);color:#a89fff;border:1px solid rgba(108,99,255,.3);}
    .tag-green{background:rgba(0,212,170,.12);color:#00d4aa;border:1px solid rgba(0,212,170,.3);}
    .tag-yellow{background:rgba(251,191,36,.12);color:#fbbf24;border:1px solid rgba(251,191,36,.3);}
    .diagram-card{background:var(--sf);border:1px solid var(--bd);border-radius:16px;overflow:hidden;margin-bottom:28px;}
    .diagram-card-header{padding:14px 20px;border-bottom:1px solid var(--bd);font-weight:700;font-size:.95rem;display:flex;align-items:center;gap:8px;}
    .diagram-card img{width:100%;display:block;background:#fff;cursor:zoom-in;transition:transform .2s;}
    .diagram-card img:hover{transform:scale(1.01);}
    .info-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:28px;}
    .info-item{background:var(--sf);border:1px solid var(--bd);border-radius:12px;padding:18px 20px;}
    .info-item-label{font-size:.75rem;font-weight:600;color:var(--mu);text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;}
    .info-item-value{font-size:.95rem;font-weight:700;color:var(--tx);line-height:1.5;}
    .component-list{background:var(--sf);border:1px solid var(--bd);border-radius:16px;padding:20px 24px;margin-bottom:28px;}
    .component-list h3{font-size:.95rem;font-weight:700;margin-bottom:14px;display:flex;align-items:center;gap:8px;}
    .component-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;}
    .component-chip{display:flex;align-items:center;gap:8px;background:var(--sf2);border:1px solid var(--bd);border-radius:8px;padding:8px 12px;font-size:.85rem;font-weight:500;}
    .chip-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;}
    .lecture-bar{background:linear-gradient(135deg,rgba(108,99,255,.1),rgba(0,212,170,.08));border:1px solid var(--bd);border-radius:16px;padding:20px 24px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:28px;}
    .lecture-info h4{font-size:1rem;font-weight:700;}
    .lecture-info p{color:var(--mu);font-size:.83rem;margin-top:4px;}
    .lecture-btn{display:inline-flex;align-items:center;gap:8px;color:#fff;text-decoration:none;padding:10px 22px;border-radius:10px;font-weight:700;font-size:.9rem;transition:all .2s;}
    .lecture-btn:hover{transform:translateY(-2px);}
    .lecture-btn-1{background:linear-gradient(135deg,#6c63ff,#9c89ff);box-shadow:0 4px 16px rgba(108,99,255,.3);}
    .lecture-btn-2{background:linear-gradient(135deg,#00d4aa,#00b48a);box-shadow:0 4px 16px rgba(0,212,170,.3);}
    footer{text-align:center;padding:28px;border-top:1px solid var(--bd);color:var(--mu);font-size:.82rem;}
    .lightbox{display:none;position:fixed;inset:0;background:rgba(0,0,0,.92);z-index:999;align-items:center;justify-content:center;padding:20px;}
    .lightbox.open{display:flex;}
    .lightbox img{max-width:95vw;max-height:90vh;border-radius:8px;object-fit:contain;}
    .lightbox-close{position:absolute;top:20px;right:24px;font-size:2rem;color:#fff;cursor:pointer;background:none;border:none;line-height:1;}
  </style>
</head>
<body>
<header>
  <div class="logo">
    <div class="logo-icon">⚡</div>
    <div><div class="logo-text">CPLD Quartus 教學</div><div class="logo-sub">數位電子乙級技術士</div></div>
  </div>
  <a href="../index.html" class="back-btn">← 返回首頁</a>
</header>
<div class="hero">
  <div class="hero-badge">🎓 114年 數位乙級檢定</div>
  <h1>Quartus MegaWizard<br>精靈 CPLD 實作教學</h1>
  <p>使用 Altera Quartus II MegaWizard Plug-In Manager 精靈元件，快速完成數位乙級第一題與第二題的 CPLD 電路設計與 PCB 佈線。</p>
  <div class="hero-stats">
    <div><div class="stat-num">2</div><div class="stat-lbl">題組教學</div></div>
    <div><div class="stat-num">2</div><div class="stat-lbl">操作影片</div></div>
    <div><div class="stat-num">11</div><div class="stat-lbl">講義頁面</div></div>
    <div><div class="stat-num">AHDL</div><div class="stat-lbl">設計語言</div></div>
  </div>
</div>
<div class="nav-tabs">
  <button class="tab-btn active" onclick="switchTab(1)" id="tab1">🔷 第一題 <span class="tab-indicator">B組</span></button>
  <button class="tab-btn" onclick="switchTab(2)" id="tab2">🟢 第二題 <span class="tab-indicator tab-indicator2">E組</span></button>
</div>
<main>
  <!-- 第一題 -->
  <div class="topic-section active" id="section1">
    <div class="section-header">
      <div class="section-num" style="background:linear-gradient(135deg,#6c63ff,#9c89ff);">①</div>
      <div>
        <div class="section-title">第一題：七段顯示器循環計數（B組）</div>
        <div class="section-sub">計數器除頻 ／ 2TO4 解碼器 ／ MUX4TO1 多工器 ／ 8bit 陣列輸出</div>
      </div>
    </div>
    <div class="info-grid">
      <div class="info-item"><div class="info-item-label">📋 題目分組</div><div class="info-item-value">114年數位乙級 — B 組</div></div>
      <div class="info-item"><div class="info-item-label">🔧 設計工具</div><div class="info-item-value">Quartus II + MegaWizard 精靈</div></div>
      <div class="info-item"><div class="info-item-label">📡 輸出腳位</div><div class="info-item-value">D0~D3（PIN 4~8）DSS[7..0]（PIN 9~31）</div></div>
      <div class="info-item"><div class="info-item-label">⏱️ 時脈設定</div><div class="info-item-value">CLK → 4MHz ÷ 2¹² = 1KHz</div></div>
    </div>
    <div class="component-list">
      <h3>🧩 使用的 MegaWizard 精靈元件</h3>
      <div class="component-grid">
        <div class="component-chip"><div class="chip-dot" style="background:#6c63ff;"></div>Up Counter（上數計數器）</div>
        <div class="component-chip"><div class="chip-dot" style="background:#00d4aa;"></div>2TO4 解碼器</div>
        <div class="component-chip"><div class="chip-dot" style="background:#fbbf24;"></div>MUX4TO1 多工器</div>
        <div class="component-chip"><div class="chip-dot" style="background:#ff6b6b;"></div>8bit 常數 LPM_CONSTANT</div>
        <div class="component-chip"><div class="chip-dot" style="background:#a89fff;"></div>INPUT（PIN_43 CLK）</div>
        <div class="component-chip"><div class="chip-dot" style="background:#60efbc;"></div>OUTPUT（D0~D3, DSS）</div>
      </div>
    </div>
    <div class="diagram-card">
      <div class="diagram-card-header">🖼️ CPLD 電路方塊圖（第一題）<span style="color:var(--mu);font-size:.8rem;font-weight:400;margin-left:8px;">點擊可放大</span></div>
      <img src="數乙第一題CPLD.png" alt="第一題 CPLD 電路圖" onclick="openLightbox(this.src)" title="點擊放大">
    </div>
    <div class="video-card">
      <div class="video-card-header">
        <div class="video-icon" style="background:rgba(108,99,255,.2);">▶</div>
        <div>
          <div class="video-card-title">📹 操作示範影片 — 第一題 PCB 佈線（B組）</div>
          <div class="video-card-meta">114年數位乙級檢定 · 精靈繪圖設計 + PCB 完整流程</div>
        </div>
      </div>
      <video controls preload="metadata">
        <source src="114年數位乙級檢定第1題精靈繪圖設計-PCB-B組.mp4" type="video/mp4">
        您的瀏覽器不支援 HTML5 video。
      </video>
      <div class="video-footer">
        <span class="tag tag-purple">MegaWizard 精靈設計</span>
        <span class="tag tag-yellow">Quartus II</span>
        <span class="tag tag-green">PCB 佈線</span>
        <span class="tag tag-purple">AHDL</span>
      </div>
    </div>
    <div class="lecture-bar">
      <div class="lecture-info">
        <h4>📖 Altera MegaWizard AHDL Keyboard 講義</h4>
        <p>包含 MegaWizard 精靈各元件操作說明、AHDL 語法範例與鍵盤輸入設計（11 頁）</p>
      </div>
      <a href="megawizard_slides.html" class="lecture-btn lecture-btn-1">📖 線上閱讀講義</a>
    </div>
  </div>
  <!-- 第二題 -->
  <div class="topic-section" id="section2">
    <div class="section-header">
      <div class="section-num" style="background:linear-gradient(135deg,#00d4aa,#00b48a);color:#0f1117;">②</div>
      <div>
        <div class="section-title">第二題：七段顯示器鎖存顯示（E組）</div>
        <div class="section-sub">除頻計數器 ／ 2TO4 解碼器 ／ 4位元鎖存器 ／ 自訂七段顯示元件</div>
      </div>
    </div>
    <div class="info-grid">
      <div class="info-item"><div class="info-item-label">📋 題目分組</div><div class="info-item-value">114年數位乙級 — E 組</div></div>
      <div class="info-item"><div class="info-item-label">🔧 設計工具</div><div class="info-item-value">Quartus II + MegaWizard 精靈</div></div>
      <div class="info-item"><div class="info-item-label">📡 輸出腳位</div><div class="info-item-value">R0~R3（PIN 11~16）a~g（PIN 27~37）</div></div>
      <div class="info-item"><div class="info-item-label">⏱️ 時脈設定</div><div class="info-item-value">CLK → 4MHz ÷ 2¹² = 1KHz，clk_en 由 OR3 控制</div></div>
    </div>
    <div class="component-list">
      <h3>🧩 使用的 MegaWizard 精靈元件</h3>
      <div class="component-grid">
        <div class="component-chip"><div class="chip-dot" style="background:#00d4aa;"></div>Up Counter（上數計數器）</div>
        <div class="component-chip"><div class="chip-dot" style="background:#6c63ff;"></div>2TO4 解碼器</div>
        <div class="component-chip"><div class="chip-dot" style="background:#fbbf24;"></div>Latch4（4位元鎖存器）</div>
        <div class="component-chip"><div class="chip-dot" style="background:#ff6b6b;"></div>7Segment（七段顯示自訂元件）</div>
        <div class="component-chip"><div class="chip-dot" style="background:#a89fff;"></div>OR3 邏輯閘</div>
        <div class="component-chip"><div class="chip-dot" style="background:#60efbc;"></div>INPUT C0/C1/C2（PIN 6/8/9）</div>
      </div>
    </div>
    <div class="diagram-card">
      <div class="diagram-card-header">🖼️ CPLD 電路方塊圖（第二題）<span style="color:var(--mu);font-size:.8rem;font-weight:400;margin-left:8px;">點擊可放大</span></div>
      <img src="數乙第二題CPLD.png" alt="第二題 CPLD 電路圖" onclick="openLightbox(this.src)" title="點擊放大">
    </div>
    <div class="video-card">
      <div class="video-card-header">
        <div class="video-icon" style="background:rgba(0,212,170,.2);">▶</div>
        <div>
          <div class="video-card-title">📹 操作示範影片 — 第二題 PCB 佈線（E組）</div>
          <div class="video-card-meta">114年數位乙級檢定 · 精靈繪圖設計 + PCB 完整流程</div>
        </div>
      </div>
      <video controls preload="metadata">
        <source src="114年數位乙級檢定第2題精靈繪圖設計-PCB-E組.mp4" type="video/mp4">
        您的瀏覽器不支援 HTML5 video。
      </video>
      <div class="video-footer">
        <span class="tag tag-green">MegaWizard 精靈設計</span>
        <span class="tag tag-yellow">Quartus II</span>
        <span class="tag tag-green">PCB 佈線</span>
        <span class="tag tag-purple">自訂七段元件</span>
      </div>
    </div>
    <div class="lecture-bar">
      <div class="lecture-info">
        <h4>📖 Altera MegaWizard AHDL Keyboard 講義</h4>
        <p>包含 MegaWizard 精靈各元件操作說明、AHDL 語法範例與鍵盤輸入設計（11 頁）</p>
      </div>
      <a href="megawizard_slides.html" class="lecture-btn lecture-btn-2">📖 線上閱讀講義</a>
    </div>
  </div>
</main>
<footer>楊梅高中 實習處 · 數位電子乙級 CPLD 教學資源 · Quartus II MegaWizard</footer>
<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <button class="lightbox-close" onclick="closeLightbox()">✕</button>
  <img id="lightbox-img" src="" alt="放大圖">
</div>
<script>
  function switchTab(n) {
    document.querySelectorAll(".topic-section").forEach(s => s.classList.remove("active"));
    document.querySelectorAll(".tab-btn").forEach(b => { b.classList.remove("active"); b.style.color = ""; });
    document.getElementById("section"+n).classList.add("active");
    var btn = document.getElementById("tab"+n);
    btn.classList.add("active");
    btn.style.color = n===2 ? "#00d4aa" : "";
    document.querySelectorAll("video").forEach(v => v.pause());
  }
  function openLightbox(src) { document.getElementById("lightbox-img").src=src; document.getElementById("lightbox").classList.add("open"); }
  function closeLightbox() { document.getElementById("lightbox").classList.remove("open"); }
  document.addEventListener("keydown", e => { if(e.key==="Escape") closeLightbox(); });
</script>
</body>
</html>'''

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(HTML)
print('OK', len(HTML), 'bytes')
