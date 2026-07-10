import json
import streamlit as st

st.set_page_config(page_title="ES Window Insider", layout="wide")

@st.cache_data
def load_and_clean_data():
    """
    Returns a plain list[dict] (no pandas DataFrame, no pyarrow).
    Streamlit's Arrow-based table widgets (and pandas' Arrow-backed string
    dtype) are avoided entirely on purpose -- see note at bottom of file.
    """
    products = []

    for path, key, product_type in [
        ("windows.json", "window", "WINDOW"),
        ("doors.json", "door", "DOOR"),
    ]:
        try:
            with open(path, "r") as f:
                raw = json.load(f)["data"][key]
        except json.JSONDecodeError as je:
            st.error(
                f"**Syntax Error in `{path}`!** Check around line {je.lineno}, "
                f"column {je.colno}. Reason: {je.msg}"
            )
            st.stop()
        except FileNotFoundError:
            st.error(f"Critical Error: '{path}' not found in this folder.")
            st.stop()

        for item in raw:
            ext = item.get("ext_psf_range") or {}
            intp = item.get("int_psf_range") or {}
            width = item.get("width_range") or {}
            height = item.get("height_range") or {}

            products.append(
                {
                    "brand": item.get("brand", "UNKNOWN"),
                    "category": (item.get("category") or "UNKNOWN").upper(),
                    "impact_rating": (item.get("impact_rating") or "UNKNOWN").upper(),
                    "model": item.get("model", ""),
                    "configuration": item.get("configuration", ""),
                    "product_type": product_type,
                    "ext_psf_min": ext.get("min"),
                    "ext_psf_max": ext.get("max"),
                    "int_psf_min": intp.get("min"),
                    "int_psf_max": intp.get("max"),
                    "width_min": width.get("min"),
                    "width_max": width.get("max"),
                    "height_min": height.get("min"),
                    "height_max": height.get("max"),
                }
            )

    return products

### Get raw product data ###
try:
    products_raw = load_and_clean_data()
except Exception as e:
    st.error(f"Initialization failed. Verify 'windows.json' and 'doors.json' exist. Error: {e}")
    st.stop()


### UI ###
#st.header("🪟 ESWindow Products Filtering", divider=True)

st.sidebar.header("🔍 Specifications Selection")

prod_type = st.sidebar.selectbox("Product Type", ["All Types", "WINDOW", "DOOR"])
filtered = products_raw if prod_type == "All Types" else [
    p for p in products_raw if p["product_type"] == prod_type
]

brand_options = sorted({p["brand"] for p in filtered})
brands = st.sidebar.multiselect("Brand", options=brand_options)
if brands:
    filtered = [p for p in filtered if p["brand"] in brands]
    
category_options = sorted({p["category"] for p in filtered})
categories = st.sidebar.multiselect("Sub-Category Filter", options=category_options)
if categories:
    filtered = [p for p in filtered if p["category"] in categories]

impact_options = sorted({p["impact_rating"] for p in filtered})
impact_ratings = st.sidebar.multiselect("Impact Performance Rating", options=impact_options)
if impact_ratings:
    filtered = [p for p in filtered if p["impact_rating"] in impact_ratings]

st.sidebar.write("---")
st.sidebar.subheader("📐 Dimensions")

enable_dimension = st.sidebar.checkbox("Enable dimensions?", value=False)
if enable_dimension:
    user_width = st.sidebar.number_input(
        "Target Width (in)", min_value=0.0000, value=36.0000, step=0.0625
    )
    user_height = st.sidebar.number_input(
        "Target Height (in)", min_value=0.0000, value=80.0000, step=0.0625
    )

    def fits_dimensions(p):
        w_min = p["width_min"] if p["width_min"] is not None else 0.0
        w_max = p["width_max"] if p["width_max"] is not None else float("inf")
        h_min = p["height_min"] if p["height_min"] is not None else 0.0
        h_max = p["height_max"] if p["height_max"] is not None else float("inf")
        return w_min <= user_width <= w_max and h_min <= user_height <= h_max

    filtered = [p for p in filtered if fits_dimensions(p)]

st.sidebar.write("---")
st.sidebar.subheader("💨 Ext. & Int. Wind Pressure")

enable_psf = st.sidebar.checkbox("Enable wind pressure?", value=False)
if enable_psf:
    user_ext_psf = st.sidebar.number_input("Exterior PSF Cap (+)", min_value=0.0, value=60.0, step=1.0)
    user_int_psf = st.sidebar.number_input("Interior PSF Cap (-)", min_value=0.0, value=60.0, step=1.0)

    def fits_pressure(p):
        ext_max = p["ext_psf_max"] if p["ext_psf_max"] is not None else float("inf")
        int_max = p["int_psf_max"] if p["int_psf_max"] is not None else float("inf")
        return ext_max >= user_ext_psf and int_max >= user_int_psf

    filtered = [p for p in filtered if fits_pressure(p)]

st.subheader(f"📊 ESWindow Qualified Matches ({len(filtered)} Items)")

DISPLAY_COLS = [
    ("brand", "Brand"),
    ("category", "Category"),
    ("model", "Model"),
    ("configuration", "Configuration"),
    ("impact_rating", "Impact Rating"),
    ("width_min", "Width Min (in)"),
    ("width_max", "Width Max (in)"),
    ("height_min", "Height Min (in)"),
    ("height_max", "Height Max (in)"),
    ("ext_psf_max", "Exterior PSF"),
    ("int_psf_max", "Interior PSF"),
]


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


if filtered:
    table = st.container()
    rows = sorted(filtered, key=lambda p: (p["brand"], p["model"]))

    # Render as a plain HTML table -- deliberately NOT st.dataframe()/st.table(),
    # both of which serialize the data through pyarrow. See note at bottom.
    header_html = "".join(f"<th>{label}</th>" for _, label in DISPLAY_COLS)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{fmt(row[key])}</td>" for key, _ in DISPLAY_COLS) + "</tr>"
        for row in rows
    )
    table_html = f"""
    <div style="max-height: 75vh; overflow:auto; border:1px solid #eee; border-radius:2px;">
    <table style="width:100%; border-collapse:collapse; font-size:14px;">
      <thead style="position:sticky; top:0; background:#eee">
        <tr>{header_html}</tr>
      </thead>
      <tbody>{body_html}</tbody>
    </table>
    </div>
    <style>
      td, th {{ padding:6px 10px; text-align:left; border-bottom:1px solid #333; }}
    </style>
    """
    table.markdown(table_html, unsafe_allow_html=True)

else:
    st.warning(
        "No items in the database explicitly fulfill your current sizing or pressure thresholds. Try backing out strict constraints."
    )
