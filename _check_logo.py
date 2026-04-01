from PIL import Image
import os

logo = r'Daten\Email\Logo.jpg'
if os.path.exists(logo):
    img = Image.open(logo)
    w, h = img.size
    dpi = img.info.get('dpi', (96, 96))
    print(f'Logo: {w}x{h} px, dpi={dpi}')
    h_inch = h / w
    h_twips = h_inch * 1440
    print(f'Renderhoehe bei width=1.0": {h_inch:.3f}" = {h_twips:.0f} twips = {h_twips/566.929:.2f} cm')
    print(f'Verfuegbarer Header-Bereich: 1020-227 = 793 twips = 1.40 cm')
    print(f'UEBERLAUF: {h_twips > 793}  (um {max(0, h_twips - 793):.0f} twips)')
else:
    print('Logo nicht gefunden')
