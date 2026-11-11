"""Optional: fills the database with demo data so the app looks alive.
Run once with: python seed.py

The food pictures are simple placeholder illustrations. Replace them with real
photos from the vendor Menu page (click a picture to change it).
"""
import os

import db

UPLOADS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
os.makedirs(UPLOADS, exist_ok=True)

PLATE = ('<ellipse cx="200" cy="205" rx="118" ry="22" fill="rgba(0,0,0,.14)"/>'
         '<circle cx="200" cy="150" r="102" fill="#fff"/><circle cx="200" cy="150" r="82" fill="#f5f1e8"/>')

FOODS = {
    "rice": ("#fde7c8", "#f7c98b", PLATE +
             '<path d="M135 165 Q200 70 265 165 Z" fill="#fff" stroke="#e8e2d2" stroke-width="3"/>'
             '<circle cx="262" cy="160" r="15" fill="#c8421e"/>'
             '<circle cx="140" cy="168" r="11" fill="#7bb661"/><circle cx="160" cy="180" r="11" fill="#7bb661"/>'),
    "noodles": ("#fdebc0", "#f2c14e", PLATE +
                '<path d="M135 125 q16 -22 32 0 t32 0 t32 0 t32 0" stroke="#e0a73a" stroke-width="10" fill="none" stroke-linecap="round"/>'
                '<path d="M135 150 q16 -22 32 0 t32 0 t32 0 t32 0" stroke="#e8b54a" stroke-width="10" fill="none" stroke-linecap="round"/>'
                '<path d="M135 175 q16 -22 32 0 t32 0 t32 0 t32 0" stroke="#e0a73a" stroke-width="10" fill="none" stroke-linecap="round"/>'
                '<circle cx="200" cy="148" r="14" fill="#8bc34a"/>'),
    "western": ("#e6eefc", "#b5cdf3", PLATE +
                '<ellipse cx="185" cy="148" rx="52" ry="34" fill="#a8683a"/>'
                '<ellipse cx="185" cy="144" rx="40" ry="24" fill="#c0824c"/>'
                '<rect x="232" y="125" width="10" height="46" rx="4" fill="#f4c542" transform="rotate(20 237 148)"/>'
                '<rect x="248" y="128" width="10" height="46" rx="4" fill="#f4c542" transform="rotate(35 253 151)"/>'),
    "snacks": ("#fff0cf", "#f7d27a", PLATE +
               '<rect x="150" y="105" width="12" height="70" rx="5" fill="#f4c542" transform="rotate(-18 156 140)"/>'
               '<rect x="172" y="100" width="12" height="76" rx="5" fill="#f7d160" transform="rotate(-6 178 138)"/>'
               '<rect x="196" y="100" width="12" height="76" rx="5" fill="#f4c542" transform="rotate(4 202 138)"/>'
               '<rect x="220" y="104" width="12" height="72" rx="5" fill="#f7d160" transform="rotate(16 226 140)"/>'
               '<rect x="242" y="112" width="12" height="62" rx="5" fill="#f4c542" transform="rotate(28 248 143)"/>'),
    "drinks": ("#dff3ee", "#9fd8c9",
               '<ellipse cx="200" cy="228" rx="70" ry="12" fill="rgba(0,0,0,.14)"/>'
               '<path d="M150 80 L250 80 L238 220 L162 220 Z" fill="#ffffff" fill-opacity=".85" stroke="#fff" stroke-width="3"/>'
               '<path d="M155 120 L245 120 L238 220 L162 220 Z" fill="#d9843d"/>'
               '<rect x="205" y="30" width="10" height="100" rx="4" fill="#F37021" transform="rotate(12 210 80)"/>'),
    "dessert": ("#fde4ee", "#f7b6cf", PLATE +
                '<circle cx="185" cy="135" r="34" fill="#f48fb1"/><circle cx="222" cy="150" r="30" fill="#fff3e0"/>'
                '<circle cx="190" cy="105" r="9" fill="#c62828"/>'),
    "other": ("#e8effa", "#bcd0ee", PLATE + '<circle cx="200" cy="150" r="40" fill="#F37021"/>'),
}


def make_image(key):
    bg1, bg2, shapes = FOODS[key]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{bg1}"/>'
        f'<stop offset="1" stop-color="{bg2}"/></linearGradient></defs>'
        f'<rect width="400" height="300" fill="url(#g)"/>{shapes}</svg>'
    )
    name = f"seed-{key}.svg"
    with open(os.path.join(UPLOADS, name), "w", encoding="utf-8") as f:
        f.write(svg)
    return name


db.init_db()
db.register_student("TP012345", "Demo Student", "demo1234")

stalls = {
    "Nasi Lemak Corner": [("Nasi Lemak Ayam", 7.50, "Rice"), ("Nasi Lemak Telur", 5.00, "Rice"),
                          ("Teh Tarik", 2.50, "Drinks")],
    "Western Bites": [("Chicken Chop", 12.90, "Western"), ("Fish and Chips", 11.50, "Western"),
                      ("Fries", 4.50, "Snacks")],
    "Noodle House": [("Curry Mee", 8.00, "Noodles"), ("Wantan Mee", 7.50, "Noodles"),
                     ("Iced Lemon Tea", 3.00, "Drinks"), ("Cendol", 4.50, "Dessert")],
}
for shop, items in stalls.items():
    ok, _ = db.register_vendor(shop, shop.split()[0].lower(), "demo1234")
    if ok:
        vid = [v for v in db.list_vendors() if v["shop_name"] == shop][0]["id"]
        for name, price, category in items:
            db.add_menu_item(vid, name, price, category, make_image(category.lower()))

print("Done. Student: TP012345 / demo1234. Every stall password: demo1234.")
