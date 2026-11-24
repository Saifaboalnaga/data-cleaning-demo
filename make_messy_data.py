"""Generate a synthetic, intentionally messy sales dataset for the cleaning demo.

All records are fictional. Run once to (re)create data/raw_sales.csv.
"""
import random
from pathlib import Path

random.seed(42)

customers = ["Ahmed Hassan", "Sara Ali", "Omar Khaled", "Mona Adel", "Youssef Samir",
             "Nour Ibrahim", "Karim Fathy", "Laila Mostafa", "Hany Zaki", "Dina Farouk"]
products = ["Laptop", "Monitor", "Keyboard", "Mouse", "Headset", "Webcam"]
regions = ["Cairo", "Giza", "Alexandria"]
date_formats = ["%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y", "%d %b %Y"]

import datetime as dt

rows = []
for i in range(1, 201):
    d = dt.date(2026, 1, 1) + dt.timedelta(days=random.randint(0, 300))
    name = random.choice(customers)
    # naming inconsistencies: case and extra whitespace
    name = random.choice([name, name.upper(), name.lower(), f"  {name} ", name.replace(" ", "  ")])
    product = random.choice(products)
    product = random.choice([product, product.lower(), f" {product}"])
    region = random.choice(regions)
    region = random.choice([region, region.upper(), "alex" if region == "Alexandria" else region])
    qty = random.randint(1, 5)
    price = round(random.uniform(10, 900), 2)
    # currency formatting inconsistencies
    price_str = random.choice([f"{price}", f"${price}", f"{price} USD", f"{price:,.2f}", f"EGP {price}"])
    date_str = d.strftime(random.choice(date_formats))
    rows.append([f"INV-{1000 + i}", date_str, name, product, region, str(qty), price_str])

# missing values
for r in random.sample(rows, 12):
    r[random.choice([2, 4, 5])] = ""
# corrupted values
for r in random.sample(rows, 6):
    r[5] = random.choice(["abc", "-3", "?"])
# outliers
for r in random.sample(rows, 4):
    r[6] = "999999"
# exact and near duplicates
dupes = random.sample(rows, 15)
rows += [list(r) for r in dupes]
for r in random.sample(rows, 5):
    rows.append([r[0], r[1], r[2].strip().upper(), r[3], r[4], r[5], r[6]])
random.shuffle(rows)

out = Path("data/raw_sales.csv")
out.parent.mkdir(exist_ok=True)
with out.open("w", encoding="utf-8") as f:
    f.write("invoice_id,order_date,customer_name,product,region,quantity,unit_price\n")
    for r in rows:
        f.write(",".join(f'"{c}"' if "," in c else c for c in r) + "\n")
print(f"Wrote {len(rows)} rows to {out}")
