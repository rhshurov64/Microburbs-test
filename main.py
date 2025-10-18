from fastapi import FastAPI, Query
import requests
from typing import Dict, Any, List
import statistics
import math

app = FastAPI(title="Belmont North Property Intelligence API")

API_URL = "https://www.microburbs.com.au/report_generator/api/suburb/properties"
API_PARAMS = {"suburb": "Belmont North"}
API_HEADERS = {
    "Authorization": "Bearer test",
    "Content-Type": "application/json"
}

# ---------- Utility Functions ----------


def parse_number(value):
    if value in [None, "None", "nan", ""]:
        return None
    try:
        return float(str(value).replace("m²", "").replace(" ", ""))
    except:
        return None


def distance(lat1, lon1, lat2, lon2):
    """Haversine formula for distance in km"""
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def fetch_properties():
    response = requests.get(API_URL, params=API_PARAMS, headers=API_HEADERS)
    return response.json().get("results", [])


@app.get("/all-properties", response_model=List[Dict[str, Any]])
def all_properties():
    properties = fetch_properties()
    all_props = []

    for p in properties:
        all_props.append({
            "street": p["address"]["street"],
            "suburb": p["address"]["sal"],
            "state": p["address"]["state"],
            "price": parse_number(p.get("price")),
            "bedrooms": parse_number(p["attributes"].get("bedrooms")),
            "bathrooms": parse_number(p["attributes"].get("bathrooms")),
            "land_size_m2": parse_number(p["attributes"].get("land_size")),
            "property_type": p.get("property_type"),
            "listing_date": p.get("listing_date"),
            "description": p["attributes"].get("description"),
            "latitude": p["coordinates"]["latitude"],
            "longitude": p["coordinates"]["longitude"]
        })

    return all_props


# ---------- 1. Suburb Summary ----------


@app.get("/suburb-summary", response_model=Dict[str, Any])
def suburb_summary():
    properties = fetch_properties()
    prices, bedrooms, bathrooms, land_sizes = [], [], [], []
    property_type_count = {}

    for p in properties:
        price = parse_number(p.get("price"))
        bed = parse_number(p["attributes"].get("bedrooms"))
        bath = parse_number(p["attributes"].get("bathrooms"))
        land = parse_number(p["attributes"].get("land_size"))
        ptype = p.get("property_type")

        if price:
            prices.append(price)
        if bed:
            bedrooms.append(bed)
        if bath:
            bathrooms.append(bath)
        if land:
            land_sizes.append(land)
        if ptype:
            property_type_count[ptype] = property_type_count.get(ptype, 0) + 1

    return {
        "total_properties": len(properties),
        "average_price": round(statistics.mean(prices), 2) if prices else None,
        "median_price": round(statistics.median(prices), 2) if prices else None,
        "average_bedrooms": round(statistics.mean(bedrooms), 2) if bedrooms else None,
        "average_bathrooms": round(statistics.mean(bathrooms), 2) if bathrooms else None,
        "average_land_size_m2": round(statistics.mean(land_sizes), 2) if land_sizes else None,
        "most_common_property_type": max(property_type_count, key=property_type_count.get) if property_type_count else None,
        "property_type_count": property_type_count
    }

# ---------- 2. Property Search & Filter ----------


@app.get("/search-properties", response_model=List[Dict[str, Any]])
def search_properties(
    min_price: float = Query(0),
    max_price: float = Query(10000000),
    bedrooms: int = Query(None),
    bathrooms: int = Query(None),
    property_type: str = Query(None)
):
    properties = fetch_properties()
    results = []

    for p in properties:
        price = parse_number(p.get("price"))
        bed = parse_number(p["attributes"].get("bedrooms"))
        bath = parse_number(p["attributes"].get("bathrooms"))
        ptype = p.get("property_type")

        if price is None:
            continue
        if not (min_price <= price <= max_price):
            continue
        if bedrooms and bed != bedrooms:
            continue
        if bathrooms and bath != bathrooms:
            continue
        if property_type and ptype != property_type:
            continue

        results.append({
            "street": p["address"]["street"],
            "price": price,
            "bedrooms": bed,
            "bathrooms": bath,
            "property_type": ptype
        })

    return results

# ---------- 3. Top Expensive & Best Value ----------


@app.get("/property-ranking", response_model=Dict[str, Any])
def property_ranking():
    properties = fetch_properties()
    top_expensive, best_value = [], []

    for p in properties:
        price = parse_number(p.get("price"))
        land = parse_number(p["attributes"].get("land_size"))
        street = p["address"]["street"]

        if price:
            top_expensive.append({"street": street, "price": price})
        if price and land:
            best_value.append(
                {"street": street, "price_per_m2": round(price/land, 2)})

    top_expensive = sorted(
        top_expensive, key=lambda x: x["price"], reverse=True)[:3]
    best_value = sorted(best_value, key=lambda x: x["price_per_m2"])[:3]

    return {
        "top_3_expensive": top_expensive,
        "top_3_best_value": best_value
    }

# ---------- 4. Family-Friendly Properties ----------


@app.get("/family-friendly", response_model=List[Dict[str, Any]])
def family_friendly_properties():
    properties = fetch_properties()
    family_list = []

    for p in properties:
        bed = parse_number(p["attributes"].get("bedrooms"))
        bath = parse_number(p["attributes"].get("bathrooms"))
        land = parse_number(p["attributes"].get("land_size"))
        price = parse_number(p.get("price"))
        street = p["address"]["street"]

        if bed >= 3 and bath >= 2 and land >= 500:
            score = round(bed + bath + land/1000, 2)
            family_list.append(
                {"street": street, "score": score, "price": price})

    return sorted(family_list, key=lambda x: x["score"], reverse=True)[:5]

# ---------- 5. Property Comparison ----------


@app.get("/compare-properties", response_model=List[Dict[str, Any]])
def compare_properties(street1: str, street2: str):
    properties = fetch_properties()
    result = []

    for p in properties:
        if p["address"]["street"] in [street1, street2]:
            price = parse_number(p.get("price"))
            bed = parse_number(p["attributes"].get("bedrooms"))
            bath = parse_number(p["attributes"].get("bathrooms"))
            land = parse_number(p["attributes"].get("land_size"))
            result.append({
                "street": p["address"]["street"],
                "price": price,
                "bedrooms": bed,
                "bathrooms": bath,
                "land_size_m2": land,
                "price_per_m2": round(price/land, 2) if price and land else None
            })

    return result

 

