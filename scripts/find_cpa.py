import os, glob, fitz

folder = r'C:\Users\user\OneDrive\Desktop\kilo memory'
files = glob.glob(os.path.join(folder, '*.pdf'))
hits = []
for f in files:
    try:
        doc = fitz.open(f)
        for i, line in enumerate(''.join(page.get_text() for page in doc).splitlines()):
            if 'CPA' in line:
                hits.append((os.path.basename(f), i, line.strip()))
        doc.close()
    except Exception as e:
        hits.append((os.path.basename(f), -1, f'ERROR: {e}'))
    if len(hits) >= 20:
        break

print('\n'.join([f'{a}:{b}:{c}' for a,b,c in hits]) if hits else 'NO_CPA_MATCH')
