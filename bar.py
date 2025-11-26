import streamlit as st
import json
import time
import os
import re 
from PIL import Image, ExifTags # EXIF tags needed for fixing image rotation

# --- CORE HELPER FUNCTIONS ---

def convert_ml_to_oz(text):
    """Converts metric units in recipe text to US oz standards (rounded to 0.25oz)."""
    # Regex to find numbers followed by ml or cl
    pattern = r'(\d+\.?\d*)\s*(ml|cl)'
    
    def convert_match(match):
        value = float(match.group(1))
        unit = match.group(2)
        if unit == 'cl': value *= 10
        # Convert to Ounces (using 30ml = 1oz for bar accuracy)
        ounces = round(value / 30, 2)
        # Round to nearest quarter ounce logic
        if ounces % 0.25 != 0: ounces = round(ounces * 4) / 4
        return f"{ounces:.2f}oz" if ounces > 0 else "dash"

    return re.sub(pattern, convert_match, text, flags=re.IGNORECASE)

def clean_ingredient_name(line):
    """Removes leading amounts (numbers, oz, dashes) to get just the ingredient name for Guest View."""
    # Removes things like "2oz", "0.75", "1.5 ", "3 dashes" from the start of the string
    cleaned = re.sub(r'^[0-9.\s/]+(?:oz|ml|cl|dash|dashes)?\s*', '', line, flags=re.IGNORECASE)
    return cleaned.strip()

def load_menu():
    """Loads the cocktail menu from menu.json. Creates file with seed data if missing."""
    seed_data = [
        {"name": "Grand Margarita (Fixed)", "spirit": "Tequila", "description": "Patron Silver, Grand Marnier, Cointreau, agave nectar, orange and lime juices. NO BASIL.", "ingredients": ["Patron Silver", "Grand Marnier", "Cointreau", "Lime Juice", "Agave"], "spec_recipe": ["1.5oz Patron Silver", "0.5oz Grand Marnier", "0.5oz Cointreau", "1oz Fresh Lime Juice", "0.5oz Agave Nectar"], "glassware": "Rocks Glass", "garnish": "Salt Rim & Lime Wheel", "instructions": "Shake with ice, strain over fresh ice. NO BASIL.", "image_path": "", "is_classic": False, "is_cotw": False},
        {"name": "Southern Belle (Fresh)", "spirit": "Vodka", "description": "Absolut Raspberri, lime juice, muddled FRESH raspberries, simple syrup.", "ingredients": ["Absolut Raspberri", "Fresh Raspberries", "Lime", "Simple Syrup"], "spec_recipe": ["2oz Absolut Raspberri", "0.75oz Lime Juice", "0.5oz Simple Syrup", "4-5 Fresh Raspberries"], "glassware": "Coupe", "garnish": "3 Fresh Raspberries on pick", "instructions": "Muddle berries in tin. Add liquids. Shake hard double strain to remove seeds.", "image_path": "", "is_classic": False, "is_cotw": True}
    ]
    
    if os.path.exists("menu.json"):
        with open("menu.json", "r") as f:
            try:
                content = f.read()
                if not content: return []
                return json.loads(content)
            except json.JSONDecodeError:
                return []
    else:
        with open("menu.json", "w") as f:
            json.dump(seed_data, f, indent=4)
        return seed_data

def save_menu(menu_data):
    """Saves the updated cocktail menu to menu.json."""
    with open("menu.json", "w") as f:
        json.dump(menu_data, f, indent=4)

# --- START OF STREAMLIT APP LOGIC ---

