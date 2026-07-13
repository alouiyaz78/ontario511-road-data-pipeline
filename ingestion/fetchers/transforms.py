"""Transformations de lignes spécifiques aux sources dont la structure API
ne correspond pas au mapping 1:1 par défaut (imbrication, listes à joindre)."""

from .ontario511_fetcher import Ontario511Fetcher


def transform_camera(item: dict) -> list[dict]:
    """Aplatit les vues imbriquées : une ligne par (caméra, vue)."""
    rows = []
    for view in item.get("Views", []):
        rows.append({
            "baseid": item.get("Id") or item.get("ID"),
            "source": item.get("Source"),
            "sourceid": item.get("SourceId"),
            "roadway": item.get("Roadway"),
            "direction": item.get("Direction"),
            "location": item.get("Location"),
            "latitude": item.get("Latitude"),
            "longitude": item.get("Longitude"),
            "viewid": view.get("Id"),
            "url": view.get("Url"),
            "status": view.get("Status"),
            "description": view.get("Description"),
        })
    return rows


def transform_roadcondition(item: dict) -> list[dict]:
    """Joint la liste Condition (ex: ['Wet', 'Snow']) en une chaîne."""
    condition = item.get("Condition", [])
    condition_str = "|".join(condition) if isinstance(condition, list) else str(condition or "")
    return [{
        "locationdescription": item.get("LocationDescription"),
        "condition": condition_str,
        "visibility": item.get("Visibility"),
        "drifting": item.get("Drifting"),
        "region": item.get("Region"),
        "roadwayname": item.get("RoadwayName"),
        "encodedpolyline": item.get("EncodedPolyline"),
        "lastupdated": Ontario511Fetcher._epoch_to_datetime(item.get("LastUpdated")),
    }]


def transform_alert(item: dict) -> list[dict]:
    """Joint la liste Regions (ex: ['Central', 'Eastern']) en une chaîne."""
    regions = item.get("Regions", [])
    regions_str = "|".join(regions) if isinstance(regions, list) else str(regions or "")
    return [{
        "id": item.get("Id"),
        "message": item.get("Message"),
        "notes": item.get("Notes"),
        "starttime": Ontario511Fetcher._epoch_to_datetime(item.get("StartTime")),
        "endtime": Ontario511Fetcher._epoch_to_datetime(item.get("EndTime")),
        "lastupdated": Ontario511Fetcher._epoch_to_datetime(item.get("LastUpdated")),
        "regions": regions_str,
        "highimportance": item.get("HighImportance"),
        "sendnotification": item.get("SendNotification"),
    }]