import streamlit as st
import json
import time
import os
import re 
from PIL import Image, ExifTags

# --- CORE HELPER FUNCTIONS ---

def convert_ml_to_oz(text):
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
    cleaned = re.sub(r'^[0-9.\s/]+(?:oz|ml|cl|dash|dashes)?\s*', '', line, flags=re.IGNORECASE)
    return cleaned.strip()

def format_price(price):
    if price is None or price == 0: return ""
    try:
        val = float(price)
        if val.is_integer(): return f"{int(val)}"
        return f"{val:.2f}"
    except (ValueError, TypeError): return ""

def load_menu():
    seed_data = [{"name": "Grand Margarita", "spirit": "Tequila", "description": "Seed data...", "ingredients": [], "spec_recipe": [], "glassware": "", "garnish": "", "instructions": "", "image_path": "", "is_classic": False, "is_cotw": False}]
    if os.path.exists("menu.json"):
        with open("menu.json", "r", encoding="utf-8") as f:
            try:
                content = f.read()
                if not content: return []
                return json.loads(content)
            except json.JSONDecodeError: return []
    else:
        with open("menu.json", "w", encoding="utf-8") as f:
            json.dump(seed_data, f, indent=4)
        return seed_data

def save_menu(menu_data):
    with open("menu.json", "w", encoding="utf-8") as f:
        json.dump(menu_data, f, indent=4)

# --- START OF STREAMLIT APP LOGIC ---

