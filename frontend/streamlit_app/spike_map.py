"""Streamlit map spike (0.5.4) testing H3 hexagon rendering and clicks."""

from typing import Any

import folium
import h3
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium  # type: ignore[import-untyped]


def get_dummy_data() -> pd.DataFrame:
    """Generate dummy data for Pune city center."""
    # Pune center roughly 18.5204, 73.8567
    center_h3 = h3.latlng_to_cell(18.5204, 73.8567, 9)
    # Get a disk of k=2 around the center
    hexagons = list(h3.grid_disk(center_h3, 2))

    # Assign a dummy score based on distance from center (index in list)
    data = []
    for i, h in enumerate(hexagons):
        data.append(
            {"h3_index": h, "score": max(0, 100 - i * 5), "zone_name": f"Dummy Zone {i + 1}"}
        )
    return pd.DataFrame(data)


def h3_to_geojson(df: pd.DataFrame) -> dict[str, Any]:
    """Convert H3 dataframe to GeoJSON feature collection."""
    features = []
    for _, row in df.iterrows():
        # h3.cell_to_boundary returns ((lat, lon), ...)
        boundary = h3.cell_to_boundary(row["h3_index"])
        # GeoJSON needs lon, lat and the polygon needs to be closed
        coords = [[lon, lat] for lat, lon in boundary]
        coords.append(coords[0])

        feature = {
            "type": "Feature",
            "id": row["h3_index"],
            "geometry": {"type": "Polygon", "coordinates": [coords]},
            "properties": {
                "h3_index": row["h3_index"],
                "score": row["score"],
                "zone_name": row["zone_name"],
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    st.set_page_config(page_title="SiteScout Map Spike", layout="wide")
    st.title("SiteScout H3 Map Spike")

    df = get_dummy_data()
    geojson_data = h3_to_geojson(df)

    # Pune center
    m = folium.Map(location=[18.5204, 73.8567], zoom_start=13, tiles="CartoDB positron")

    # Add choropleth using GeoJson
    folium.GeoJson(
        geojson_data,
        style_function=lambda feature: {
            "fillColor": "green"
            if feature["properties"]["score"] > 80
            else "orange"
            if feature["properties"]["score"] > 50
            else "red",
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.5,
        },
        highlight_function=lambda feature: {
            "weight": 3,
            "fillOpacity": 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["zone_name", "score"],
            aliases=["Zone:", "Score:"],
            style=(
                "background-color: white; color: #333333; "
                "font-family: arial; font-size: 12px; padding: 10px;"
            ),
        ),
    ).add_to(m)

    col1, col2 = st.columns([2, 1])

    with col1:
        st_data = st_folium(m, width="100%", height=600, returned_objects=["last_active_drawing"])

    with col2:
        st.subheader("Interaction Details")
        if st_data and st_data.get("last_active_drawing"):
            props = st_data["last_active_drawing"]["properties"]
            st.write(f"**Clicked Zone:** {props['zone_name']}")
            st.write(f"**Score:** {props['score']}")
            st.write(f"**H3 Index:** {props['h3_index']}")
        else:
            st.info("Click on a hexagon to see details.")


if __name__ == "__main__":
    main()
