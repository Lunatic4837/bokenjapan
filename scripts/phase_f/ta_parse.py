"""Facts from a TripAdvisor restaurant page: the tag groups embedded in the page's own JSON
(cuisines, price_types, meal_types, diets, dishes, features) plus ld+json servesCuisine/priceRange."""
import re, urllib.parse
def decoded(s):
    d = s
    for _ in range(4): d = urllib.parse.unquote(d)
    return d.replace('\\\\\\"', '"').replace('\\"', '"')
def groups(s):
    d = decoded(s); out = {}
    for g in ('cuisines', 'price_types', 'meal_types', 'diets', 'dishes', 'features', 'establishment_types'):
        for m in re.finditer(r'"%s":\{"items":(\[.*?\])\}' % g, d):
            names = re.findall(r'"localizedName":"([^"]+)"', m.group(1))
            if names: out.setdefault(g, [])
            for n in names:
                if n not in out[g]: out[g].append(n)
    return out