def main():
    st.set_page_config(page_title="The Well", page_icon="🥃", layout="wide")

    # Custom CSS for the HTML Rows
    st.markdown("""
    <style>
        .stExpander { border: 1px solid #333; border-radius: 10px; margin-bottom: 10px; }
        .stButton>button { width: 100%; border-radius: 5px; }
        h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; font-weight: 300; }
        
        /* Menu Row Styling */
        .menu-row {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            padding: 4px 0;
            border-bottom: 1px solid #333;
        }
        .menu-name { font-weight: 600; font-size: 1rem; }
        .menu-desc { font-style: italic; color: #888; font-size: 0.9rem; margin-left: 8px; }
        .menu-price { font-weight: 700; font-size: 1rem; white-space: nowrap; margin-left: 15px; }
        .featured-desc { font-size: 0.85rem; color: #bbb; margin-top: 4px; display: block; }
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
            st.session_state.edit_mode = False 
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

    # --- VIEW A: ADMIN FORM ---
    if st.session_state.add_mode or st.session_state.edit_mode:
        
        is_edit = st.session_state.edit_mode
        edit_item = st.session_state.editing_item if is_edit else {}
        
        page_title = f"✏️ Edit: {edit_item.get('name')}" if is_edit else "➕ Enter New Specification"
        st.title(page_title)
        
        if st.button("← Cancel"):
            st.session_state.add_mode = False
            st.session_state.edit_mode = False
            st.rerun()

        with st.form("drink_form", clear_on_submit=False): 
            spirit_options = ["Gin", "Vodka", "Rum", "Tequila", "Whiskey", "Bourbon", "Rye", "Scotch", "Brandy", "Red Wine", "White Wine", "Sparkling", "Beer", "Liqueur", "Non-Alcoholic", "Other"]
            
            def_name = edit_item.get('name', "")
            def_spirit = edit_item.get('spirit', "Vodka")
            if def_spirit not in spirit_options: def_spirit = "Other"
            def_price = float(edit_item.get('price', 0.00) or 0.00)
            def_desc = edit_item.get('description', "")
            def_cotw = edit_item.get('is_cotw', False)
            def_recipe = "\n".join(edit_item.get('spec_recipe', [])) if is_edit else ""
            def_instr = edit_item.get('instructions', "")
            def_glass = edit_item.get('glassware', "")
            def_garnish = edit_item.get('garnish', "")
            
            name = st.text_input("Item Name", value=def_name)
            spirit = st.selectbox("Category / Base Spirit", spirit_options, index=spirit_options.index(def_spirit))
            
            is_craft_selection = edit_item.get('is_craft', True)
            beer_type_selection = edit_item.get('beer_type', "Bottle/Can")
            is_well_selection = edit_item.get('is_well', False)
            
            if spirit == "Beer":
                beer_idx = 0 if beer_type_selection == "Bottle/Can" else 1
                beer_type_selection = st.radio("Beer Format", ["Bottle/Can", "Draft"], index=beer_idx, horizontal=True)
            elif spirit not in ['Red Wine', 'White Wine', 'Sparkling', 'Non-Alcoholic']:
                col_q1, col_q2 = st.columns(2)
                with col_q1:
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
            if is_edit and edit_item.get('image_path'):
                st.caption(f"Current Image: {edit_item.get('image_path')}")
            uploaded_file = st.file_uploader("Upload Photo", type=["png", "jpg", "jpeg"])
            
            spec_recipe_raw = st.text_area("Specs / Pour Details", value=def_recipe, help="For Wines: Enter '6oz: 8' and '9oz: 10' on separate lines.")
            instructions = st.text_area("Instructions", value=def_instr)
            glassware = st.text_input("Glassware", value=def_glass)
            garnish = st.text_input("Garnish", value=def_garnish)

            submitted = st.form_submit_button("Update Item" if is_edit else "Add Item to Menu")

            if submitted:
                if name: 
                    if is_cotw_input:
                        is_new_wine = "Wine" in spirit or "Sparkling" in spirit
                        for d in menu:
                            d_is_wine = "Wine" in d.get('spirit', '') or "Sparkling" in d.get('spirit', '')
                            if is_edit and d == edit_item: continue 
                            if is_new_wine and d_is_wine: d['is_cotw'] = False
                            elif not is_new_wine and not d_is_wine: d['is_cotw'] = False

                    image_path = edit_item.get('image_path', "") if is_edit else "" 
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
                            image.thumbnail((1000, 1000))
                            image.save(file_name, optimize=True, quality=80)
                            image_path = file_name
                        except Exception as e:
                            with open(file_name, "wb") as f: f.write(uploaded_file.getbuffer())
                            image_path = file_name

                    raw_lines = [i.strip() for i in spec_recipe_raw.split('\n') if i.strip()]
                    
                    if spirit in ['Red Wine', 'White Wine', 'Sparkling', 'Beer', 'Non-Alcoholic']:
                        final_ingredients = raw_lines 
                    else:
                        final_ingredients = [clean_ingredient_name(line) for line in raw_lines] 
                    
                    new_entry = {
                        "name": name, "spirit": spirit, "price": price_input, "description": description, 
                        "ingredients": final_ingredients, 
                        "spec_recipe": [convert_ml_to_oz(line) for line in raw_lines], 
                        "glassware": glassware, "garnish": garnish, "instructions": instructions, 
                        "image_path": image_path, "is_classic": False, "is_cotw": is_cotw_input,
                        "is_craft": is_craft_selection, "beer_type": beer_type_selection, "is_well": is_well_selection
                    }
                    
                    if is_edit:
                        try:
                            idx = menu.index(edit_item)
                            menu[idx] = new_entry
                            st.toast(f"Updated {name}!")
                        except ValueError: menu.append(new_entry)
                    else:
                        menu.append(new_entry)
                        st.toast(f"Added {name}!")

                    save_menu(menu)
                    time.sleep(0.5)
                    st.session_state.add_mode = False
                    st.session_state.edit_mode = False
                    st.rerun() 
                else: st.error("Name required.")
    
    # --- VIEW B: MENU DISPLAY ---
    else: 
        st.title("The Well")
        
        tab_featured, tab_cocktails, tab_other, tab_beer, tab_wine, tab_liquors, tab_na, tab_import = st.tabs([
            "✨ Featured Sips", "🍸 Craft Cocktails", "🍹 Other Cocktails", "🍺 Beer", "🍷 Wine", "🥃 Liquors", "🚫 Zero Proof", "🌍 Import"
        ])

        # --- DISPLAY FUNCTIONS ---

        def display_simple_row(drink, source_tab):
            # 1. PRICE CALCULATION
            price_str = ""
            
            # WINE LOGIC (6oz | 9oz | Btl)
            if drink.get('spirit') in ['Red Wine', 'White Wine']:
                data_source = drink.get('ingredients') if drink.get('ingredients') else drink.get('spec_recipe', [])
                
                p6, p9, pBtl = "-", "-", "-"
                for line in data_source:
                    val = line.split(":")[-1].strip().replace('$','')
                    if "6oz" in line: p6 = val
                    if "9oz" in line: p9 = val
                    if "Bottle" in line: pBtl = val
                
                if p6 != "-" or p9 != "-":
                    price_str = f"{p6} | {p9} | {pBtl}"
                else:
                    price_str = format_price(drink.get('price', 0))
            else:
                 price_str = format_price(drink.get('price', 0))

            # 2. NAME & DESC PREP
            icon = "⭐️ " if drink.get('is_cotw') else ""
            name_safe = drink['name']
            desc_safe = drink.get('description', '').replace('Bottle Only', '').strip().rstrip('.')
            
            # Hide inline description if featured (it moves to bottom)
            inline_desc = "" if drink.get('is_cotw') else desc_safe

            # 3. HTML RENDER (GUEST MODE) - Uses Flexbox for perfect spacing
            if not bartender_mode:
                html = f"""
                <div class="menu-row">
                    <div>
                        <span class="menu-name">{icon}{name_safe}</span>
                        <span class="menu-desc">{inline_desc}</span>
                    </div>
                    <div class="menu-price">{price_str}</div>
                </div>
                """
                if drink.get('is_cotw') and desc_safe:
                    html += f"<span class='featured-desc'>📝 {desc_safe}</span>"
                
                st.markdown(html, unsafe_allow_html=True)
            
            # 4. COLUMNS RENDER (BARTENDER MODE) - Needs columns for buttons
            else:
                c1, c2, c3 = st.columns([6, 2, 2])
                with c1: st.markdown(f"**{name_safe}** _{inline_desc}_")
                with c2: st.markdown(f"<div style='text-align: right; font-weight:bold'>{price_str}</div>", unsafe_allow_html=True)
                with c3:
                    c_edit, c_del = st.columns(2)
                    if c_edit.button("✏️", key=f"ed_{drink['name']}_{source_tab}"):
                        st.session_state.edit_mode = True
                        st.session_state.editing_item = drink
                        st.rerun()
                    if c_del.button("🗑️", key=f"del_{drink['name']}_{source_tab}"):
                        menu.remove(drink)
                        save_menu(menu)
                        st.rerun()
                st.markdown("---")


        def display_drink_card(drink, source_tab):
            header = drink['name']
            if drink.get('is_cotw'): header = f"⭐️ {drink['name']}"
            price_display = ""
            if drink.get('price', 0) > 0: price_display = f" - {format_price(drink.get('price'))}"

            with st.expander(f"**{header}**{price_display}"):
                col_img, col_desc = st.columns([1, 2])
                with col_img:
                    if drink.get('image_path') and os.path.exists(drink['image_path']):
                        st.image(drink['image_path'], width=150)
                    else:
                        st.markdown("📷 *No Photo*")

                with col_desc:
                    st.write(drink.get('description', ''))
                    if not bartender_mode:
                        if drink.get('ingredients'): st.caption("Specs:"); st.write(", ".join(drink.get('ingredients', [])))
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
                st.subheader("🍺 Draft")
                for drink in drafts: display_simple_row(drink, "beer_draft")
            with c2:
                st.subheader("🍾 Bottle / Can")
                for drink in bottles: display_simple_row(drink, "beer_bottle")

        with tab_wine: 
            reds = [d for d in wines if "Red" in d['spirit']]
            whites = [d for d in wines if "White" in d['spirit']]
            sparkling = [d for d in wines if "Sparkling" in d['spirit']]

            def is_bottle_only(d): return "Bottle Only" in d.get('description', '')

            reds_glass = [d for d in reds if not is_bottle_only(d)]
            reds_reserve = [d for d in reds if is_bottle_only(d)]
            
            whites_glass = [d for d in whites if not is_bottle_only(d)]
            whites_reserve = [d for d in whites if is_bottle_only(d)]
            
            # --- SIDE-BY-SIDE LAYOUT (NOW WORKS WITH HTML ROWS!) ---
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("### 🍷 Reds ( 6oz | 9oz | Btl )")
                for drink in reds_glass: display_simple_row(drink, "wine_red")
                
                if reds_reserve:
                    st.markdown("---")
                    st.subheader("🍾 Red Reserve (Bottle Only)")
                    for drink in reds_reserve: display_simple_row(drink, "red_res")

            with c2:
                st.markdown("### 🥂 Whites ( 6oz | 9oz | Btl )")
                for drink in whites_glass: display_simple_row(drink, "wine_white")

                if whites_reserve:
                    st.markdown("---")
                    st.subheader("🍾 White Reserve (Bottle Only)")
                    for drink in whites_reserve: display_simple_row(drink, "white_res")

                if sparkling:
                    st.markdown("---")
                    st.markdown("### 🫧 Bubbles")
                    for drink in sparkling: display_simple_row(drink, "wine_sparkling")
        
        with tab_liquors:
            wells = [d for d in liquors if d.get('is_well')]
            shelf = [d for d in liquors if not d.get('is_well')]
            if wells:
                st.header("⭐ Premium Well")
                for drink in wells: display_simple_row(drink, "well")
                st.markdown("---")
            st.header("House Pour List")
            unique_spirits = sorted(list(set([d['spirit'] for d in shelf])))
            for spirit_type in unique_spirits:
                st.subheader(f"{spirit_type}")
                these_drinks = [d for d in shelf if d['spirit'] == spirit_type]
                for drink in these_drinks: display_simple_row(drink, f"liq_{spirit_type}")
                    
        with tab_na:
            st.header("🚫 Zero Proof")
            if not na_drinks: st.info("No NA options added yet.")
            for drink in na_drinks: display_simple_row(drink, "na")

        with tab_import: st.header("Import from IBA Cocktails"); st.info("Disabled.")

if __name__ == "__main__":
    main()