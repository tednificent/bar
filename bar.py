import streamlit as st
import json
import time
import os
import re 
from PIL import Image, ExifTags

# --- CORE HELPER FUNCTIONS ---

def convert_ml_to_oz(text):
    """Converts metric units in recipe text to US oz standards (rounded to 0.25oz)."""
    pattern = r'(\d+\.?\d*)\s*(ml|cl)'
    
    def convert_match(match):
        value = float(match.group(1))
        unit = match.group(2)
        if unit == 'cl': value *= 10
        ounces = round(value / 30, 2)
        if ounces % 0.25 != 0: ounces = round(ounces * 4) / 4
        return f"{ounces:.2f}oz" if ounces > 0 else "dash"

    return re.sub(pattern, convert_match, text, flags=re.IGNORECASE)

def clean_ingredient_name(line):
    """Removes leading amounts (numbers, oz, dashes) to get just the ingredient name."""
    cleaned = re.sub(r'^[0-9.\s/]+(?:oz|ml|cl|dash|dashes)?\s*', '', line, flags=re.IGNORECASE)
    return cleaned.strip()

def load_menu():
    """Loads the cocktail menu from menu.json."""
    seed_data = [{"name": "Grand Margarita", "spirit": "Tequila", "description": "Seed data...", "ingredients": [], "spec_recipe": [], "glassware": "", "garnish": "", "instructions": "", "image_path": "", "is_classic": False, "is_cotw": False}]
    
    if os.path.exists("menu.json"):
        with open("menu.json", "r", encoding="utf-8") as f:
            try:
                content = f.read()
                if not content: return []
                return json.loads(content)
            except json.JSONDecodeError:
                return []
    else:
        with open("menu.json", "w", encoding="utf-8") as f:
            json.dump(seed_data, f, indent=4)
        return seed_data

