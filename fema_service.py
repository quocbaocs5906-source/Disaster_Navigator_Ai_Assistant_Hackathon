import math
import requests
import streamlit as st

def get_disaster_declarations(state_code: str) -> str:
    """
    Retrieves the 5 most recent disaster declarations for a given US state from the OpenFEMA API.
    """
    url = f"https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?$filter=state eq '{state_code.upper()}'&$top=5&$orderby=declarationDate desc"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            try:
                json_data = response.json()
            except Exception:
                return "System Alert: FEMA API is currently returning malformed data. Please try again later."

            data = json_data.get("DisasterDeclarationsSummaries", [])
            if not data:
                return "No recent disaster data found for this state."

            summary_list = []
            for item in data:
                disaster_num = item.get("disasterNumber")
                title = item.get("declarationTitle")
                area = item.get("designatedArea")
                date = item.get("declarationDate", "")[:10]
                summary_list.append(
                    f"- **Disaster #{disaster_num}**: {title} in {area} (Declared: {date})"
                )

            return "\n".join(summary_list)
        return f"Error calling FEMA API: HTTP Status {response.status_code}"
    except Exception as e:
        return f"API Connection Error: {str(e)}"


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the great-circle distance between two points on Earth in miles using the Haversine formula.
    """
    R = 3958.8  # Radius of Earth in miles

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def get_coordinates_from_zip(zip_code: str):
    """
    Geocodes a 5-digit US ZIP code to geographic coordinates.
    Uses Zippopotam.us as primary geocoder with OpenStreetMap Nominatim as fallback.
    """
    
    # Primary Geocoder: Zippopotam.us (Fast & highly reliable for US ZIP codes)
    try:
        backup_url = f"https://api.zippopotam.us/us/{zip_code}"
        resp = requests.get(backup_url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            place = data["places"][0]
            return float(place["latitude"]), float(place["longitude"])
    except Exception:
        pass

    # Fallback Geocoder: OpenStreetMap Nominatim
    url = f"https://nominatim.openstreetmap.org/search?postalcode={zip_code}&country=US&format=json"
    headers = {
        # Đổi thành email dự án hoặc email trường đại học của bạn để tuân thủ Nominatim API Policy
        "User-Agent": "DisasterAssistanceNavigatorApp/1.0 (disaster.navigator.project@gmail.com)",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data_list = response.json()
            if isinstance(data_list, list) and len(data_list) > 0:
                data = data_list[0]
                return float(data["lat"]), float(data["lon"])
    except Exception:
        pass

    return None, None

def search_drc_by_radius(zip_code: str, radius_miles: float = 100.0) -> str:
    """
    Finds nearest active Disaster Recovery Centers (DRCs) within a specified radius or nationwide fallback.
    """
    # Step 1: Geocode input ZIP code
    lat, lon = get_coordinates_from_zip(zip_code)

    if lat is None or lon is None:
        return f"Could not determine geographical coordinates for ZIP code '{zip_code}'. Please verify the input."

    # Step 2: Fetch Active DRCs from FEMA's ArcGIS REST API
    url = "https://gis.fema.gov/arcgis/rest/services/FEMA/DRC/FeatureServer/0/query?where=openCenter%3D'Y'&outFields=*&f=json"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return f"Unable to fetch active DRC locations (FEMA API Status: {response.status_code})."

        try:
            payload = response.json()
        except Exception:
            return "System Alert: ArcGIS API response parsing failed due to unexpected format."

        features = payload.get("features", [])
        all_centers = []

        # Step 3: Spatial distance calculations
        for feature in features:
            center = feature.get("attributes", {})
            c_lat = center.get("latitude") or center.get("LATITUDE")
            c_lon = center.get("longitude") or center.get("LONGITUDE")

            if c_lat and c_lon:
                dist = haversine_distance(lat, lon, float(c_lat), float(c_lon))
                all_centers.append((dist, center))

        # Sort all centers by geographical distance
        all_centers.sort(key=lambda x: x[0])

        # Filter centers within specified radius
        nearby_centers = [c for c in all_centers if c[0] <= radius_miles]

        # Fallback: If no DRCs within radius, return the nearest 3 active centers nationwide
        is_fallback = False
        if not nearby_centers and all_centers:
            nearby_centers = all_centers[:3]
            is_fallback = True

        if not nearby_centers:
            return "No active Disaster Recovery Centers found at this time."

        results = []
        if is_fallback:
            results.append(
                f"*Note: No active DRCs found within {radius_miles:.0f} miles. Displaying nearest active centers nationwide:*\n"
            )

        for dist, center in nearby_centers[:3]:
            name = (
                center.get("centerName")
                or center.get("NAME")
                or "Disaster Recovery Center"
            )
            addr = (
                center.get("addressLine1")
                or center.get("ADDRESS")
                or "Address unavailable"
            )
            city = center.get("city") or center.get("CITY") or ""
            state = center.get("state") or center.get("STATE") or ""
            zip_c = center.get("zipCode") or center.get("ZIP") or ""
            hours = (
                center.get("operatingHours")
                or center.get("HOURS")
                or "Mon-Sat 8:00 AM - 6:00 PM (Standard)"
            )

            results.append(
                f"- **{name}** ({dist:.1f} miles away)\n"
                f"  *Address:* {addr}, {city}, {state} {zip_c}\n"
                f"  *Hours:* {hours}"
            )

        return "\n\n".join(results)

    except Exception as e:
        return f"Error retrieving DRC data: {str(e)}"


# Alias functions for backward compatibility with main app router
def search_drc_by_zip(zip_code: str) -> str:
    return search_drc_by_radius(zip_code)


def get_nearby_drc(zip_code: str) -> str:
    return search_drc_by_radius(zip_code)


def get_fema_fraud_guidance() -> str:
    """
    Standard disaster fraud warnings mapped from official FEMA policies.
    """
    return """
OFFICIAL FEMA DISASTER FRAUD WARNINGS:
1. FEMA inspectors or representatives NEVER charge money to apply for or receive disaster assistance.
2. Beware of scams asking for wire transfers, bank account details, or upfront fees.
3. Official FEMA personnel always carry an official laminated photo ID badge.
4. Report suspected disaster fraud to the National Center for Disaster Fraud (NCDF) hotline at 866-720-5721 or email stopvfraud@oig.dhs.gov.
"""


if __name__ == "__main__":
    # Integration test block
    print("--- Running Backend Integration Tests ---")
    print(search_drc_by_radius("22030"))