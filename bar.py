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
    if 'edit_mode' not in st.session_state: st.session_state['edit_mode'] = False
    if 'editing_item' not in st.session_state: st.session_state['editing_item'] = None
        
    # --- SIDEBAR ---
    st.sidebar.header("Configuration")
    bartender_mode = st.sidebar.toggle("Bartender Mode (Show Specs)", value=False)
    
    if bartender_mode:
        if st.sidebar.button("➕ Add New Spec"): 
            st.session_state.add_mode = True
            st.session_state.edit_mode = False # Ensure we aren't editing
            st.session_state.editing_item = None
            st.rerun()
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
    na_drinks = [d for d in base_list if "Non-Alcoholic" in d.get("spirit", "")]
    liquors = [d for d in base_list if d.get("spirit") not in ["Beer", "Red Wine", "White Wine", "Sparkling", "Non-Alcoholic"] and not d.get("spec_recipe")]
    all_cocktails = [d for d in base_list if d not in wines and d not in beers and d not in na_drinks and d not in liquors]
    
    craft_cocktails = [d for d in all_cocktails if d.get('is_craft', True)]
    other_cocktails = [d for d in all_cocktails if not d.get('is_craft', True)]
    featured_items = [d for d in base_list if d.get('is_cotw')]

    # --- VIEW A: ADMIN FORM (SHARED FOR ADD & EDIT) ---
    if st.session_state.add_mode or st.session_state.edit_mode:
        
        # PRE-FILL LOGIC
        is_edit = st.session_state.edit_mode
        edit_item = st.session_state.editing_item if is_edit else {}
        
        page_title = f"✏️ Edit: {edit_item.get('name')}" if is_edit else "➕ Enter New Specification"
        st.title(page_title)
        
        if st.button("← Cancel"):
            st.session_state.add_mode = False
            st.session_state.edit_mode = False
            st.rerun()

        with st.form("drink_form", clear_on_submit=False): # Changed to False to keep edits visible if error
            spirit_options = ["Gin", "Vodka", "Rum", "Tequila", "Whiskey", "Bourbon", "Rye", "Scotch", "Brandy", "Red Wine", "White Wine", "Sparkling", "Beer", "Liqueur", "Non-Alcoholic", "Other"]
            
            # DEFAULT VALUES
            def_name = edit_item.get('name', "")
            def_spirit = edit_item.get('spirit', "Vodka")
            if def_spirit not in spirit_options: def_spirit = "Other"
            def_price = float(edit_item.get('price', 0.00))
            def_desc = edit_item.get('description', "")
            def_cotw = edit_item.get('is_cotw', False)
            def_recipe = "\n".join(edit_item.get('spec_recipe', [])) if is_edit else ""
            def_instr = edit_item.get('instructions', "")
            def_glass = edit_item.get('glassware', "")
            def_garnish = edit_item.get('garnish', "")
            
            # FORM WIDGETS
            name = st.text_input("Item Name", value=def_name)
            spirit = st.selectbox("Category / Base Spirit", spirit_options, index=spirit_options.index(def_spirit))
            
            # --- DYNAMIC DEFAULTS ---
            is_craft_selection = edit_item.get('is_craft', True)
            beer_type_selection = edit_item.get('beer_type', "Bottle/Can")
            is_well_selection = edit_item.get('is_well', False)
            
            # Dynamic Toggles
            if spirit == "Beer":
                beer_idx = 0 if beer_type_selection == "Bottle/Can" else 1
                beer_type_selection = st.radio("Beer Format", ["Bottle/Can", "Draft"], index=beer_idx, horizontal=True)
            elif spirit not in ['Red Wine', 'White Wine', 'Sparkling', 'Non-Alcoholic']:
                col_q1, col_q2 = st.columns(2)
                with col_q1:
                   # Cocktail Type
                   craft_idx = 0 if is_craft_selection else 1
                   type_choice = st.radio("List Section (For Cocktails)", ["✨ Craft / House Spec", "🍹 Other / Standard"], index=craft_idx, horizontal=True)
                   is_craft_selection = (type_choice == "✨ Craft / House Spec")
                with col_q2:
                   st.markdown("<br>", unsafe_allow_html=True) 
                   is_well_selection = st.checkbox("Set as House/Premium Well? (For Liquors)", value=is_well_selection)

            price_input = st.number_input("Selling Price ($)", min_value=0.00, value=def_price, step=0.50, format="%.2f")
            description = st.text_area("Description (Guest Facing)", value=def_desc)
            is_cotw_input = st.checkbox("✨ Set as Featured Item?", value=def_cotw)
            
            st.markdown("---")
            # Image handling note: We can't pre-fill the file uploader, but we can preserve the old path
            if is_edit and edit_item.get('image_path'):
                st.caption(f"Current Image: {edit_item.get('image_path')}")
                st.info("Upload a new photo ONLY if you want to replace the current one.")
            
            uploaded_file = st.file_uploader("Upload Photo", type=["png", "jpg", "jpeg"])
            
            spec_recipe_raw = st.text_area("Specs / Pour Details", value=def_recipe, help="Leave BLANK if this is just a bottle of liquor.")
            instructions = st.text_area("Instructions", value=def_instr)
            glassware = st.text_input("Glassware", value=def_glass)
            garnish = st.text_input("Garnish", value=def_garnish)

            btn_label = "Update Item" if is_edit else "Add Item to Menu"
            submitted = st.form_submit_button(btn_label)

            if submitted:
                # Validation
                is_simple_item = spirit in ['Red Wine', 'White Wine', 'Sparkling', 'Beer', 'Non-Alcoholic'] or not spec_recipe_raw
                
                if name: 
                    # 1. Handle Feature Toggle Logic
                    if is_cotw_input:
                        is_new_wine = "Wine" in spirit or "Sparkling" in spirit
                        for d in menu:
                            d_is_wine = "Wine" in d.get('spirit', '') or "Sparkling" in d.get('spirit', '')
                            # Only uncheck if we are NOT the item currently being edited
                            if is_edit and d == edit_item: continue 
                            if is_new_wine and d_is_wine: d['is_cotw'] = False
                            elif not is_new_wine and not d_is_wine: d['is_cotw'] = False

                    # 2. Image Processing
                    image_path = edit_item.get('image_path', "") if is_edit else "" # Default to old path
                    
                    if uploaded_file is not None:
                        # If new file provided, process it
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
                            image.thumbnail((1000, 1000))
                            image.save(file_name, optimize=True, quality=80)
                            image_path = file_name
                        except Exception as e:
                            with open(file_name, "wb") as f: f.write(uploaded_file.getbuffer())
                            image_path = file_name

                    raw_lines = [i.strip() for i in spec_recipe_raw.split('\n') if i.strip()]
                    
                    new_entry = {
                        "name": name, "spirit": spirit, "price": price_input, "description": description, 
                        "ingredients": [clean_ingredient_name(line) for line in raw_lines], 
                        "spec_recipe": [convert_ml_to_oz(line) for line in raw_lines], 
                        "glassware": glassware, "garnish": garnish, "instructions": instructions, 
                        "image_path": image_path, "is_classic": False, "is_cotw": is_cotw_input,
                        "is_craft": is_craft_selection, "beer_type": beer_type_selection, "is_well": is_well_selection
                    }
                    
                    # 3. SAVE LOGIC
                    if is_edit:
                        # Find the index of the original item and update it
                        try:
                            idx = menu.index(edit_item)
                            menu[idx] = new_entry
                            st.toast(f"Updated {name}!")
                        except ValueError:
                            # Fallback if item not found (rare)
                            menu.append(new_entry)
                    else:
                        menu.append(new_entry)
                        st.toast(f"Added {name}!")

                    save_menu(menu)
                    time.sleep(0.5)
                    st.session_state.add_mode = False
                    st.session_state.edit_mode = False
                    st.rerun() 
                else:
                    st.error("Name required.")
    
    # --- VIEW B: MENU DISPLAY ---
    else: 
        st.title("The Chop House")
        
        tab_featured, tab_cocktails, tab_other, tab_beer, tab_wine, tab_liquors, tab_na, tab_import = st.tabs([
            "✨ Featured Sips", "🍸 Craft Cocktails", "🍹 Other Cocktails", "🍺 Beer", "🍷 Wine", "🥃 Liquors", "🚫 Zero Proof", "🌍 Import"
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
                        st.image(drink['image_path'], width=150)
                    else:
                        st.markdown("📷 *No Photo*")

                with col_desc:
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
                            for line in drink.get('spec_recipe', []): st.markdown(f"- {line}")
                        st.caption("Instructions:"); st.info(drink.get('instructions', 'N/A'))
                        
                        st.markdown("---")
                        # EDIT AND DELETE BUTTONS
                        c_edit, c_del = st.columns([1, 1])
                        with c_edit:
                            if st.button(f"✏️ Edit", key=f"edit_{drink['name']}_{source_tab}"):
                                st.session_state.edit_mode = True
                                st.session_state.editing_item = drink
                                st.rerun()
                        with c_del:
                            if st.button(f"🗑️ Delete", key=f"del_{drink['name']}_{source_tab}"):
                                menu.remove(drink)
                                save_menu(menu)
                                st.rerun()

        # --- TABS RENDERING ---

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
            for drink in sorted(other_cocktails, key=lambda x: x['name']): display_drink_card(drink, "other")

        with tab_beer: 
            drafts = [d for d in beers if d.get('beer_type') == "Draft"]
            bottles = [d for d in beers if d.get('beer_type') != "Draft"]
            c1, c2 = st.columns(2)
            with c1:
                st.header("🍺 Draft")
                for drink in drafts: display_drink_card(drink, "beer_draft")
            with c2:
                st.header("🍾 Bottle / Can")
                for drink in bottles: display_drink_card(drink, "beer_bottle")

        with tab_wine: 
            reds = [d for d in wines if "Red" in d['spirit']]
            whites = [d for d in wines if "White" in d['spirit'] or "Sparkling" in d['spirit']]
            c1, c2 = st.columns(2)
            with c1:
                st.header("🍷 Reds")
                for drink in reds: display_drink_card(drink, "wine_red")
            with c2:
                st.header("🥂 White & Bubbles")
                for drink in whites: display_drink_card(drink, "wine_white")
        
        with tab_liquors:
            wells = [d for d in liquors if d.get('is_well')]
            shelf = [d for d in liquors if not d.get('is_well')]
            if wells:
                st.header("⭐ Premium Well")
                for drink in wells: display_drink_card(drink, "well")
                st.markdown("---")
            st.header("House Pour List")
            unique_spirits = sorted(list(set([d['spirit'] for d in shelf])))
            for spirit_type in unique_spirits:
                st.subheader(f"{spirit_type}")
                these_drinks = [d for d in shelf if d['spirit'] == spirit_type]
                for drink in these_drinks: display_drink_card(drink, f"liq_{spirit_type}")
                    
        with tab_na:
            st.header("🚫 Zero Proof")
            if not na_drinks: st.info("No NA options added yet.")
            for drink in na_drinks: display_drink_card(drink, "na")

        with tab_import: st.header("Import from IBA Cocktails"); st.info("Disabled.")

if __name__ == "__main__":
    main()