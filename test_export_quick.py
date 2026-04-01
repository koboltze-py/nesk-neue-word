from functions.staerkemeldung_dashboard_export import StaerkemeldungDashboardExport
from datetime import datetime
import zipfile, os
from lxml import etree

data = {'dispo': [], 'betreuer': [], 'kranke': []}
exp = StaerkemeldungDashboardExport(data, 'test_cmp.docx', datetime(2026,3,26), datetime(2026,3,26), pax_zahl=42000, einsaetze_zahl=7, bulmor_aktiv=4)
pfad, _ = exp.export()

with zipfile.ZipFile(pfad) as z:
    xml = z.read('word/document.xml')
root = etree.fromstring(xml)
ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
qn = lambda n: f'{{{ns}}}{n}'
body = root.find(qn('body'))
tbl = body.find(qn('tbl'))
tr = tbl.find(qn('tr'))
trH = tr.find(qn('trPr')).find(qn('trHeight'))
tbl_h = int(trH.get(qn('val'), 0))
ps = [ch for ch in body if ch.tag == qn('p')]
sectPr = body.find(qn('sectPr'))
pgSz = sectPr.find(qn('pgSz'))
pgMar = sectPr.find(qn('pgMar'))
avail = int(pgSz.get(qn('h'))) - int(pgMar.get(qn('top'))) - int(pgMar.get(qn('bottom')))

print(f'Tabelle:      {tbl_h} twips = {tbl_h/566.929:.2f} cm')
print(f'Paragraphen:  {len(ps)}')
if ps:
    pPr = ps[0].find(qn('pPr'))
    sp = pPr.find(qn('spacing')) if pPr is not None else None
    snap = pPr.find(qn('snapToGrid')) if pPr is not None else None
    if sp is not None:
        print(f'  spacing line={sp.get(qn("line"))} lineRule={sp.get(qn("lineRule"))}')
    print(f'  snapToGrid={snap.get(qn("val")) if snap is not None else "nicht gesetzt"}')
print(f'Verfuegbar:   {avail} twips = {avail/566.929:.2f} cm')
print(f'Tbl+p(20):    {tbl_h+20} twips, Puffer: {avail - tbl_h - 20} twips')
print(f'Tbl+p(360):   {tbl_h+360} twips, Differenz zu avail: {avail - tbl_h - 360} twips')

os.remove(pfad)
print('OK')
