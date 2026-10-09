import json, sys
from PIL import Image, ImageDraw
for key in sys.argv[1:]:
    d = f'cov/{key}'; idx = json.load(open(f'{d}/index.json'))
    W, H, cols = 300, 170, 5
    idx = idx[:40]
    sh = Image.new('RGB', (W * cols, (H + 14) * max(1, (len(idx) + cols - 1) // cols)), 'white'); dr = ImageDraw.Draw(sh)
    for i, x in enumerate(idx):
        try: im = Image.open(f'{d}/{x["file"]}').convert('RGB'); im.thumbnail((W, H))
        except Exception: continue
        X, Y = (i % cols) * W, (i // cols) * (H + 14); sh.paste(im, (X, Y)); dr.text((X + 2, Y + H), f'{i} {x["w"]}x{x["h"]}', fill='black')
    sh.save(f'/tmp/sheet_{key}.jpg', quality=80)
    print(key, len(idx))
