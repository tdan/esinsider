import json
import pandas as pd
import streamlit as st

# Set page layout to wide for comfortable data scanning
st.set_page_config(layout="wide")


@st.cache_data
def load_and_clean_data():
    all_products = []

    # 1. Load Windows file verbatim
    with open("window_formatted.json", "r") as f:
        windows_data = json.load(f)["data"]["window"]
        for item in windows_data:
            item["product_type"] = "WINDOW"
            all_products.append(item)

    # 2. Load Doors file verbatim
    with open("get_specs_door.json", "r") as f:
        doors_data = json.load(f)["data"]["door"]
        for item in doors_data:
            item["product_type"] = "DOOR"
            all_products.append(item)

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
        f"Initialization failed. Verify 'window_formatted.json' and 'get_specs_door.json' exist. Error: {e}"
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
        (filtered_df["width_min"].fillna(float("inf")) <= user_width)
        & (user_width <= filtered_df["width_max"].fillna(-1.0))
        & (filtered_df["height_min"].fillna(float("inf")) <= user_height)
        & (user_height <= filtered_df["height_max"].fillna(-1.0))
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
        (filtered_df["ext_psf_max"].fillna(-1.0) >= user_ext_psf)
        & (filtered_df["int_psf_max"].fillna(-1.0) >= user_int_psf)
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
