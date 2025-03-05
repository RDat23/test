import streamlit as st
import pydeck as pdk
import pandas as pd
import h3

# Data laden met caching
@st.cache_data
def load_data():
    file_path = "data_KJ.csv"
    df = pd.read_csv(file_path)
    return df

df = load_data()

# Alleen relevante kolommen inladen
df = df[["kJ_per_m2", "oppervlakte", "woonplaats", "Energieklasse", "huisnummer", "huisletter", "postcode", "openbare_ruimte", "latitude", "longitude"]]

# Dynamische H3-resolutie bepalen op basis van zoomniveau
def get_dynamic_resolution(zoom_level):
    if zoom_level <= 5:
        return 6  # Grotere hexagonen op lagere zoomniveaus
    elif zoom_level <= 10:
        return 8  # Middelgrote hexagonen op gemiddelde zoomniveaus
    else:
        return 12  # Kleinere hexagonen voor gedetailleerde weergave
    
# Kleurmapping
colorbrewer_colors = [
    [215, 48, 39, 255], # Rood (Geen potentie)
    [252, 141, 89, 255], # Oranje (Lage potentie)
    [254, 224, 129, 255], # Geel (Matige potentie)
    [255, 255, 191, 255], # Lichtgeel (Redelijke potentie)
    [217, 239, 139, 255], # Lichtgroen (Goede potentie)
    [145, 207, 96, 255], # Groen (Hoge potentie)
    [26, 152, 80, 255] # Donkergroen (Zeer hoge potentie)
]

def get_color(kJ_value):
    bins = [50_000, 150_000, 300_000, 500_000, 1_000_000, 3_000_000]
    for i, threshold in enumerate(bins):
        if kJ_value < threshold:
            return colorbrewer_colors[i]
    return colorbrewer_colors[-1]  # For values >= 5,000,000

df["color"] = df["kJ_per_m2"].apply(get_color)

# Streamlit UI
st.title("H3 Warmtekaart")

# Sidebar opties
st.sidebar.header("Opties")

# Uitleg over H3-schalen
with st.sidebar.expander("ℹ Uitleg over H3-schalen"):
    st.write(
        "H3 is een hexagonaal raster dat gebieden verdeelt in zeshoeken van verschillende resoluties. "
        "Elke hexagoon krijgt een unieke ID en bevat gegevens over de warmtebehoefte."
    )

# Kies een kaartstijl
map_style = st.sidebar.selectbox(
    "Kies een kaartstijl:",
    options=["light", "dark", "streets", "outdoors", "satellite", "satellite-streets"],
    format_func=lambda x: x.capitalize()
)

map_style_url = f"mapbox://styles/mapbox/{map_style}-v9"

# Zoom slider
zoom_level = st.sidebar.slider("Selecteer zoomniveau", 1, 15, 7)
resolution = get_dynamic_resolution(zoom_level)

with st.sidebar.expander("ℹ Uitleg over zoomniveau"):
    st.write(
        "Het zoomniveau bepaalt de mate van detail op de kaart:\n"
        "- **1-3 (~1500 km - 5000 km)**: Wereld- en landniveau, waarbij hele continenten of landen zichtbaar zijn. Om de prestaties te optimaliseren, wordt 5% van de gegevens weergegeven.\n"
        "- **4-7 (~70 km - 700 km)**: Grote steden en regio’s komen in beeld. In deze weergave wordt 20% van de gegevens geladen.\n"
        "- **8-11 (~4 km - 35 km)**: Specifieke buurten en industriegebieden zijn herkenbaar. Vanaf dit niveau kan de volledige dataset worden gefilterd op woonplaats.\n"
        "- **12-15 (~200 m - 2 km)**: Straatniveau, waarbij ook de volledige dataset beschikbaar is gefilterd op woonplaats. Individuele panden en straten zijn gedetailleerd zichtbaar.\n\n"
        "Bij lagere zoomniveaus (1 tot 7) wordt slechts een deel van de data weergegeven om de prestaties te verbeteren.\n\n"
        "Deze zoomniveaus zijn gebaseerd op de documentatie van [Mapbox](https://docs.mapbox.com/help/glossary/zoom-level/)."
    )

