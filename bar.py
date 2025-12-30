import streamlit as st
import json
import time
from PIL import Image
# Rebuilding app
# --- CUSTOM DATABASE UTILS ---
# This file handles all the talking to your new SQLite database
from db_utils import get_all_recipes, save_new_recipe, convert_ml_to_oz
# NEW: Import admin functions
from db_utils import delete_recipe, update_recipe_category, update_recipe_details, update_whole_recipe

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="My Digital Bar", layout="wide")

# --- 2. SESSION STATE SETUP ---
if 'bartender_mode' not in st.session_state:
    st.session_state.bartender_mode = False
if 'show_import_menu' not in st.session_state:
    st.session_state.show_import_menu = False

# --- 3. HELPER: DIALOGS ---
@st.dialog("Edit Recipe")
def edit_recipe_dialog(recipe):
    # Form Inputs
    new_name = st.text_input("Name", value=recipe['name'])
    new_cat = st.selectbox("Category", 
        ['Featured Sips', 'Craft Cocktails', 'Classics', 'Beer', 'Wine', 'Liquors', 'Zero Proof'],
        index=['Featured Sips', 'Craft Cocktails', 'Classics', 'Beer', 'Wine', 'Liquors', 'Zero Proof'].index(recipe['category']) if recipe['category'] in ['Featured Sips', 'Craft Cocktails', 'Classics', 'Beer', 'Wine', 'Liquors', 'Zero Proof'] else 2
    )
    new_desc = st.text_area("Description", value=recipe.get('description') or "")
    new_spirit = st.text_input("Spirit (Sub-grouping)", value=recipe.get('spirit') or "", help="Used for filtering wines (Red Wine, White Wine, etc.)")
    new_price = st.text_input("Price", value=recipe.get('price') or "")
    new_img = st.text_input("Image URL", value=recipe.get('image_url') or "")
    
    # Specs (Joined by newlines for editing)
    specs_str = "\n".join(recipe.get('specs', []))
    new_specs_block = st.text_area("Ingredients (One per line)", value=specs_str, height=150)
    
    new_instr = st.text_area("Instructions", value=recipe.get('instructions') or "", height=150)
    
    if st.button("Save Changes"):
        # Process Specs back to list
        new_specs_list = [line.strip() for line in new_specs_block.split('\n') if line.strip()]
        
        data = {
            'name': new_name,
            'category': new_cat,
            'description': new_desc,
            'price': new_price,
            'image_url': new_img,
            'instructions': new_instr,
            'specs': new_specs_list,
            'spirit': new_spirit
        }
        
        if update_whole_recipe(recipe['id'], data):
            st.success("Recipe Updated!")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("Update failed.")

@st.dialog("Add New Drink")
def add_recipe_dialog():
    st.info("Create a new menu item.")
    name = st.text_input("Name")
    cat = st.selectbox("Category", ['Featured Sips', 'Craft Cocktails', 'Classics', 'Beer', 'Wine', 'Liquors', 'Zero Proof'])
    desc = st.text_area("Description")
    spirit = st.text_input("Spirit / Sub-type", help="e.g. Red Wine, White Wine for filtering")
    price = st.text_input("Price (e.g. $12)")
    img = st.text_input("Image URL")
    specs_block = st.text_area("Ingredients / Specs (One per line)")
    instr = st.text_area("Instructions")
    
    if st.button("Create Drink"):
        if not name:
            st.error("Name is required.")
            return

        specs_list = [line.strip() for line in specs_block.split('\n') if line.strip()]
        data = {
            'name': name,
            'category': cat,
            'description': desc,
            'price': price,
            'image_url': img,
            'instructions': instr,
            'specs': specs_list,
            'spirit': spirit
        }
        if save_new_recipe(data):
            st.success("Added new drink!")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("Failed to save (Name might use duplicate?).")


# --- 4. SIDEBAR (SETTINGS) ---
def toggle_bartender_mode():
    pass 

