# -*- coding: utf-8 -*-
import re, io, os

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
years = ['115', '114', '113', '112', '110']

def fname(y, premium):
    if y == '110':
        return 'coursemap_premium.html' if premium else 'coursemap.html'
    return ('coursemap_premium%s.html' if premium else 'coursemap%s.html') % y

def read(name):
    return io.open(os.path.join(base, name), encoding='utf-8').read()

# ---------- shared print CSS (identical across years) ----------
print_css = re.search(r'<style type="text/css">([\s\S]*?)</style>', read('coursemap115.html')).group(1)

def print_inner(y):
    src = read(fname(y, False))
    m = re.search(r'<div class="a4">([\s\S]*?)</div>\s*</div>\s*</body>', src)
    return m.group(1)

# ---------- premium shared CSS ----------
psrc0 = read('coursemap_premium115.html')
pcss = re.search(r'<style type="text/css">([\s\S]*?)</style>', psrc0).group(1)
pcss = pcss.replace(':root', '.pmap')
pcss = re.sub(r'(?m)^body\s*\{', '.pmap {', pcss)
pcss = pcss.replace('cmap', 'pmap')
pcss = ("@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Noto+Sans+TC:wght@300;400;500;700;900&display=swap');\n"
        + pcss
        + "\n.ptab{position:absolute;opacity:0;pointer-events:none}\n")

def premium_inner(y):
    src = read(fname(y, True))
    body = re.search(r'<body>([\s\S]*?)</body>', src).group(1)
    body = re.sub(r'<script>[\s\S]*?</script>', '', body)
    body = body.replace('cmap', 'pmap')
    # replace dept switcher buttons with labels
    dept = ('<div class="switcher">'
            '<label class="switcher-btn" for="d%s-all">全部科別</label>'
            '<label class="switcher-btn" for="d%s-elec">電子科</label>'
            '<label class="switcher-btn" for="d%s-info">資訊科</label>'
            '</div>') % (y, y, y)
    dom = ('<div class="switcher">'
           '<label class="switcher-btn" for="m%s-all">全部領域</label>'
           '<label class="switcher-btn" for="m%s-chip">晶片設計領域</label>'
           '<label class="switcher-btn" for="m%s-micro">微電腦應用領域</label>'
           '</div>') % (y, y, y)
    body = re.sub(r'<div class="switcher" id="deptSwitcher">[\s\S]*?</div>', dept, body, count=1)
    body = re.sub(r'<div class="switcher" id="domainSwitcher">[\s\S]*?</div>', dom, body, count=1)
    # insert radios right after the .pmap open tag
    radios = ('<input class="ptab" id="d%s-all" name="d%s" type="radio" checked="checked" />'
              '<input class="ptab" id="d%s-elec" name="d%s" type="radio" />'
              '<input class="ptab" id="d%s-info" name="d%s" type="radio" />'
              '<input class="ptab" id="m%s-all" name="m%s" type="radio" checked="checked" />'
              '<input class="ptab" id="m%s-chip" name="m%s" type="radio" />'
              '<input class="ptab" id="m%s-micro" name="m%s" type="radio" />') % ((y, y) * 6)
    body = body.replace('<div class="pmap">', '<div class="pmap">' + radios, 1)
    return body.strip()

def premium_rules(y):
    return (
        '#d{y}-elec:checked ~ .a4 .row-info{{display:none}}'
        '#d{y}-info:checked ~ .a4 .row-elec{{display:none}}'
        '#m{y}-chip:checked ~ .a4 .chip[data-domain="micro"],#m{y}-micro:checked ~ .a4 .chip[data-domain="chip"]{{opacity:0.15;filter:grayscale(80%) blur(0.5px)}}'
        '#m{y}-chip:checked ~ .a4 .chip[data-domain="chip"],#m{y}-micro:checked ~ .a4 .chip[data-domain="micro"]{{transform:scale(1.03);box-shadow:0 4px 10px rgba(0,0,0,0.15);border-color:currentColor}}'
        '#d{y}-all:checked ~ .a4 label[for=d{y}-all],#d{y}-elec:checked ~ .a4 label[for=d{y}-elec],#d{y}-info:checked ~ .a4 label[for=d{y}-info],'
        '#m{y}-all:checked ~ .a4 label[for=m{y}-all],#m{y}-chip:checked ~ .a4 label[for=m{y}-chip],#m{y}-micro:checked ~ .a4 label[for=m{y}-micro]'
        '{{background-color:var(--head);color:#fff;box-shadow:0 4px 10px rgba(13,148,136,0.25)}}'
    ).format(y=y)

