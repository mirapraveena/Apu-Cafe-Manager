# MealSync

MealSync is a campus food pre-ordering system that allows APU students to order food from campus stalls in advance.

## Getting Started

1. Install the required packages:

   ```bash
   python -m pip install -r requirements.txt
   ```

2. (Optional) Add demo data:

   ```bash
   python seed.py
   ```

3. Start the application:

   ```bash
   python app.py
   ```

4. Open **http://127.0.0.1:5000** in your browser.

## Demo Login

After running `seed.py`:

- **Student:** TP012345
- **Password:** demo1234
- **Vendor:** Select a stall from the dropdown.
- **Vendor Password:** demo1234

## Main Features

- Students can browse stalls, view menus and place pre-orders.
- Students can track, cancel and view their orders.
- Vendors can manage menu items and update order statuses.
- Vendors can view and cancel orders.

## Order Status

Orders follow this sequence:

`Pending → Preparing → Ready → Completed`

- Students can cancel orders while they are Pending.
- Vendors can cancel orders before they are Completed.

## Technologies Used

- Python (Flask)
- SQLite
- HTML, CSS and JavaScript

## Colour Theme

- Navy: `#003A8C`
- Orange: `#F37021`
