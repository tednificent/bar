import streamlit as st
import json
import time
from PIL import Image

# --- CUSTOM DATABASE UTILS ---
# This file handles all the talking to your new SQLite database
from db_utils import get_all_recipes, save_new_recipe, convert_ml_to_oz

# --- 1. APP CONFIGURATION ---
st.set_page_config(page_title="My Digital Bar", layout="wide")

# --- 2. SESSION STATE SETUP ---
if 'bartender_mode' not in st.session_state:
    st.session_state.bartender_mode = False
if 'show_import_menu' not in st.session_state:
    st.session_state.show_import_menu = False

# --- 3. SIDEBAR (SETTINGS) ---
with st.sidebar:
    st.title("Settings")
    # The Toggle Switch for Bartender Mode
    st.session_state.bartender_mode = st.toggle("Bartender Mode", value=st.session_state.bartender_mode)
    
    if st.session_state.bartender_mode:
        st.info("🔧 Edit & Import tools are ACTIVE")

# --- 4. MAIN APP LOGIC (Your Menu) ---
st.title("🍸 The Home Bar")

# [CRITICAL]: We load the ACTIVE menu from SQLite (bar.db), NOT json.
active_recipes = get_all_recipes()

# Display Your Bar
if not active_recipes:
    st.info("Your bar is empty! Switch to Bartender Mode to import recipes.")
else:
    st.write(f"**Current Menu ({len(active_recipes)} Drinks)**")
    
    # Simple Grid Display
    cols = st.columns(3) 
    for i, recipe in enumerate(active_recipes):
        with cols[i % 3]:
            with st.container(border=True):
                st.subheader(recipe['name'])
                
                # Show Specs (Ingredients)
                if recipe.get('specs'):
                    for line in recipe['specs']:
                        st.text(f"• {line}")
                
                # Show Instructions (collapsible)
                with st.expander("Instructions"):
                    st.write(recipe.get('instructions', "No instructions provided."))

st.markdown("---")

# --- 5. BARTENDER TOOLS (The Import Section) ---
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
            
            # [CRITICAL]: We read menu.json HERE just to show you the "Catalog" of options.
            try:
                with open("menu.json", "r") as f:
                    master_list = json.load(f)
            except FileNotFoundError:
                st.error("Could not find 'menu.json'. Make sure the file exists.")
                master_list = []

            # The Form where you pick items
            with st.form(key='import_form'):
                selected_recipes = []
                
                for i, recipe in enumerate(master_list):
                    col1, col2 = st.columns([0.1, 0.9])
                    
                    with col1:
                        # Checkbox for this item
                        checked = st.checkbox("", key=f"import_check_{i}")
                    
                    with col2:
                        st.markdown(f"**{recipe.get('name')}**")
                        # Preview the conversion (cl -> oz)
                        if 'specs' in recipe:
                            preview = [convert_ml_to_oz(s) for s in recipe['specs']]
                            st.caption(f"{', '.join(preview[:2])}...")

                    if checked:
                        selected_recipes.append(recipe)

                st.markdown("---")
                
                # The Save Button
                if st.form_submit_button("Import Selected Recipes"):
                    if not selected_recipes:
                        st.warning("No recipes selected.")
                    else:
                        success_count = 0
                        for item in selected_recipes:
                            # 1. Copy the item
                            to_save = item.copy()
                            
                            # 2. Convert Units PERMANENTLY before saving
                            if 'specs' in to_save:
                                to_save['specs'] = [convert_ml_to_oz(s) for s in to_save['specs']]
                            
                            # 3. Save to SQLite (bar.db)
                            if save_new_recipe(to_save):
                                success_count += 1
                        
                        st.success(f"Successfully imported {success_count} cocktails!")
                        time.sleep(1)
                        st.session_state.show_import_menu = False
                        st.rerun()