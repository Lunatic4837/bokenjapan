# Pages slim build

`scripts/build-pages-site.py` publishes `_site` to `gh-pages`. GitHub Pages rejects a site at 1 GiB. The script gate is **900 MiB**.

After main `73401b10f4`, baking every referenced photo (560px WebP q25) produced ~1,010 MiB and exit 2. Almost all of that was facility thumbs (~67k), not HTML (~43 MiB after map externalize) and not the ~1,600 municipality covers.

Remote image URLs are not available on this path. Photo-credit comments link to article pages, not image files, and Cloudflare R2 is not enabled. Thumbs stay local, with a cap, instead of a hotlink.

What is baked:

- Every cover, at 1200px / WebP q62, so municipality heroes stay sharp.
- Homepage hero unchanged (1600px / q40).
- Per page, per section: Stay 8, Dining 8, Sights 4, any other section 2. Extra `<img class="thumb">` tags are omitted. Place names and hidden photo-credit comments stay.
- Locator maps are still one SVG per prefecture, fetched by the existing loader.

Ohira still ships its cover, its stay photo, its sight thumbs, and the first 8 dining photos. A catalog page such as Sendai keeps 8 stay, 8 dining, and 4 sights instead of thousands of dining files.

The cap, not a tighter WebP quality, is what leaves room for later facility waves. Full saturation of today’s municipality count at these caps is roughly 600–750 MiB plus HTML, under the 900 MiB gate.

Measured on this tree (main `73401b10f4` plus the cap): 8,481 WebP files, 62,295 thumbs omitted, `_site` **304.1 MiB** (WebP 255.3 MiB, HTML 34.5 MiB), exit 0.