# Woonplaatsen
# Unieke woonplaatsen ophalen
woonplaatsen = df["woonplaats"].dropna().unique()

# Bij zoomniveau 1-7: automatisch alle woonplaatsen in Friesland selecteren
if 1 <= zoom_level <= 7:
    friesland_woonplaatsen = df["woonplaats"].unique()  # Alle woonplaatsen in Friesland
    df = df[df["woonplaats"].isin(friesland_woonplaatsen)]
else:
    # Alleen de woonplaatsfilter tonen bij zoomniveau >= 8
    woonplaats_selectie = st.sidebar.multiselect(
        "Filter op woonplaats:",
        options=sorted(woonplaatsen),
        default=["Leeuwarden"]
    )

    # Zorg ervoor dat er altijd minimaal één woonplaats is geselecteerd
    if not woonplaats_selectie:
        st.warning("Selecteer minimaal één woonplaats.")
        # Terugvallen op standaardwaarde
        woonplaats_selectie = ["Leeuwarden"] 

    df = df[df["woonplaats"].isin(woonplaats_selectie)]

# Scenario selectie
multiplier = st.sidebar.selectbox(
    "Selecteer een scenario:",
    options=["Scenario 1", "Scenario 2", "Scenario 3", "Scenario 4"],
    index=0
)

scenario_mapping = {"Scenario 1": 1, "Scenario 2": 2, "Scenario 3": 3, "Scenario 4": 4}
multiplier = scenario_mapping[multiplier]

# Uitleg over scenario's
with st.sidebar.expander("ℹ Uitleg over scenario’s"):
    st.write(
        "De scenario’s bepalen hoe sterk de 3D-weergave de warmtebehoefte vergroot:\n\n"
        "- **Scenario 1:** Standaard hoogte, direct gebaseerd op warmtebehoefte.\n"
        "- **Scenario 2:** Verdubbelt de hoogte voor beter zichtbare patronen.\n"
        "- **Scenario 3:** Extra versterkt om energiehotspots uit te lichten.\n"
        "- **Scenario 4:** Maximale versterking voor de grootste contrasten.\n\n"
        "Hogere scenario’s helpen om verschillen beter te analyseren!"
    )


# 2D/3D-weergave
extruded = st.sidebar.toggle("3D Weergave", value=False)

# Uitleg over 3D-weergave
with st.sidebar.expander("ℹ Uitleg over 3D-weergave"):
    st.write(
        "Wanneer 3D-weergave is ingeschakeld, wordt de hoogte van de hexagonen aangepast op basis van het warmtegebruik.\n"
        "Dit helpt bij het visualiseren van gebieden met hogere of lagere energiebehoefte."
    )

# Knop om de kaart te weergeven
if "show_map" not in st.session_state:
    st.session_state.show_map = False

map_container = st.empty()

if st.sidebar.button("Maak Kaart"):
    st.session_state.show_map = True  