def save_menu(menu_data):
    """Saves the updated cocktail menu to menu.json."""
    with open("menu.json", "w", encoding="utf-8") as f:
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
    all_spirits = sorted(list(set([d.get("spirit", "Other") for d in menu if d.get("spirit")])))
    inventory_filter = st.sidebar.multiselect("Inventory Filter", all_spirits)

    base_list = menu
    if inventory_filter:
        base_list = [d for d in base_list if d.get("spirit") in inventory_filter]

    # --- CATEGORIZATION LOGIC ---
    wines = [d for d in base_list if "Wine" in d.get("spirit", "") or "Sparkling" in d.get("spirit", "")]
    beers = [d for d in base_list if "Beer" in d.get("spirit", "")]
    all_cocktails = [d for d in base_list if d not in wines and d not in beers]
    
    # SPLIT COCKTAILS: Check for 'is_craft' key. Default to True if missing.
    craft_cocktails = [d for d in all_cocktails if d.get('is_craft', True)]
    other_cocktails = [d for d in all_cocktails if not d.get('is_craft', True)]

    featured_items = [d for d in base_list if d.get('is_cotw')]

    # --- VIEW A: ADMIN FORM ---
    if st.session_state.add_mode:
        st.title("➕ Enter New Specification")
        if st.button("← Back to Menu"):
            st.session_state.add_mode = False
            st.rerun()

        with st.form("new_drink_form", clear_on_submit=True):
            spirit_options = ["Gin", "Vodka", "Rum", "Tequila", "Whiskey", "Bourbon", "Rye", "Scotch", "Brandy", "Red Wine", "White Wine", "Sparkling", "Beer", "Liqueur", "Other"]
            
            name = st.text_input("Item Name")
            spirit = st.selectbox("Category / Base Spirit", spirit_options)
            
            # --- COCKTAIL TYPE SELECTOR ---
            is_craft_selection = True
            if spirit not in ['Red Wine', 'White Wine', 'Sparkling', 'Beer']:
                type_choice = st.radio("List Section", ["✨ Craft / House Spec", "🍹 Other / Standard"], horizontal=True)
                is_craft_selection = (type_choice == "✨ Craft / House Spec")

            price_input = st.number_input("Selling Price ($)", min_value=0.00, value=0.00, step=0.50, format="%.2f")
            description = st.text_area("Description (Guest Facing)")
            
            is_cotw_input = st.checkbox("✨ Set as Featured Item? (Replaces current Featured Item of same type)")
            
            st.markdown("---")
            uploaded_file = st.file_uploader("Upload Photo", type=["png", "jpg", "jpeg"])
            spec_recipe_raw = st.text_area("Specs / Pour Details", help="1 line per item")
            instructions = st.text_area("Instructions")
            glassware = st.text_input("Glassware")
            garnish = st.text_input("Garnish")

            submitted = st.form_submit_button("Add Item to Menu")

            if submitted:
                is_simple_item = spirit in ['Red Wine', 'White Wine', 'Sparkling', 'Beer']
                
                if name and (spec_recipe_raw or is_simple_item):
                    
                    # --- SMART FEATURED LOGIC ---
                    if is_cotw_input:
                        is_new_wine = "Wine" in spirit or "Sparkling" in spirit
                        for d in menu:
                            d_is_wine = "Wine" in d.get('spirit', '') or "Sparkling" in d.get('spirit', '')
                            if is_new_wine and d_is_wine: d['is_cotw'] = False
                            elif not is_new_wine and not d_is_wine: d['is_cotw'] = False

                    # --- IMAGE PROCESSING ---
                    image_path = ""
                    if uploaded_file is not None:
                        if not os.path.exists("images"): os.makedirs("images")
                        file_name = f"images/{name.replace(' ', '_').lower()}_{int(time.time())}.jpg"
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
                        except:
                            with open(file_name, "wb") as f: f.write(uploaded_file.getbuffer())
                            image_path = file_name

                    raw_lines = [i.strip() for i in spec_recipe_raw.split('\n') if i.strip()]
                    
                    new_entry = {
                        "name": name, 
                        "spirit": spirit, 
                        "price": price_input, 
                        "description": description, 
                        "ingredients": [clean_ingredient_name(line) for line in raw_lines], 
                        "spec_recipe": [convert_ml_to_oz(line) for line in raw_lines], 
                        "glassware": glassware, 
                        "garnish": garnish, 
                        "instructions": instructions, 
                        "image_path": image_path, 
                        "is_classic": False, 
                        "is_cotw": is_cotw_input,
                        "is_craft": is_craft_selection
                    }
                    menu.append(new_entry)
                    save_menu(menu)
                    st.success(f"Added {name}!")
                    time.sleep(0.5)
                    st.session_state.add_mode = False
                    st.rerun() 
                else:
                    st.error("Name required.")
    
    # --- VIEW B: MENU DISPLAY ---
    else: 
        st.title("The Chop House")
        
        tab_featured, tab_cocktails, tab_other, tab_beer, tab_wine, tab_liquors, tab_import = st.tabs([
            "✨ Featured Sips", "🍸 Craft Cocktails", "🍹 Other Cocktails", "🍺 Beer", "🍷 Wine", "🥃 Liquors", "🌍 Import Classics"
        ])

        def display_drink_card(drink, source_tab):
            header = drink['name']
            if drink.get('is_cotw'): header = f"⭐️ {drink['name']}"
            price_display = ""
            if drink.get('price', 0) > 0: price_display = f" - ${drink.get('price'):.2f}"

            with st.expander(f"**{header}** ({drink['spirit']}){price_display}"):
                col_img, col_desc = st.columns([1, 2])
                with col_img:
                    if drink.get('image_path') and os.path.exists(drink['image_path']):
                        st.image(drink['image_path'], use_container_width=True)
                    else:
                        st.markdown("📷 *No Photo*")

                with col_desc:
                    # FIX 1: Removed Underscores
                    st.write(drink.get('description', ''))
                    
                    if not bartender_mode:
                        if drink.get('ingredients'): st.caption("Ingredients:"); st.write(", ".join(drink.get('ingredients', [])))
                        elif drink.get('spec_recipe'): st.write(", ".join(drink.get('spec_recipe', [])))

                    if bartender_mode:
                        st.markdown("---")
                        c1, c2 = st.columns(2)
                        with c1: st.markdown(f"**Glass:** {drink.get('glassware', 'N/A')}"); st.markdown(f"**Garnish:** {drink.get('garnish', 'N/A')}")
                        with c2: 
                            st.markdown("**Specs:**")
                            # FIX 2: Replaced list comprehension with proper loop to prevent DeltaGenerator error
                            for line in drink.get('spec_recipe', []):
                                st.markdown(f"- {line}")
                                
                        st.caption("Instructions:"); st.info(drink.get('instructions', 'N/A'))
                        
                        st.markdown("---")
                        if st.button(f"🗑️ Delete", key=f"del_{drink['name']}_{source_tab}"):
                            menu.remove(drink)
                            save_menu(menu)
                            st.rerun()

        with tab_featured:
            st.header("⭐️ Weekly Features")
            if not featured_items: st.info("No features selected this week.")
            else:
                for drink in featured_items: display_drink_card(drink, "featured")

        with tab_cocktails:
            st.subheader("Our House Specs")
            if not craft_cocktails: st.info("No House Specs added.")
            else:
                for drink in sorted(craft_cocktails, key=lambda x: x['name']): display_drink_card(drink, "craft")

        with tab_other: 
            st.header("Standard & Classics")
            if not other_cocktails: st.info("No standard cocktails added.")
            else:
                for drink in sorted(other_cocktails, key=lambda x: x['name']): display_drink_card(drink, "other")

        with tab_beer: 
            st.header("Draft & Bottle Selection")
            for drink in beers: display_drink_card(drink, "beer")

        with tab_wine: 
            st.header("By the Glass")
            for drink in wines: display_drink_card(drink, "wine")
                
        with tab_liquors: st.header("House Pour List")
        with tab_import: st.header("Import from IBA Cocktails"); st.info("Disabled.")

if __name__ == "__main__":
    main()