with st.sidebar:
    st.title("Settings")
    # The Toggle Switch for Bartender Mode
    st.session_state.bartender_mode = st.toggle(
        "Bartender Mode", 
        value=st.session_state.bartender_mode,
        key="bartender_toggle" 
    )
    
    if st.session_state.bartender_mode:
        st.info("🔧 Top Shelf Mode Active")
        st.markdown("---")
        st.subheader("Admin Tools")
        if st.button("➕ Add New Drink"):
            add_recipe_dialog()

# --- 5. MAIN APP LOGIC (Your Menu) ---
st.title("🍸 The Home Bar")

# A. Load Active Recipes from Database
active_recipes = get_all_recipes()

# B. Display Your Bar (The Menu)
if not active_recipes:
    st.info("Your bar is empty! Switch to Bartender Mode to import recipes.")
else:
    # Categories
    card_categories = ['Featured Sips', 'Craft Cocktails', 'Classics', 'Zero Proof']
    list_categories = ['Beer', 'Wine', 'Liquors']
    
    grouped_recipes = {cat: [] for cat in card_categories + list_categories}
    
    for recipe in active_recipes:
        cat = recipe.get('category')
        all_cats = card_categories + list_categories
        if not cat or cat not in all_cats:
            cat = 'Classics'
        grouped_recipes[cat].append(recipe)

    # --- PART 1: COCKTAIL CARDS (Collapsible) ---
    for cat in card_categories:
        recipes = grouped_recipes[cat]
        if not recipes: continue
            
        st.header(cat)
        
        # Grid Display
        cols = st.columns(3) 
        for i, recipe in enumerate(recipes):
            with cols[i % 3]:
                # NEW: Collapsible Card Logic
                # The Header is the Expander Label
                with st.expander(f"**{recipe['name']}**", expanded=False):
                    
                    # Image
                    if recipe.get('image_url'):
                        try:
                            st.image(recipe['image_url'], width=300)
                        except:
                            pass 

                    # Description
                    if recipe.get('description'):
                        st.caption(f"*{recipe['description']}*")
                    
                    # Price
                    if recipe.get('price'):
                         st.write(f"**{recipe['price']}**")

                    # Ingredients / Specs (Always show in expander for cards? 
                    # Prompt says "Guest can click to see photo and details".
                    # Details usually implies specs/ingredients for guests? 
                    # Original prompt said guest mode hides specs. 
                    # User: "Inside the expander, place ... Ingredients/Specs." 
                    # User didn't restrict this to bartender only in this specific request.
                    # I will assuming transparency is desired inside the click, or I should stick to 'Specs only if Bartender'.
                    # "This ensures the menu is clean... but guests can click to see... details." 
                    # I'll show ingredients list (specs) to everyone inside the expander, as requested.)
                    
                    st.markdown("#### Ingredients")
                    if recipe.get('specs'):
                        for line in recipe['specs']:
                            st.markdown(f"- {line}")
                    
                    # Instructions (Still maybe bartender only? Or everyone? 
                    # Let's keep instructions separate or at bottom. 
                    # Prompt said "Inside expander... Image, Description, and Ingredients/Specs".
                    # It didn't mention instructions. I'll hide instructions for guests to keep "Privacy" logic akin to before.)
                    
                    if st.session_state.bartender_mode:
                        st.markdown("---")
                        st.markdown("**Instructions:**")
                        st.write(recipe.get('instructions', "No instructions."))
                    
                    # Admin Controls inside
                    if st.session_state.bartender_mode:
                        st.markdown("---")
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("Edit", key=f"edit_{recipe['id']}"):
                                edit_recipe_dialog(recipe)
                        with c2:
                            if st.button("Delete", key=f"del_{recipe['id']}"):
                                if delete_recipe(recipe['id']):
                                    st.rerun()


    # --- PART 2: LIST VIEW (Beer/Wine - Tight) ---
    st.markdown("---")
    
    for cat in list_categories:
        recipes = grouped_recipes[cat]
        if not recipes: continue
        
        st.header(cat)
        
        # WINE SUB-GROUPING
        if cat == 'Wine':
            # Predefined Sub-Groups
            wine_subgroups = ['House Wine', 'Red Wine', 'White Wine', 'Bubbles']
            # We sort recipes into these buckets
            wines_by_type = {sub: [] for sub in wine_subgroups}
            others = []
            
            for r in recipes:
                # Filter by Spirit field (populated by migration or manually)
                # Fallback to checking name if spirit is empty?
                s = r.get('spirit', '')
                if s in wine_subgroups:
                    wines_by_type[s].append(r)
                elif 'Red' in s: wines_by_type['Red Wine'].append(r)
                elif 'White' in s: wines_by_type['White Wine'].append(r)
                elif 'Sparkling' in s or 'Bubbles' in s or 'Champagne' in s: wines_by_type['Bubbles'].append(r)
                else:
                    others.append(r) # Fallback
            
            # Display Subgroups
            for sub in wine_subgroups:
                if wines_by_type[sub]:
                    st.subheader(sub)
                    for r in wines_by_type[sub]:
                        # Tight MD Block
                        price_span = f"<b>{r['price']}</b>" if r.get('price') else ""
                        desc_span = f"<i>{r['description']}</i>" if r.get('description') else ""
                        row_html = f"""
                        <div style="line-height:1.4; margin-bottom: 4px;">
                            <b>{r['name']}</b> &nbsp;|&nbsp; {desc_span} &nbsp;|&nbsp; {price_span}
                        </div>
                        """
                        col_txt, col_btn = st.columns([0.9, 0.1])
                        with col_txt:
                            st.markdown(row_html, unsafe_allow_html=True)
                        with col_btn:
                            if st.session_state.bartender_mode:
                                with st.popover("⋮"):
                                    if st.button("Edit", key=f"ed_w_{r['id']}"): edit_recipe_dialog(r)
                                    if st.button("Del", key=f"dl_w_{r['id']}"): 
                                        delete_recipe(r['id'])
                                        st.rerun()
            
            # Display Others
            if others:
                st.subheader("Other Wines")
                for r in others:
                     # Same HTML block logic... (Refactor potential but inline is fine for now)
                    price_span = f"<b>{r['price']}</b>" if r.get('price') else ""
                    desc_span = f"<i>{r['description']}</i>" if r.get('description') else ""
                    row_html = f"""<div style="line-height:1.4; margin-bottom: 4px;"><b>{r['name']}</b> | {desc_span} | {price_span}</div>"""
                    col_txt, col_btn = st.columns([0.9, 0.1])
                    with col_txt: st.markdown(row_html, unsafe_allow_html=True)
                    with col_btn:
                        if st.session_state.bartender_mode:
                            with st.popover("⋮"):
                                if st.button("Edit", key=f"ed_wo_{r['id']}"): edit_recipe_dialog(r)
                                if st.button("Del", key=f"dl_wo_{r['id']}"): 
                                    delete_recipe(r['id']); st.rerun()

        # LIQUORS (Grouped)
        elif cat == 'Liquors':
            # Sub-Groups
            wells = []
            others = []
            
            for r in recipes:
                s = r.get('spirit', '').lower()
                if 'house' in s:
                    wells.append(r)
                else:
                    others.append(r)
            
            # 1. Premium Wells
            if wells:
                st.subheader("Premium Wells")
                for r in wells:
                    price_span = f"<b>{r['price']}</b>" if r.get('price') else ""
                    desc_span = f"<i>{r['description']}</i>" if r.get('description') else ""
                    row_html = f"""<div style="line-height:1.4; margin-bottom: 4px;"><b>{r['name']}</b> | {desc_span} | {price_span}</div>"""
                    
                    col_txt, col_btn = st.columns([0.9, 0.1])
                    with col_txt: st.markdown(row_html, unsafe_allow_html=True)
                    with col_btn:
                        if st.session_state.bartender_mode:
                            with st.popover("⋮"):
                                if st.button("Edit", key=f"ed_l_{r['id']}"): edit_recipe_dialog(r)
                                if st.button("Del", key=f"dl_l_{r['id']}"): 
                                    delete_recipe(r['id']); st.rerun()

            # 2. Premium Selections (Others)
            if others:
                st.subheader("Premium Selections")
                for r in others:
                    price_span = f"<b>{r['price']}</b>" if r.get('price') else ""
                    desc_span = f"<i>{r['description']}</i>" if r.get('description') else ""
                    row_html = f"""<div style="line-height:1.4; margin-bottom: 4px;"><b>{r['name']}</b> | {desc_span} | {price_span}</div>"""
                    
                    col_txt, col_btn = st.columns([0.9, 0.1])
                    with col_txt: st.markdown(row_html, unsafe_allow_html=True)
                    with col_btn:
                        if st.session_state.bartender_mode:
                            with st.popover("⋮"):
                                if st.button("Edit", key=f"ed_lo_{r['id']}"): edit_recipe_dialog(r)
                                if st.button("Del", key=f"dl_lo_{r['id']}"): 
                                    delete_recipe(r['id']); st.rerun()

        # BEER (Simple List)
        else:
            if cat == 'Beer': st.caption("*Bottle | Draft*")
            
            for r in recipes:
                price_span = f"<b>{r['price']}</b>" if r.get('price') else ""
                desc_span = f"<i>{r['description']}</i>" if r.get('description') else ""
                
                # HTML Block for tight spacing
                row_html = f"""
                <div style="line-height:1.4; margin-bottom: 4px;">
                    <b>{r['name']}</b> &nbsp;|&nbsp; {desc_span} &nbsp;|&nbsp; {price_span}
                </div>
                """
                
                c1, c2 = st.columns([0.9, 0.1])
                with c1:
                    st.markdown(row_html, unsafe_allow_html=True)
                with c2:
                    if st.session_state.bartender_mode:
                         with st.popover("⋮"):
                              if st.button("Edit", key=f"ed_b_{r['id']}"): edit_recipe_dialog(r)
                              if st.button("Del", key=f"dl_b_{r['id']}"): 
                                    delete_recipe(r['id']); st.rerun()



