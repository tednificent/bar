import sqlite3
import re
import os

DB_NAME = "bar.db"

# --- 1. YOUR HELPER FUNCTION ---
def convert_ml_to_oz(text):
    """Converts metric units to US oz (rounded to 0.25oz)."""
    # Regex to find numbers followed by ml or cl
    pattern = r'(\d+\.?\d*)\s*(ml|cl)'
    
    def convert_match(match):
        value = float(match.group(1))
        unit = match.group(2)
        if unit == 'cl': value *= 10  # Convert cl to ml first
        ounces = round(value / 30, 2) # Rough conversion: 30ml = 1oz
        
        # Round to nearest quarter ounce for readability
        if ounces < 0.15: return "dash" 
        
        remainder = ounces % 0.25
        if remainder < 0.12:
            ounces = ounces - remainder
        else:
            ounces = ounces + (0.25 - remainder)
            
        return f"{ounces:.2f} oz".replace(".00", "") 
        
    return re.sub(pattern, convert_match, text, flags=re.IGNORECASE)

# --- 2. DATABASE SETUP ---
def init_db():
    """Creates the tables if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Table for the Cocktail itself
    c.execute('''
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            instructions TEXT,
            glassware TEXT,
            is_favorite BOOLEAN DEFAULT 0
        )
    ''')

    # Table for the Specs (Smart Ingredients)
    c.execute('''
        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER,
            amount REAL,        
            unit TEXT,          
            ingredient TEXT,    
            raw_text TEXT,      
            FOREIGN KEY(recipe_id) REFERENCES recipes(id)
        )
    ''')
    
    conn.commit()
    conn.close()

# --- 3. HELPER: PARSE STRINGS ---
def parse_spec_line(spec_line):
    """
    Breaks a string like '1.5 oz Bourbon' into parts: (1.5, 'oz', 'Bourbon')
    """
    match = re.match(r"([\d\.]+)\s*(oz|dash|dashes|cl|ml)?\s+(.*)", spec_line, re.IGNORECASE)
    if match:
        amount = float(match.group(1))
        unit = match.group(2) if match.group(2) else ""
        ingredient = match.group(3)
        return amount, unit, ingredient
    return 0, "", spec_line 

# --- 4. APP FUNCTIONS (Used by bar.py) ---

def get_all_recipes():
    """Fetches all recipes from DB and formats them for the UI."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    c = conn.cursor()
    
    recipes = []
    try:
        c.execute("SELECT id, name, instructions, glassware, is_favorite, category, description, image_url, price, spirit FROM recipes")
        rows = c.fetchall()
        
        for row in rows:
            r_dict = dict(row)
            
            # Fetch ingredients for this specific recipe
            c.execute("SELECT raw_text FROM recipe_ingredients WHERE recipe_id = ?", (row['id'],))
            ing_rows = c.fetchall()
            
            # Flatten ingredients back to list
            r_dict['specs'] = [i['raw_text'] for i in ing_rows]
            recipes.append(r_dict)
    except Exception as e:
        print(f"Error loading recipes: {e}")
    finally:
        conn.close()
        
    return recipes

def save_new_recipe(recipe_data):
    """Saves a single recipe dict to the DB."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    try:
        # Check for duplicates first
        c.execute("SELECT id FROM recipes WHERE name = ?", (recipe_data.get('name'),))
        if c.fetchone():
            return False # Duplicate

        # 1. Insert Recipe
        c.execute("""
            INSERT INTO recipes (name, instructions, category, description, price, image_url, spirit) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            recipe_data.get('name'), 
            recipe_data.get('instructions', ''), 
            recipe_data.get('category', 'Classics'),
            recipe_data.get('description', ''),
            recipe_data.get('price', ''),
            recipe_data.get('image_url', ''),
            recipe_data.get('spirit', '')
        ))
        recipe_id = c.lastrowid
        
        # 2. Insert Ingredients
        for spec in recipe_data.get('specs', []):
            amt, unit, ing = parse_spec_line(spec)
            
            c.execute('''
                INSERT INTO recipe_ingredients (recipe_id, amount, unit, ingredient, raw_text)
                VALUES (?, ?, ?, ?, ?)
            ''', (recipe_id, amt, unit, ing, spec))
            
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving recipe: {e}")
        return False
    finally:
        conn.close()

# --- NEW FUNCTION IN db_utils.py ---
def add_category_column():
    """Adds the category column if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # We try to add the column; if it already exists, the database ignores the error.
        c.execute("ALTER TABLE recipes ADD COLUMN category TEXT DEFAULT 'Uncategorized'")
        conn.commit()
        print("Category column ensured in recipes table.")
    except sqlite3.OperationalError as e:
        # Likely means the column already exists (which is fine)
        if "duplicate column name" in str(e):
             print("Category column already exists.")
        else:
             print(f"Error adding category column: {e}")
    finally:
        conn.close()

# Update the execution block at the very bottom of db_utils.py

# --- 5. NEW: ADMIN FUNCTIONS ---

def delete_recipe(recipe_id):
    """Deletes a recipe and its ingredients."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
        c.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting recipe: {e}")
        return False
    finally:
        conn.close()