# ---------- outer shell ----------
outer_css = (
  '.mapall{font-family:"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif}'
  '.mapall .gtab{position:absolute;opacity:0;pointer-events:none}'
  '.mapall .gybtns{display:flex;flex-wrap:wrap;gap:0.6rem;justify-content:center;margin:10px 0 14px}'
  '.mapall .gybtn{cursor:pointer;font-size:1.05rem;color:#0e7a6f;background:#fff;border:2px solid #cfd8cf;border-radius:14px;padding:8px 20px;line-height:1.15;text-align:center;transition:all 0.15s ease}'
  '.mapall .gybtn:hover{border-color:#0e7a6f}'
  '.mapall .gpanel{display:none}'
  '.mapall .vbtns{display:flex;gap:0.5rem;justify-content:center;margin:0 0 12px}'
  '.mapall .vbtn{cursor:pointer;font-size:0.9rem;color:#5b6b78;background:#fff;border:1px solid #cfd8cf;border-radius:999px;padding:5px 16px;transition:all 0.15s ease}'
  '.mapall .vbtn:hover{border-color:#0e7a6f;color:#0e7a6f}'
  '.mapall .vpanel{display:none}'
)
for y in years:
    outer_css += ('#gy{y}:checked ~ .gpanel.gy{y}p{{display:block}}'
                  '#gy{y}:checked ~ .gybtns label[for=gy{y}]{{background:#0e7a6f;color:#fff;border-color:#0e7a6f}}').format(y=y)
    outer_css += ('#v{y}p:checked ~ .vpanel.v{y}pp{{display:block}}'
                  '#v{y}i:checked ~ .vpanel.v{y}ip{{display:block}}'
                  '#v{y}p:checked ~ .vbtns label[for=v{y}p]{{background:#0e7a6f;color:#fff;border-color:#0e7a6f}}'
                  '#v{y}i:checked ~ .vbtns label[for=v{y}i]{{background:#0e7a6f;color:#fff;border-color:#0e7a6f}}').format(y=y)

prem_rules = ''.join(premium_rules(y) for y in years)

parts = []
parts.append('<style type="text/css">' + print_css + outer_css + pcss + prem_rules + '</style>')
parts.append('<div class="mapall">')
for i, y in enumerate(years):
    ck = ' checked="checked"' if i == 0 else ''
    parts.append('<input class="gtab" id="gy%s" name="gy" type="radio"%s />' % (y, ck))
parts.append('<div class="gybtns">' + ''.join(
    '<label class="gybtn" for="gy%s">%s學年入學</label>' % (y, y) for y in years) + '</div>')
for y in years:
    parts.append('<div class="gpanel gy%sp">' % y)
    parts.append('<input class="gtab" id="v%sp" name="v%s" type="radio" checked="checked" />' % (y, y))
    parts.append('<input class="gtab" id="v%si" name="v%s" type="radio" />' % (y, y))
    parts.append('<div class="vbtns">'
                 '<label class="vbtn" for="v%sp">列印版</label>'
                 '<label class="vbtn" for="v%si">互動版</label>'
                 '</div>' % (y, y))
    parts.append('<div class="vpanel v%spp"><div class="cmap"><div class="a4">%s</div></div></div>' % (y, print_inner(y)))
    parts.append('<div class="vpanel v%sip">%s</div>' % (y, premium_inner(y)))
    parts.append('</div>')
parts.append('</div>')

out = '\n'.join(parts)
io.open(os.path.join(base, 'coursemap_all2.html'), 'w', encoding='utf-8').write(out)
print('written', len(out))
