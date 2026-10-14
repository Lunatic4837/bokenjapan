#!/home/box/venvs/bjclip/bin/python
"""CLIP zero-shot photo judge (P5). Long-lived worker: one image path per stdin line ->
one JSON line {"path","label","p","reject"} on stdout. Run with the bjclip venv python."""
import sys, json, torch, open_clip
from PIL import Image
OK = ['a photo of a hotel building exterior', 'a photo of a hotel room with a bed', 'a photo of a japanese tatami guest room',
      'a photo of a hotel lobby', 'a photo of an outdoor hot spring bath', 'a photo of an indoor public bath',
      'a photo of a japanese inn entrance', 'a scenic view from a hotel', 'a photo of a hotel restaurant interior']
BAD = {'a photo of a meal on a table': 'food', 'a photo of a kaiseki dinner tray': 'food', 'a close-up photo of food dishes': 'food',
       'a photo of a breakfast buffet': 'food', 'a promotional banner with large text': 'promo', 'an advertisement graphic with japanese text': 'promo',
       'an award badge or logo': 'promo', 'a collage of several photos with text': 'promo', 'a photo of a pet dog or cat': 'pet',
       'a photo of people posing': 'people'}
LABELS = OK + list(BAD)
m, _, pre = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k'); m.eval()
tok = open_clip.get_tokenizer('ViT-B-32')
with torch.no_grad():
    T = m.encode_text(tok(LABELS)); T /= T.norm(dim=-1, keepdim=True)
print(json.dumps({'ready': True}), flush=True)
for line in sys.stdin:
    p = line.strip()
    if not p: continue
    try:
        with torch.no_grad():
            I = m.encode_image(pre(Image.open(p).convert('RGB')).unsqueeze(0)); I /= I.norm(dim=-1, keepdim=True)
            pr = (100 * I @ T.T).softmax(-1)[0]
        bad = sum(float(pr[i]) for i, l in enumerate(LABELS) if l in BAD)
        top = LABELS[int(pr.argmax())]
        rej = BAD.get(top) if (top in BAD and bad >= 0.5) else None
        print(json.dumps({'path': p, 'label': top, 'p_bad': round(bad, 3), 'reject': rej}), flush=True)
    except Exception as e:
        print(json.dumps({'path': p, 'error': str(e)[:200], 'reject': None}), flush=True)
