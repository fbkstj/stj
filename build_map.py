import re, io, os

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')
years = ['115', '114', '113', '112']

# take CSS from 115 (identical across years), strip outer body/head
src115 = io.open(os.path.join(base, 'coursemap115.html'), encoding='utf-8').read()
css = re.search(r'<style type="text/css">([\s\S]*?)</style>', src115).group(1)
# remove @media print page rule? keep it. Keep .cmap rules as-is.

panels = []
btns = []
inputs = []
tabcss = []
for i, y in enumerate(years):
    src = io.open(os.path.join(base, 'coursemap%s.html' % y), encoding='utf-8').read()
    m = re.search(r'<div class="a4">([\s\S]*?)</div>\s*</div>\s*</body>', src)
    inner = m.group(1)
    checked = ' checked="checked"' if i == 0 else ''
    inputs.append('<input class="cytab" id="cy%s" name="cy-year" type="radio"%s />' % (y, checked))
    btns.append('<label class="cybtn" for="cy%s">%s學年入學</label>' % (y, y))
    tabcss.append('#cy%s:checked ~ .panel.cy%s{display:block} #cy%s:checked ~ .cybtns label[for=cy%s]{background:var(--head);color:#fff;border-color:var(--head)}' % (y, y, y, y))
    panels.append('<div class="panel cy%s">\n<div class="a4">%s</div>\n</div>' % (y, inner))

tab_style = ('.cmap .cytab{position:absolute;opacity:0;pointer-events:none}'
  '.cmap .cybtns{display:flex;flex-wrap:wrap;gap:0.6rem;justify-content:center;margin:0 0 14px}'
  '.cmap .cybtn{cursor:pointer;font-size:1.05rem;font-weight:normal;color:var(--head);background:#fff;border:2px solid var(--line);border-radius:14px;padding:8px 20px;line-height:1.15;text-align:center;transition:all 0.15s ease}'
  '.cmap .cybtn:hover{border-color:var(--head)}'
  '.cmap .panel{display:none}' + ''.join(tabcss))

out = ('<style type="text/css">' + css + tab_style + '</style>\n'
  '<div class="cmap">\n'
  + ''.join(inputs) + '\n'
  '<div class="cybtns">\n' + '\n'.join(btns) + '\n</div>\n'
  + '\n'.join(panels) + '\n'
  '</div>')

io.open(os.path.join(base, 'coursemap_all.html'), 'w', encoding='utf-8').write(out)
print('written', len(out))