if st.session_state.show_map:
    # Data filtering per zoomniveau
    if zoom_level <= 3:
        df_filtered = df.sample(frac=0.05)
    elif zoom_level <= 7:
        df_filtered = df.sample(frac=0.20)
    elif zoom_level <= 11:
        df_filtered = df
    else:
        df_filtered = df

    # H3 Index berekenen na filtering
    df_filtered["h3_index"] = df_filtered.apply(lambda row: h3.latlng_to_cell(row["latitude"], row["longitude"], resolution), axis=1)

    # Schaalvergroting aanpassen (scenario)
    MAX_HEIGHT = 3000  # Adjust between 2500 - 5000 for best effect

    # Normalize elevation between 0 and MAX_HEIGHT
    df_filtered["scaled_elevation"] = (df_filtered["kJ_per_m2"] - 50_000) / (3_000_000 - 50_000) * MAX_HEIGHT

    # Ensure it doesn't go over MAX_HEIGHT
    df_filtered["scaled_elevation"] = df_filtered["scaled_elevation"].clip(upper=MAX_HEIGHT)

    # Gebruik alleen de nodige kolommen
    df_filtered = df_filtered[["h3_index", 
                               "kJ_per_m2", 
                               "color", 
                               "woonplaats", 
                               "huisnummer", 
                               "scaled_elevation", 
                               "oppervlakte", 
                               "postcode", 
                               "Energieklasse", 
                               "openbare_ruimte", 
                               "huisletter"]]

    # Functie om de H3 laag aan te maken
    def create_layer(visible, elevation_scale):
        return pdk.Layer(
            "H3HexagonLayer",
            df_filtered,
            pickable=True,
            filled=True,
            extruded=extruded,
            coverage=1,
            get_hexagon="h3_index",
            get_fill_color="color",
            get_elevation="scaled_elevation",
            elevation_scale=elevation_scale if extruded else 0,
            elevation_range=[0, 7000.0],
            visible=visible,
        )

    layers = [
        create_layer(zoom_level <= 3, 0.01),
        create_layer(4 <= zoom_level <= 7, 0.05),
        create_layer(8 <= zoom_level <= 11, 0.08),
        create_layer(zoom_level >= 12, 0.10),
    ]

    # ViewState correct bijwerken
    st.session_state.view_state = pdk.ViewState(
        longitude=df["longitude"].mean(),
        latitude=df["latitude"].mean(),
        zoom=zoom_level,  
        min_zoom=1,  
        max_zoom=15,  
        pitch=40.5,
        bearing=0,
    )

    tooltip = {
        "html": """
            <b>Postcode:</b> {postcode}<br>
            <b>Woonplaats:</b> {woonplaats}<br>
            <b>Straatnaam:</b> {openbare_ruimte}<br>
            <b>Huisnummer:</b> {huisnummer}<br>
            <b>Huisletter:</b> {huisletter}<br>
            <b>Energiegebruik:</b> {kJ_per_m2} kJ/m²<br>
            <b>Oppervlakte:</b> {oppervlakte} m²<br>
            <b>Energieklasse:</b> {Energieklasse} <br>
        """,
        "style": {
            "backgroundColor": "white",
            "color": "black",
            "font-family": "Arial",
            "padding": "5px",
            "border-radius": "5px"
        }
    }

    map_container.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=st.session_state.view_state,
            map_style=map_style_url,
            tooltip=tooltip 
        )
    )

    # **Legenda**
    legend_html = """
        <style>
            .legend {
                position: absolute;
                bottom: 5px;
                left: 5px;
                width: 220px;
                background: white;
                padding: 10px;
                border-radius: 5px;
                font-family: Arial, sans-serif;
                font-size: 12px;
                color: black;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
            }
            .legend-title {
                font-weight: bold;
                margin-bottom: 5px;
            }
            .color-box {
                width: 15px;
                height: 15px;
                display: inline-block;
                margin-right: 5px;
            }
        </style>
        <div class="legend">
            <div class="legend-title">Warmtepotentieel (kJ/m²)</div>
            <div><span class="color-box" style="background-color: #d73027;"></span> &lt; 50,000</div>
            <div><span class="color-box" style="background-color: #fc8d59;"></span> 50,000 - 150,000</div>
            <div><span class="color-box" style="background-color: #fee08b;"></span> 150,000 - 300,000</div>
            <div><span class="color-box" style="background-color: #ffffbf;"></span> 300,000 - 500,000</div>
            <div><span class="color-box" style="background-color: #d9ef8b;"></span> 500,000 - 1,000,000</div>
            <div><span class="color-box" style="background-color: #91cf60;"></span> 1,000,000 - 3,000,000</div>
            <div><span class="color-box" style="background-color: #1a9850;"></span> &gt; 3,000,000</div>
        </div>
    """
    st.markdown(legend_html, unsafe_allow_html=True)