def update_recipe_category(recipe_id, new_category):
    """Updates the category for a specific recipe."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("UPDATE recipes SET category = ? WHERE id = ?", (new_category, recipe_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating category: {e}")
        return False
    finally:
        conn.close()

def update_whole_recipe(recipe_id, data):
    """Updates ALL fields of a recipe, including ingredients."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        # 1. Update Core Fields
        c.execute("""
            UPDATE recipes 
            SET name=?, category=?, description=?, price=?, image_url=?, instructions=?, spirit=?
            WHERE id=?
        """, (data['name'], data['category'], data['description'], 
              data['price'], data['image_url'], data['instructions'], data.get('spirit', ''), recipe_id))
        
        # 2. Update Ingredients (Delete Old -> Insert New)
        # This is easier than trying to diff them
        c.execute("DELETE FROM recipe_ingredients WHERE recipe_id=?", (recipe_id,))
        
        for spec in data.get('specs', []):
            if not spec.strip(): continue # Skip empty lines
            amt, unit, ing = parse_spec_line(spec)
            c.execute("""
                INSERT INTO recipe_ingredients (recipe_id, amount, unit, ingredient, raw_text)
                VALUES (?, ?, ?, ?, ?)
            """, (recipe_id, amt, unit, ing, spec))
            
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating whole recipe: {e}")
        return False
    finally:
        conn.close()

def migrate_json_to_db():
    """Reads menu.json and migrates to DB if not present."""
    import json
    
    if not os.path.exists("menu.json"):
        print("No menu.json found to migrate.")
        return

    print("Starting migration...")
    try:
        with open("menu.json", "r") as f:
            data = json.load(f)
            
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        count = 0
        for item in data:
            # Check if exists
            c.execute("SELECT id FROM recipes WHERE name = ?", (item.get('name'),))
            if c.fetchone():
                continue
                
            # Auto-Categorization Logic
            category = 'Classics' # Default
            spirit = item.get('spirit', '')
            beer_type = item.get('beer_type', '')
            
            if item.get('is_cotw'):
                category = 'Featured Sips'
            elif spirit == 'Beer' or beer_type:
                category = 'Beer'
            elif spirit in ['Red Wine', 'White Wine'] or 'Wine' in spirit:
                category = 'Wine'
            elif spirit == 'Non-Alcoholic':
                category = 'Zero Proof'
            elif item.get('is_craft'):
                category = 'Craft Cocktails'
            elif item.get('is_classic'):
                category = 'Classics'
            elif spirit in ['Tequila', 'Vodka', 'Gin', 'Rum', 'Whiskey', 'Bourbon']:
                category = 'Liquors' # Assuming this maps to Liquors, or we can put cocktails here? 
                # Actually user list had 'Liquors' separate. Let's aim for 'Craft Cocktails' or 'Classics' mostly for cocktails.
                # If it's just a raw spirit entry (no ingredients?), maybe Liquors?
                # For now let's stick to the list: 'Featured Sips', 'Craft Cocktails', 'Classics', 'Beer', 'Wine', 'Liquors', 'Zero Proof'
                pass
            
            # Insert Recipe
            c.execute("INSERT INTO recipes (name, instructions, category) VALUES (?, ?, ?)", 
                      (item.get('name'), item.get('instructions', ''), category))
            recipe_id = c.lastrowid
            
            # Insert Specs (Use spec_recipe from JSON)
            specs = item.get('spec_recipe', [])
            for spec in specs:
                 # Clean up the spec string if needed
                 if isinstance(spec, str):
                     amt, unit, ing = parse_spec_line(spec)
                     c.execute("INSERT INTO recipe_ingredients (recipe_id, amount, unit, ingredient, raw_text) VALUES (?, ?, ?, ?, ?)",
                               (recipe_id, amt, unit, ing, spec))

            count += 1
            
        conn.commit()
        conn.close()
        print(f"Migration complete. Imported {count} new recipes.")
        
    except Exception as e:
        print(f"Migration failed: {e}")

# --- 6. NEW: DETAILS COLUMNS ---
def add_details_columns():
    """Adds description, image_url, price, and spirit columns if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    columns = [
        ("description", "TEXT"),
        ("image_url", "TEXT"),
        ("price", "TEXT"),
        ("spirit", "TEXT") # New Spirit Column for filtering
    ]
    try:
        for col_name, col_type in columns:
            try:
                c.execute(f"ALTER TABLE recipes ADD COLUMN {col_name} {col_type}")
                print(f"Added column: {col_name}")
            except sqlite3.OperationalError:
                pass # Already exists
        conn.commit()
    except Exception as e:
        print(f"Error adding detail columns: {e}")
    finally:
        conn.close()

def update_recipe_details(recipe_id, description, price, image_url):
    """Updates the details for a specific recipe."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE recipes 
            SET description = ?, price = ?, image_url = ? 
            WHERE id = ?
        """, (description, price, image_url, recipe_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating details: {e}")
        return False
    finally:
        conn.close()

def backfill_details_from_json():
    """Updates existing DB records with data from menu.json."""
    import json
    if not os.path.exists("menu.json"): return

    print("Backfilling details from JSON...")
    try:
        with open("menu.json", "r") as f:
            data = json.load(f)
            
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        count = 0
        for item in data:
            # Map JSON fields
            desc = item.get('description', '')
            img = item.get('image_path', '')
            spirit = item.get('spirit', '')
            
            # Handle Price
            price_val = item.get('price', 0.0)
            price_str = ""
            try:
                if isinstance(price_val, (int, float)) and price_val > 0:
                    price_str = f"${price_val:.0f}"
                elif isinstance(price_val, str):
                     price_str = price_val
            except Exception:
                price_str = ""
            
            # Update matching recipe
            c.execute("""
                UPDATE recipes 
                SET description = ?, image_url = ?, price = ?, spirit = ?
                WHERE name = ?
            """, (desc, img, price_str, spirit, item.get('name')))
            
            if c.rowcount > 0:
                count += 1
                
        conn.commit()
        conn.close()
        print(f"Backfill complete. Updated {count} recipes.")
        
    except Exception as e:
        print(f"Backfill failed: {e}")

# Run init if this file is run directly
if __name__ == "__main__":
    init_db()
    add_category_column() 
    add_details_columns() # <--- NEW
    migrate_json_to_db()
    backfill_details_from_json() # <--- NEW