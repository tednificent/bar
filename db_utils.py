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
        c.execute("SELECT * FROM recipes")
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
        c.execute("INSERT INTO recipes (name, instructions) VALUES (?, ?)", 
                  (recipe_data.get('name'), recipe_data.get('instructions', '')))
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
if __name__ == "__main__":
    init_db() 
    add_category_column() # <-- Add this line here
    migrate_json_to_db()
# Run init if this file is run directly
if __name__ == "__main__":
    init_db()