# Phase F: sourced Dining line 4

Replaces the generic "A restaurant in X" line on Dining cards with a short English line taken from the card's
own listing (Tabelog, or TripAdvisor for TA-only cards): genre/cuisine, Top-100/award, station access,
lunch/dinner budget band, opening hours, closed days, English address area, parking/takeout.
Ratings are never shown (locked rule 4). Lines repeated >3x on a page get further listing facts.
Cards whose listing gives nothing beyond name/genre keep their existing line and are logged in no-data-wave*.csv.

Run: fetch listings politely (line4/work/fetch.py), then `python3 gen2.py && python3 apply.py && python3 count_generic.py`.
