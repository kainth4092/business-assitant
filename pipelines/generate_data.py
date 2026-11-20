"""
Synthetic BigMart Sales Data Generator
Generates realistic BigMart sales dataset with intentional data quality issues:
- Messy labels in Item_Fat_Content ('LF', 'low fat', 'Low Fat', 'reg', 'Regular')
- Missing values (nulls) in Item_Weight (~15%) and Outlet_Size (~25%)
- Duplicate rows (~25 rows)
- Leading/trailing whitespace in string fields
"""

import os
import csv
import random

# Seed for reproducibility
random.seed(42)

OUTLET_MAP = {
    "OUT010": {"year": 1998, "type": "Grocery Store", "loc": "Tier 3", "size": None},
    "OUT013": {"year": 1987, "type": "Supermarket Type1", "loc": "Tier 3", "size": "High"},
    "OUT017": {"year": 2007, "type": "Supermarket Type1", "loc": "Tier 2", "size": None},
    "OUT018": {"year": 2009, "type": "Supermarket Type2", "loc": "Tier 3", "size": "Medium"},
    "OUT019": {"year": 1985, "type": "Grocery Store", "loc": "Tier 1", "size": "Small"},
    "OUT027": {"year": 1985, "type": "Supermarket Type3", "loc": "Tier 3", "size": "Medium"},
    "OUT035": {"year": 2004, "type": "Supermarket Type1", "loc": "Tier 2", "size": "Small"},
    "OUT045": {"year": 2002, "type": "Supermarket Type1", "loc": "Tier 2", "size": None},
    "OUT046": {"year": 1997, "type": "Supermarket Type1", "loc": "Tier 1", "size": "Small"},
    "OUT049": {"year": 1999, "type": "Supermarket Type1", "loc": "Tier 1", "size": "Medium"},
}

ITEM_TYPES = [
    "Dairy", "Soft Drinks", "Meat", "Fruits and Vegetables", "Household",
    "Baking Goods", "Snack Foods", "Frozen Foods", "Breakfast",
    "Health and Hygiene", "Hard Drinks", "Canned", "Breads",
    "Starchy Foods", "Others", "Seafood"
]

FAT_CONTENT_VARIANTS = {
    "Low Fat": ["Low Fat", "low fat", "LF", " Low Fat "],
    "Regular": ["Regular", "reg", " Regular "]
}

def generate_bigmart_sales_csv(output_path: str = "data/BigMart_Sales.csv", num_rows: int = 1500):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    headers = [
        "Item_Identifier", "Item_Weight", "Item_Fat_Content", "Item_Visibility",
        "Item_Type", "Item_MRP", "Outlet_Identifier", "Outlet_Establishment_Year",
        "Outlet_Size", "Outlet_Location_Type", "Outlet_Type", "Item_Outlet_Sales"
    ]
    
    # Pre-generate item catalog of ~250 unique items to ensure consistent weights across items
    item_catalog = {}
    for i in range(250):
        prefix = random.choice(["FD", "DR", "NC"])
        letter = chr(random.randint(65, 90))
        num = random.randint(1, 99)
        item_id = f"{prefix}{letter}{num:02d}"
        
        # Item weight between 4.5 and 21.5 kg
        base_weight = round(random.uniform(4.5, 21.5), 3)
        item_type = random.choice(ITEM_TYPES)
        
        if prefix == "NC":  # Non-consumable
            fat_content = "Low Fat"
        else:
            fat_content = random.choice(["Low Fat", "Regular"])
            
        base_mrp = round(random.uniform(32.0, 266.0), 2)
        item_catalog[item_id] = {
            "weight": base_weight,
            "type": item_type,
            "fat": fat_content,
            "mrp": base_mrp
        }
    
    item_ids = list(item_catalog.keys())
    outlet_ids = list(OUTLET_MAP.keys())
    
    rows = []
    for _ in range(num_rows):
        item_id = random.choice(item_ids)
        outlet_id = random.choice(outlet_ids)
        meta = item_catalog[item_id]
        outlet = OUTLET_MAP[outlet_id]
        
        # 15% probability of missing Item_Weight
        weight = "" if random.random() < 0.15 else meta["weight"]
        
        # Messy fat content representation
        canonical_fat = meta["fat"]
        fat_content = random.choice(FAT_CONTENT_VARIANTS[canonical_fat])
        
        # Visibility: sometimes 0.0
        visibility = 0.0 if random.random() < 0.08 else round(random.uniform(0.01, 0.28), 6)
        
        # MRP with minor random deviation
        mrp = round(meta["mrp"] + random.uniform(-2.0, 2.0), 2)
        if mrp < 30.0:
            mrp = 30.0
            
        # Outlet size (simulate missing sizes for certain outlets or random missingness)
        size = outlet["size"]
        if size is None or random.random() < 0.15:
            size_val = ""
        else:
            size_val = size
            
        # Calculate realistic sales
        outlet_mult = 1.0
        if "Supermarket Type3" in outlet["type"]:
            outlet_mult = 2.2
        elif "Supermarket Type2" in outlet["type"]:
            outlet_mult = 1.4
        elif "Supermarket Type1" in outlet["type"]:
            outlet_mult = 1.6
        else: # Grocery store
            outlet_mult = 0.4
            
        sales = round((mrp * random.uniform(8.0, 24.0) * outlet_mult) + random.uniform(10.0, 80.0), 2)
        
        row = [
            item_id,
            weight,
            fat_content,
            visibility,
            meta["type"],
            mrp,
            outlet_id,
            outlet["year"],
            size_val,
            outlet["loc"],
            outlet["type"],
            sales
        ]
        rows.append(row)
        
    # Inject 30 duplicate rows to test PySpark deduplication
    for _ in range(30):
        duplicate_row = random.choice(rows).copy()
        rows.append(duplicate_row)
        
    random.shuffle(rows)
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
        
    print(f"Generated synthetic dataset with {len(rows)} records at {output_path}")
    return output_path

if __name__ == "__main__":
    generate_bigmart_sales_csv()