# --- 6. BARTENDER TOOLS (The Import Section) ---
# This section is ONLY for adding NEW things to your database.
if st.session_state.bartender_mode:
    st.header("🛠️ Bartender Tools: Classics Import")
    
    # 1. The Trigger Button
    if st.button("Browse Master Catalog (menu.json)"):
        st.session_state.show_import_menu = not st.session_state.show_import_menu

    # 2. The Selection Menu
    if st.session_state.show_import_menu:
        with st.expander("Select Cocktails to Import", expanded=True):
            st.info("Select recipes from the master list. Units will convert to ounces automatically.")
            
            try:
                with open("menu.json", "r") as f:
                    master_list = json.load(f)
            except FileNotFoundError:
                st.error("Could not find 'menu.json'. Make sure the file exists.")
                master_list = []

            with st.form(key='import_form'):
                selected_recipes = []
                
                for i, recipe in enumerate(master_list):
                    col1, col2 = st.columns([0.1, 0.9])
                    
                    with col1:
                        checked = st.checkbox("", key=f"import_check_{i}")
                    
                    with col2:
                        st.markdown(f"**{recipe.get('name')}**")
                        if 'specs' in recipe:
                            preview = [convert_ml_to_oz(s) for s in recipe['specs']]
                            st.caption(f"{', '.join(preview[:2])}...")

                    if checked:
                        selected_recipes.append(recipe)

                st.markdown("---")
                
                if st.form_submit_button("Import Selected Recipes"):
                    if not selected_recipes:
                        st.warning("No recipes selected.")
                    else:
                        success_count = 0
                        for item in selected_recipes:
                            to_save = item.copy()
                            if 'specs' in to_save:
                                to_save['specs'] = [convert_ml_to_oz(s) for s in to_save['specs']]
                            
                            # Default new imports to Classics if no category logic applied here yet
                            # (Actually db migration logic isn't here, so we should allow db_utils to handle defaults 
                            # or just set a default here. Let's set 'Classics' to be safe)
                            to_save['category'] = to_save.get('category', 'Classics')
                            if 'is_cotw' in item and item['is_cotw']: to_save['category'] = 'Featured Sips'

                            if save_new_recipe(to_save):
                                success_count += 1
                        
                        st.success(f"Successfully imported {success_count} cocktails!")
                        time.sleep(1)
                        st.session_state.show_import_menu = False
                        st.rerun()