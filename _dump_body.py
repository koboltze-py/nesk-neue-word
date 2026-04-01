"""Dumps vollstaendiges Body-XML des generierten exports."""
from functions.staerkemeldung_dashboard_export import StaerkemeldungDashboardExport
from datetime import datetime
import zipfile, os
from lxml import etree

def ma(name, dk, start='07:00', end='15:30'):
    return {'vollname': name, 'anzeigename': name.split()[0],
            'dienst_kategorie': dk, 'start_zeit': start, 'end_zeit': end}

data = {
    'dispo': [
        ma('Max Mustermann', 'DT', '06:30', '15:00'),
        ma('Anna Schmidt', 'DT', '06:30', '15:00'),
        ma('Sarah Wolf', 'DN', '15:00', '23:30'),
    ],
    'betreuer': [ma('Hans Fischer', '', '06:00', '14:30')],
    'kranke': []
}

pfad = 'test_dump.docx'
exp = StaerkemeldungDashboardExport(
    data, pfad, datetime(2026,3,26), datetime(2026,3,26),
    pax_zahl=100, bulmor_aktiv=4
)
exp.export()

ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W = lambda n: f'{{{ns}}}{n}'

with zipfile.ZipFile(pfad) as z:
    xml = z.read('word/document.xml')

root = etree.fromstring(xml)
body = root.find(W('body'))

# Body-Kinder ganz detailliert
print('=== BODY direct children ===')
for i, ch in enumerate(body):
    tag = ch.tag.split('}')[1] if '}' in ch.tag else ch.tag
    print(f'[{i}] <{tag}>')
    if tag == 'p':
        # pPr dump
        pPr = ch.find(W('pPr'))
        if pPr is not None:
            print('    pPr:', etree.tostring(pPr, pretty_print=True).decode())
    if tag == 'sectPr':
        pgSz = ch.find(W('pgSz'))
        pgMar = ch.find(W('pgMar'))
        docGrid = ch.find(W('docGrid'))
        if pgSz is not None:
            print(f'    pgSz h={pgSz.get(W("h"))} w={pgSz.get(W("w"))}')
        if pgMar is not None:
            print(f'    pgMar top={pgMar.get(W("top"))} bot={pgMar.get(W("bottom"))} '
                  f'hdr={pgMar.get(W("header"))} ftr={pgMar.get(W("footer"))}')
        if docGrid is not None:
            print(f'    docGrid type={docGrid.get(W("type"))} linePitch={docGrid.get(W("linePitch"))}')

# Tabelle trHeight und Zellen
tbl = body.find(W('tbl'))
if tbl is not None:
    tr = tbl.find(W('tr'))
    trPr = tr.find(W('trPr'))
    trH = trPr.find(W('trHeight')) if trPr is not None else None
    if trH is not None:
        print(f'\n=== TABLE ROW HEIGHT ===')
        print(f'val={trH.get(W("val"))} hRule={trH.get(W("hRule"))}')
    
    # tblPr dump
    tblPr = tbl.find(W('tblPr'))
    if tblPr is not None:
        print('\n=== tblPr ===')
        print(etree.tostring(tblPr, pretty_print=True).decode()[:800])

# sectPr vollstaendig
sectPr = body.find(W('sectPr'))
print('\n=== FULL sectPr ===')
print(etree.tostring(sectPr, pretty_print=True).decode())

os.remove(pfad)
print('DONE')