def main():
    st.set_page_config(page_title="Digital Bar Manager", page_icon="🍸", layout="wide")

    # Custom CSS
    st.markdown("""
    <style>
        .stExpander { border: 1px solid #333; border-radius: 10px; margin-bottom: 10px; }
        .stButton>button { width: 100%; border-radius: 5px; }
        h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; font-weight: 300; }
    </style>
    """, unsafe_allow_html=True)
    
    # --- STATE INITIALIZATION ---
    if 'add_mode' not in st.session_state: st.session_state['add_mode'] = False
        
    # --- SIDEBAR ---
    st.sidebar.header("Configuration")
    bartender_mode = st.sidebar.toggle("Bartender Mode (Show Specs)", value=False)
    
    if bartender_mode:
        if st.sidebar.button("➕ Add New Spec"): st.session_state.add_mode = True 
        st.sidebar.caption("---")
    
    menu = load_menu()
    
    # --- FILTERING LOGIC ---
    # Determine all unique spirits for the filter dropdown
    all_spirits = sorted(list(set([d.get("spirit", "Other") for d in menu if d.get("spirit")])))
    inventory_filter = st.sidebar.multiselect("Inventory Filter", all_spirits)

    base_list = menu
    if inventory_filter:
        base_list = [d for d in base_list if d.get("spirit") in inventory_filter]

    # CATEGORIZATION LOGIC (Splitting items into Tabs)
    # Wines: Look for "Wine" or "Sparkling" in the spirit name
    wines = [d for d in base_list if "Wine" in d.get("spirit", "") or "Sparkling" in d.get("spirit", "")]
    # Beers: Look for "Beer"
    beers = [d for d in base_list if "Beer" in d.get("spirit", "")]
    # Cocktails: Everything else
    cocktails = [d for d in base_list if d not in wines and d not in beers]

    # --- MAIN PAGE VIEW SWITCH ---

    if st.session_state.add_mode:
        # --- VIEW A: ADMIN FORM ---
        st.title("➕ Enter New Specification")
        if st.button("← Back to Menu"):
            st.session_state.add_mode = False
            st.rerun()

        with st.form("new_drink_form", clear_on_submit=True):
            # EXPANDED Spirit List to include Beer/Wine options
            spirit_options = [
                "Gin", "Vodka", "Rum", "Tequila", "Whiskey", "Bourbon", "Rye", "Scotch", 
                "Brandy", "Red Wine", "White Wine", "Sparkling", "Beer", "Liqueur", "Other"
            ]
            
            name = st.text_input("Item Name")
            spirit = st.selectbox("Category / Base Spirit", spirit_options)
            price_input = st.number_input("Selling Price ($)", min_value=0.00, value=0.00, step=0.50, format="%.2f")
            description = st.text_area("Description (Guest Facing)")
            
            # COTW Logic
            is_cotw_input = st.checkbox("Set as Cocktail of the Week? (Removes previous COTW)")
            
            st.markdown("---")
            st.caption("Upload Final Presentation Photo")
            uploaded_file = st.file_uploader("Choose a photo (.png, .jpg)", type=["png", "jpg", "jpeg"])
            
            spec_recipe_raw = st.text_area("Specs / Pour Details (1 line per item)", help="For Cocktails: ingredients. For Wine/Beer: Bottle or Pour Size.")
            instructions = st.text_area("Instructions / Notes")
            glassware = st.text_input("Glassware")
            garnish = st.text_input("Garnish")

            submitted = st.form_submit_button("Add Item to Menu")

            if submitted:
                # Validation: Requires Name AND (Recipe OR it's a Beer/Wine which might not have recipe)
                is_simple_item = spirit in ['Red Wine', 'White Wine', 'Sparkling', 'Beer']
                
                if name and (spec_recipe_raw or is_simple_item):
                    
                    # 1. COTW SWAP LOGIC
                    # If this new drink is COTW, turn OFF COTW for everyone else first
                    if is_cotw_input:
                        for existing_drink in menu:
                            existing_drink['is_cotw'] = False
                    
                    # 2. IMAGE PROCESSING
                    image_path = ""
                    if uploaded_file is not None:
                        if not os.path.exists("images"): os.makedirs("images")
                        file_name = f"images/{name.replace(' ', '_').lower()}_{int(time.time())}.jpg"
                        
                        # Fix Image Rotation (iPhone Issue)
                        try:
                            image = Image.open(uploaded_file)
                            for orientation in ExifTags.TAGS.keys():
                                if ExifTags.TAGS[orientation]=='Orientation': break
                            exif = image._getexif()
                            if exif is not None and orientation in exif:
                                if exif[orientation] == 3: image=image.rotate(180, expand=True)
                                elif exif[orientation] == 6: image=image.rotate(270, expand=True)
                                elif exif[orientation] == 8: image=image.rotate(90, expand=True)
                            image.save(file_name)
                            image_path = file_name
                        except Exception as e:
                            # Fallback if rotation fails (e.g. no exif data), just save raw
                            with open(file_name, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            image_path = file_name

                    # 3. PREPARE DATA
                    raw_lines = [i.strip() for i in spec_recipe_raw.split('\n') if i.strip()]
                    
                    # Use cleaner only for cocktails generally, but safe to use on all
                    clean_ingredients = [clean_ingredient_name(line) for line in raw_lines]
                    converted_specs = [convert_ml_to_oz(line) for line in raw_lines]
                    
                    new_entry = {
                        "name": name, 
                        "spirit": spirit, 
                        "price": price_input,
                        "description": description, 
                        "ingredients": clean_ingredients, 
                        "spec_recipe": converted_specs, 
                        "glassware": glassware, 
                        "garnish": garnish, 
                        "instructions": instructions, 
                        "image_path": image_path, 
                        "is_classic": False, 
                        "is_cotw": is_cotw_input
                    }
                    
                    # 4. SAVE
                    menu.append(new_entry)
                    save_menu(menu)
                    
                    st.success(f"Successfully added {name}!")
                    time.sleep(0.5)
                    st.session_state.add_mode = False
                    st.rerun() 
                else:
                    st.error("Please enter a name and details.")
    
    else: 
        # --- VIEW B: MENU DISPLAY ---
        st.title("The Chop House")
        
        tab_cocktails, tab_other, tab_beer, tab_wine, tab_liquors, tab_import = st.tabs([
            "🍸 Craft Cocktails", "🍹 Other Cocktails", "🍺 Beer", "🍷 Wine", "🥃 Liquors", "🌍 Import Classics"
        ])

        # --- Helper for Displaying Drink Cards ---
        def display_drink_card(drink):
            header = drink['name']
            if drink.get('is_cotw'): header = f"⭐️ COCKTAIL OF THE WEEK: {drink['name']}"
            
            # Price Display
            price_display = ""
            if drink.get('price', 0) > 0:
                price_display = f" - ${drink.get('price'):.2f}"

            with st.expander(f"**{header}** ({drink['spirit']}){price_display}"):
                col_img, col_desc = st.columns([1, 2])
                with col_img:
                    if drink.get('image_path') and os.path.exists(drink['image_path']):
                        # Fixed deprecated warning
                        st.image(drink['image_path'], use_container_width=True)
                    else:
                        st.markdown("📷 *No Photo*")

                with col_desc:
                    st.write(f"_{drink.get('description', '')}_")
                    
                    if not bartender_mode:
                        # Guest View: Clean ingredients (no amounts)
                        if drink.get('ingredients'):
                            st.caption("Ingredients:")
                            st.write(", ".join(drink.get('ingredients', [])))
                        elif drink.get('spec_recipe'):
                             # Fallback for wines/beers if ingredients empty
                             st.write(", ".join(drink.get('spec_recipe', [])))

                    if bartender_mode:
                        st.markdown("---")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.markdown(f"**Glass:** {drink.get('glassware', 'N/A')}")
                            st.markdown(f"**Garnish:** {drink.get('garnish', 'N/A')}")
                        with c2:
                            st.markdown("**Specs:**")
                            for line in drink.get('spec_recipe', []):
                                st.markdown(f"- {line}")
                        st.caption("Instructions:")
                        st.info(drink.get('instructions', 'N/A'))
                        st.markdown("---")
                col_del, col_space = st.columns([1, 4])
                with col_del:
                    # Unique key is needed for every button
                    if st.button(f"🗑️ Delete", key=f"del_{drink['name']}"):
                        menu.remove(drink) # Removes the item from the list
                        save_menu(menu)    # Saves the file
                        st.toast(f"Deleted {drink['name']}!")
                        time.sleep(0.5)
                        st.rerun()         # Refreshes the page

        # --- Tab 1: CRAFT COCKTAILS ---
        with tab_cocktails:
            st.subheader("Our House Specs")
            if not cocktails:
                st.info("No cocktails found.")
            else:
                # Sort COTW first
                sorted_cocktails = sorted(cocktails, key=lambda x: (not x.get('is_cotw', False), x['name']))
                for drink in sorted_cocktails:
                    display_drink_card(drink)

        # --- Tab 3: BEER ---
        with tab_beer: 
            st.header("Draft & Bottle Selection")
            if not beers: st.info("No beers added yet.")
            for drink in beers: display_drink_card(drink)

        # --- Tab 4: WINE ---
        with tab_wine: 
            st.header("By the Glass")
            if not wines: st.info("No wines added yet.")
            for drink in wines: display_drink_card(drink)
                
        # --- OTHER TABS ---
        with tab_other: st.header("Easy Drinking Favorites")
        with tab_liquors: st.header("House Pour List")
        with tab_import: st.header("Import from IBA Cocktails"); st.info("Disabled.")

if __name__ == "__main__":
    main()