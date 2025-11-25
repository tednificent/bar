import streamlit as st
import json
import time
import os
import re 

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

def load_menu():
    """Loads the cocktail menu from menu.json. Creates file with seed data if missing."""
    
    # 1. Define Seed Data (The two Chop House Fixed recipes)
    seed_data = [
        {"name": "Grand Margarita (Chop House Fixed)", "spirit": "Tequila", "description": "Our premium margarita. No herbs, just clean agave.", "ingredients": ["Reposado Tequila", "Grand Marnier", "Lime"], "spec_recipe": ["2oz Reposado Tequila", "0.5oz Grand Marnier", "1oz Fresh Lime Juice"], "glassware": "Rocks", "garnish": "Salt Rim & Lime Wheel", "instructions": "Shake with ice, strain over fresh ice. NO BASIL.", "image_path": "", "is_classic": False},
        {"name": "Southern Belle (Fresh)", "spirit": "Vodka", "description": "A refreshing raspberry vodka cooler.", "ingredients": ["Vodka", "Fresh Raspberries", "Lime"], "spec_recipe": ["2oz Vodka", "0.75oz Lime Juice", "Muddled FRESH Raspberries"], "glassware": "Coupe", "garnish": "3 Fresh Raspberries on pick", "instructions": "Muddle berries in tin. Shake hard double strain.", "image_path": "", "is_classic": False}
    ]
    
    if os.path.exists("menu.json"):
        with open("menu.json", "r") as f:
            try:
                content = f.read()
                if not content: return []
                return json.loads(content)
            except json.JSONDecodeError:
                st.error("Error loading menu.json. File is corrupted.")
                return []
    else:
        # 2. FILE DOES NOT EXIST: Create it with seed data
        with open("menu.json", "w") as f:
            json.dump(seed_data, f, indent=4)
        
        return seed_data

# Note: Keep your save_menu() function as is!
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
    
    # --- 1. STATE INITIALIZATION ---
    if 'add_mode' not in st.session_state:
        st.session_state['add_mode'] = False
        
    # --- 2. SIDEBAR CONFIGURATION ---
    st.sidebar.header("Configuration")
    bartender_mode = st.sidebar.toggle("Bartender Mode (Show Specs)", value=False)
    
    # ADMIN BUTTON (Only visible if Bartender Mode is ON)
    if bartender_mode:
        if st.sidebar.button("➕ Add New Spec"):
            st.session_state.add_mode = True 
        st.sidebar.caption("---")
    
    # Load Menu
    menu = load_menu()
    
    # Inventory Filter
    all_spirits = sorted(list(set([d.get("spirit", "Other") for d in menu])))
    inventory_filter = st.sidebar.multiselect("Inventory Filter", all_spirits)

    # --- 3. MAIN PAGE LOGIC ---

    if st.session_state.add_mode:
        # --- VIEW A: ADMIN FORM ---
        st.title("➕ Enter New Cocktail Specification")
        if st.button("← Back to Menu"):
            st.session_state.add_mode = False
            st.rerun()

        with st.form("new_drink_form", clear_on_submit=True):
            name = st.text_input("Cocktail Name")
            spirit = st.selectbox("Base Spirit", ["Gin", "Vodka", "Rum", "Tequila", "Whiskey", "Brandy", "Other"])
            description = st.text_area("Description (Guest Facing)")
            st.markdown("---")
            st.caption("Upload Final Presentation Photo")
            uploaded_file = st.file_uploader("Choose a photo (.png, .jpg)", type=["png", "jpg", "jpeg"])
            spec_recipe_raw = st.text_area("Full Recipe Specs (1 line per ingredient)", help="e.g. 2oz Vodka, 0.75oz Lime...")
            instructions = st.text_area("Instructions (Preparation Steps)")
            glassware = st.text_input("Glassware")
            garnish = st.text_input("Garnish")

            submitted = st.form_submit_button("Add Drink & Photo")

            if submitted:
                if name and spec_recipe_raw:
                    image_path = ""
                    if uploaded_file is not None:
                        # Create images folder if missing
                        if not os.path.exists("images"):
                            os.makedirs("images")
                        file_name = f"images/{name.replace(' ', '_').lower()}_{int(time.time())}.jpg"
                        with open(file_name, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        image_path = file_name
                    
                    new_entry = {
                        "name": name, "spirit": spirit, "description": description, 
                        "ingredients": [i.strip() for i in spec_recipe_raw.split('\n') if i.strip()], 
                        "spec_recipe": [convert_ml_to_oz(i.strip()) for i in spec_recipe_raw.split('\n') if i.strip()], 
                        "glassware": glassware, "garnish": garnish, "instructions": instructions, 
                        "image_path": image_path, "is_classic": False
                    }
                    menu.append(new_entry)
                    save_menu(menu)
                    st.success(f"Successfully added {name}!")
                    time.sleep(1)
                    st.session_state.add_mode = False
                    st.rerun() 
                else:
                    st.error("Please enter a name and recipe.")
    
    else: 
        # --- VIEW B: SPEC MENU ---
        st.title("📜 Digital Bar Manager")
        tab_menu, tab_import = st.tabs(["📜 Spec Menu", "🌍 Import Classics"])

        with tab_menu:
            # Filtering Logic
            display_menu = menu
            if inventory_filter:
                display_menu = [d for d in menu if d.get("spirit") in inventory_filter]

            if not display_menu:
                st.info("No drinks found matching your filter.")

            # --- DISPLAY LOOP ---
            for i, drink in enumerate(display_menu):
                with st.expander(f"**{drink['name']}** ({drink['spirit']})"):
                    col_img, col_desc = st.columns([1, 2])
                    
                    with col_img:
                        if drink.get('image_path') and os.path.exists(drink['image_path']):
                            st.image(drink['image_path'], use_column_width=True)
                        else:
                            st.markdown("📷 *No Photo*")

                    with col_desc:
                        st.write(f"_{drink.get('description', '')}_")
                        
                        # Guest View (Always show ingredients)
                        if not bartender_mode:
                            st.caption("Ingredients:")
                            st.write(", ".join(drink.get('ingredients', [])))

                        # Bartender View (Show Specs)
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
        
        with tab_import:
            st.header("Import from IBA Cocktails")
            st.info("Import feature currently disabled. Please use 'Add New Spec'.")

if __name__ == "__main__":
    main()