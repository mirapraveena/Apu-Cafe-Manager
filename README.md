# MealSync

Pre-order food from APU campus stalls. Flask + SQLite, plain HTML/CSS/JS.

## Run

    python -m pip install -r requirements.txt
    python seed.py        # optional demo data
    python app.py

Then open http://127.0.0.1:5000

Demo logins after seeding: student `TP012345`, password `demo1234`.
Vendors log in by picking their stall from the dropdown, password `demo1234`.

## Files

- `app.py`        - routes (login, student side, vendor side)
- `db.py`         - database and business rules (cancelling, status changes, etc.)
- `seed.py`       - demo data with placeholder food pictures
- `templates/`    - HTML pages
- `static/`       - `style.css`, `app.js`, and `uploads/` (vendor photos end up here)
- `canteen.db`    - created on first run. Delete it to reset everything.

## Order flow

Pending -> Preparing -> Ready -> Completed. Students can cancel only while an
order is Pending. Vendors can cancel any order that isn't Completed.

## Photos

Vendors add a photo when creating an item, or click the picture on an existing
item to change it. PNG, JPG, WEBP and GIF up to 8 MB. A stall's cover picture on
the stalls page is its first item with a photo.

## Colours

Navy `#003A8C` and orange `#F37021`, set at the top of `static/style.css`.
