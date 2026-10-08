"""Extra listing facts used to make otherwise-bare lines specific: opening hours and closed days
(Tabelog 営業時間 cell or TripAdvisor openingHoursSpecification) and the TripAdvisor English address area."""
import re, json
DAYJ = {'月':'Monday','火':'Tuesday','水':'Wednesday','木':'Thursday','金':'Friday','土':'Saturday','日':'Sunday'}
ORDER = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
def _clean_cell(raw):
    t = re.sub(r'<br\s*/?>', '\n', raw); t = re.sub(r'<[^>]+>', '\n', t)
    t = t.replace('&nbsp;', ' ').replace('\u3000', ' ')
    return [x.strip() for x in t.split('\n') if x.strip()]
def tb_hours(s):
    m = re.search(r'<th[^>]*>\s*営業時間\s*</th>\s*<td[^>]*>(.*?)</td>', s, re.S)
    if not m: return None, None
    lines = _clean_cell(m.group(1)); closed = []; ranges = []
    for i, l in enumerate(lines):
        if l.startswith('■'): break  # free-text notes follow
        if l == '定休日' and i > 0 and re.fullmatch(r'[月火水木金土日祝・、]+', lines[i - 1]):
            closed += [DAYJ[c] for c in lines[i - 1] if c in DAYJ]
        for a, b in re.findall(r'(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})', l):
            if (a, b) not in ranges: ranges.append((a, b))
    hours = None
    if len(ranges) == 1: hours = f'open {ranges[0][0]}–{ranges[0][1]}'
    elif len(ranges) == 2 and ranges[0][1] < ranges[1][0]: hours = f'open {ranges[0][0]}–{ranges[0][1]} and {ranges[1][0]}–{ranges[1][1]}'
    cl = None
    closed = [d for d in ORDER if d in closed]
    if 1 <= len(closed) <= 2: cl = 'closed ' + ' and '.join(d + 's' for d in closed)
    return hours, cl
def ta_hours(ld):
    spec = ld.get('openingHoursSpecification') if isinstance(ld, dict) else None
    if not spec or not isinstance(spec, list): return None, None
    days = {}; ranges = set()
    for e in spec:
        if not isinstance(e, dict): continue
        dw = e.get('dayOfWeek'); dws = dw if isinstance(dw, list) else [dw]
        o, c = (e.get('opens') or '')[:5], (e.get('closes') or '')[:5]
        if not o or not c: continue
        for d in dws:
            d = (d or '').rsplit('/', 1)[-1]
            if d in ORDER: days.setdefault(d, set()).add((o, c)); ranges.add((o, c))
    if not days: return None, None
    hours = None
    if len(ranges) == 1:
        o, c = next(iter(ranges)); hours = f'open {o}–{c}'
    elif len(ranges) == 2:
        a, b = sorted(ranges)
        if all(v == {a, b} for v in days.values()) and a[1] < b[0]: hours = f'open {a[0]}–{a[1]} and {b[0]}–{b[1]}'
    closed = [d for d in ORDER if d not in days]
    cl = ('closed ' + ' and '.join(d + 's' for d in closed)) if 1 <= len(closed) <= 2 else None
    return hours, cl
def ta_area(decoded):
    m = re.search(r'"localizedRealtimeAddress":"([^"]+)"', decoded)
    if not m: return None
    parts = [p.strip() for p in m.group(1).split(',')]
    for p in parts[:-1]:
        q = re.sub(r'^[\d\-\s]+', '', p).strip()
        q = re.sub(r'\b(\d+)-?chome\b', '', q, flags=re.I).strip(' -')
        if q and re.fullmatch(r"[A-Za-zōūāēī'\- ]{3,30}", q) and not re.search(r'prefecture|japan', q, re.I):
            return q
    return None
