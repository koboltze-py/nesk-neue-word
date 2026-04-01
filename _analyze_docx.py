"""Analysiert den generierten Dashboard-Export auf Seiten/Höhen-Probleme."""
from functions.staerkemeldung_dashboard_export import StaerkemeldungDashboardExport
from datetime import datetime
import zipfile, os
from lxml import etree

def ma(name, dk, start='07:00', end='15:30'):
    return {'vollname': name, 'anzeigename': name.split()[0],
            'dienst_kategorie': dk, 'start_zeit': start, 'end_zeit': end}

data = {
    'dispo': [
        ma('Max Mustermann',  'DT',  '06:30', '15:00'),
        ma('Anna Schmidt',    'DT',  '06:30', '15:00'),
        ma('Peter Klein',     'DT3', '07:00', '15:30'),
        ma('Maria Gross',     'DT',  '09:00', '17:30'),
        ma('Klaus Berg',      'DT',  '10:00', '18:30'),
        ma('Sarah Wolf',      'DN',  '15:00', '23:30'),
        ma('Tom Braun',       'DN',  '15:00', '23:30'),
        ma('Lisa Muller',     'DN3', '16:00', '00:30'),
    ],
    'betreuer': [
        ma('Hans Fischer',    '', '06:00', '14:30'),
        ma('Ute Schreiber',   '', '06:00', '14:30'),
        ma('Frank Kohl',      '', '07:00', '15:30'),
        ma('Eva Neumann',     '', '08:00', '16:30'),
        ma('Otto Bauer',      '', '09:00', '17:30'),
        ma('Paula Richter',   '', '10:00', '18:30'),
        ma('Jens Vogel',      '', '14:30', '23:00'),
        ma('Katrin Stein',    '', '14:30', '23:00'),
        ma('Rolf Meier',      '', '15:30', '00:00'),
        ma('Monika Lang',     '', '15:30', '00:00'),
    ],
    'kranke': []
}

pfad = 'test_real.docx'
exp = StaerkemeldungDashboardExport(
    data, pfad, datetime(2026,3,26), datetime(2026,3,26),
    pax_zahl=4200, einsaetze_zahl=3, bulmor_aktiv=4,
    sl_tag_name='Mustermann', sl_nacht_name='Wolf'
)
exp.export()

ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
W = lambda n: f'{{{ns}}}{n}'

with zipfile.ZipFile(pfad) as z:
    xml = z.read('word/document.xml')

root = etree.fromstring(xml)
body = root.find(W('body'))

print('=== BODY-KINDER ===')
for ch in body:
    tag = ch.tag.split('}')[1] if '}' in ch.tag else ch.tag
    print(f'  <{tag}>')

sectPr = body.find(W('sectPr'))
pgSz   = sectPr.find(W('pgSz'))
pgMar  = sectPr.find(W('pgMar'))
h      = int(pgSz.get(W('h')))
top    = int(pgMar.get(W('top')))
bot    = int(pgMar.get(W('bottom')))
hdr_d  = int(pgMar.get(W('header'), 0))
ftr_d  = int(pgMar.get(W('footer'), 0))
avail  = h - top - bot

print(f'\n=== SEITENMASZE ===')
print(f'  h={h}  top={top}  bot={bot}  hdr={hdr_d}  ftr={ftr_d}')
print(f'  Verfuegbar: {avail} twips = {avail/566.929:.2f} cm')

docGrid = sectPr.find(W('docGrid'))
if docGrid is not None:
    lp = docGrid.get(W('linePitch'), '?')
    print(f'  docGrid linePitch={lp}')

# Header-Hoehe pruefen
with zipfile.ZipFile(pfad) as z:
    hdr_xml = z.read('word/header1.xml') if 'word/header1.xml' in z.namelist() else None

if hdr_xml:
    hroot = etree.fromstring(hdr_xml)
    hparas = hroot.findall('.//' + W('p'))
    print(f'  Header-Paragraphen: {len(hparas)}')

# Tabellen-Zeilen-Hoehe
tbl  = body.find(W('tbl'))
tblPr = tbl.find(W('tblPr'))

tblLay = tblPr.find(W('tblLayout')) if tblPr is not None else None
if tblLay is not None:
    print(f'\n=== TABELLE ===')
    print(f'  tblLayout type={tblLay.get(W("type"))}')

tr   = tbl.find(W('tr'))
trPr = tr.find(W('trPr'))
trH  = trPr.find(W('trHeight')) if trPr is not None else None
tbl_h = 0
if trH is not None:
    tbl_h = int(trH.get(W('val'), 0))
    print(f'  trHeight val={tbl_h} = {tbl_h/566.929:.2f} cm  hRule={trH.get(W("hRule"))}')

cantSplit = trPr.find(W('cantSplit')) if trPr is not None else None
print(f'  cantSplit in trPr: {cantSplit is not None}')

# Zellen
cells = tr.findall(W('tc'))
print(f'  Zellen: {len(cells)}')
for i, tc in enumerate(cells):
    tcPr = tc.find(W('tcPr'))
    tcW  = tcPr.find(W('tcW')) if tcPr is not None else None
    w_val = tcW.get(W('w'), '?') if tcW is not None else '?'
    paras = tc.findall('.//' + W('p'))
    print(f'  Zelle {i}: w={w_val} twips, {len(paras)} Paragraphen')

# Trailing Paragraph
ps = [c for c in body if c.tag == W('p')]
print(f'\n=== TRAILING PARAGRAPH ===')
if ps:
    p0  = ps[0]
    pPr = p0.find(W('pPr'))
    if pPr is not None:
        spc  = pPr.find(W('spacing'))
        snap = pPr.find(W('snapToGrid'))
        line_val = int(spc.get(W('line'), 20)) if spc is not None else '?'
        snap_val = snap.get(W('val'), '?') if snap is not None else 'nicht vorhanden'
        print(f'  spacing.line={line_val}  snapToGrid={snap_val}')
        print(f'  Tbl+p(actual): {tbl_h + line_val} twips  Puffer={avail - tbl_h - line_val}')
        print(f'  Tbl+p(snapped): {tbl_h + 360} twips  Puffer={avail - tbl_h - 360}')
else:
    print('  KEIN trailing paragraph gefunden!')

# Pruefen ob tblW > Seitenbreite
pgSzW = int(pgSz.get(W('w')))
left  = int(pgMar.get(W('left'), 0))
right = int(pgMar.get(W('right'), 0))
body_w = pgSzW - left - right
tblW = tblPr.find(W('tblW')) if tblPr is not None else None
if tblW is not None:
    tw = int(tblW.get(W('w'), 0))
    print(f'\n=== BREITE ===')
    print(f'  body_w={body_w} twips  tblW={tw} twips  ueberlauf={tw - body_w}')

os.remove(pfad)
print('\nDONE')
