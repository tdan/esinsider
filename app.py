import json
import re
import pandas as pd
import streamlit as st

# Set page layout to wide for comfortable data scanning
st.set_page_config(page_title="ES Window Insider", layout="wide")

# String cleaner to bypass human syntax typos in raw JSON files dynamically
def auto_heal_and_load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Clear trailing syntax commas before a closing brace } or bracket ]
    content = re.sub(r",\s*([\]}])", r"\1", content)

    # Intercept missing item commas between successive rows
    content = re.sub(r'([\d"\]}])\s*\n\s*"', r"\1,\n\"", content)

    return json.loads(content)

@st.cache_data
def load_and_clean_data():
    all_products = []

    # 1. Digest Windows Inventory
    try:
        windows_payload = auto_heal_and_load_json("windows.json")
        for item in windows_payload["data"]["window"]:
            item["product_type"] = "WINDOW"
            all_products.append(item)
    except FileNotFoundError:
        st.error("❌ Critical Error: 'windows.json' not found in this folder.")
        st.stop()

    # 2. Digest Doors Inventory
    try:
        doors_payload = auto_heal_and_load_json("doors.json")
        for item in doors_payload["data"]["door"]:
            item["product_type"] = "DOOR"
            all_products.append(item)
    except FileNotFoundError:
        st.error("❌ Critical Error: 'doors.json' not found in this folder.")
        st.stop()

    df = pd.DataFrame(all_products)

    # Deep extraction helper that cleanly handles missing keys or None types
    def extract_val(row_dict, key):
        if isinstance(row_dict, dict) and row_dict:
            return row_dict.get(key)
        return None

    # Map the nested JSON layers into root-level columns
    df["ext_psf_min"] = df["ext_psf_range"].apply(lambda x: extract_val(x, "min"))
    df["ext_psf_max"] = df["ext_psf_range"].apply(lambda x: extract_val(x, "max"))
    df["int_psf_min"] = df["int_psf_range"].apply(lambda x: extract_val(x, "min"))
    df["int_psf_max"] = df["int_psf_range"].apply(lambda x: extract_val(x, "max"))
    df["width_min"] = df["width_range"].apply(lambda x: extract_val(x, "min"))
    df["width_max"] = df["width_range"].apply(lambda x: extract_val(x, "max"))
    df["height_min"] = df["height_range"].apply(lambda x: extract_val(x, "min"))
    df["height_max"] = df["height_range"].apply(lambda x: extract_val(x, "max"))

    # Force all numeric columns to float, turning empty dicts/nulls into NaN
    num_cols = [
        "ext_psf_min",
        "ext_psf_max",
        "int_psf_min",
        "int_psf_max",
        "width_min",
        "width_max",
        "height_min",
        "height_max",
    ]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Standardize textual categories
    df["category"] = df["category"].str.upper().fillna("UNKNOWN")
    df["impact_rating"] = df["impact_rating"].str.upper().fillna("UNKNOWN")

    return df


# Initialize app data
try:
    df_raw = load_and_clean_data()
except Exception as e:
    st.error(
        f"Initialization failed. Verify 'windows.json' and 'doors.json' exist. Error: {e}"
    )
    st.stop()

# --- Structural Layout & Header ---
st.title("🪟 ESWindow Products Filtering")
st.markdown(
    "Filter across combined inventory using exact physical dimensions, categories, and pressure thresholds."
)
st.write("---")

# --- Sidebar Form Filters ---
st.sidebar.header("🔍 Specifications Selection")

# Basic Category Grouping
prod_type = st.sidebar.selectbox("Product Type", ["All Types", "WINDOW", "DOOR"])
filtered_df = df_raw.copy()
if prod_type != "All Types":
    filtered_df = filtered_df[filtered_df["product_type"] == prod_type]

categories = st.sidebar.multiselect(
    "Sub-Category Filter", options=sorted(filtered_df["category"].unique())
)
if categories:
    filtered_df = filtered_df[filtered_df["category"].isin(categories)]

impact_ratings = st.sidebar.multiselect(
    "Impact Performance Rating",
    options=sorted(filtered_df["impact_rating"].unique()),
)
if impact_ratings:
    filtered_df = filtered_df[filtered_df["impact_rating"].isin(impact_ratings)]

st.sidebar.write("---")
st.sidebar.subheader("📐 Dimensions")

enable_dimension = st.sidebar.checkbox("Enable dimensions?", value=False)

if enable_dimension:
    user_width = st.sidebar.number_input(
        "Target Width (in)", min_value=0.0, value=36.0, step=0.125
    )
    user_height = st.sidebar.number_input(
        "Target Height (in)", min_value=0.0, value=80.0, step=0.125
    )

    # Use fillna strategically so incomplete data doesn't trigger false positives
    filtered_df = filtered_df[
        (filtered_df["width_min"] <= user_width | filtered_df["width_min"].isna())
        & (user_width <= filtered_df["width_max"] | filtered_df["width_min"].isna())
        & (filtered_df["height_min"] <= user_height | filtered_df["height_min"].isna())
        & (user_height <= filtered_df["height_max"] | filtered_df["height_max"].isna())
    ]

st.sidebar.write("---")
st.sidebar.subheader("💨 Ext. & Int. Wind Pressure")

enable_psf = st.sidebar.checkbox("Enable wind pressure?", value=False)
if enable_psf:
    user_ext_psf = st.sidebar.number_input(
        "Exterior PSF Cap (+)", min_value=0.0, value=60.0, step=5.0
    )
    user_int_psf = st.sidebar.number_input(
        "Interior PSF Cap (-)", min_value=0.0, value=60.0, step=5.0
    )

    # Ensure capability limit is equal to or greater than requirements
    filtered_df = filtered_df[
        (filtered_df["ext_psf_max"] >= user_ext_psf | filtered_df["ext_psf_max"].isna())
        & (filtered_df["int_psf_max"] >= user_int_psf | filtered_df["int_psf_max"].isna())
    ]

# --- Main Window Output Display ---
st.subheader(f"📊 Qualified Matches ({len(filtered_df)} Items)")

if not filtered_df.empty:
    display_cols = [
        "brand",
        "category",
        "model",
        "configuration",
        "impact_rating",
        "width_min",
        "width_max",
        "height_min",
        "height_max",
        "ext_psf_max",
        "int_psf_max",
    ]

    # Present spreadsheet-like table with sorting mechanics
    st.dataframe(
        filtered_df[display_cols].sort_values(by=["brand", "model"]),
        width="stretch",
        hide_index=True,
    )
else:
    st.warning(
        "No items in the database explicitly fulfill your current sizing or pressure thresholds. Try backing out strict constraints."
    )
