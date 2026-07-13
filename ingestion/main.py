"""
Point d'entrée : instancie et exécute les 6 fetchers Ontario 511.
L'orchestration (planification) est déléguée à Airflow — ce script
lance simplement un cycle complet de collecte, une fois appelé.
"""

import logging

from fetchers.ontario511_fetcher import Ontario511Fetcher
from fetchers.transforms import transform_camera, transform_roadcondition, transform_alert

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


def build_fetchers() -> list[Ontario511Fetcher]:
    return [
        Ontario511Fetcher(
            name="événements",
            endpoint="event",
            table="evenements",
            columns=["id", "sourceid", "organization", "roadwayname", "direction",
                     "description", "reported", "lastupdated", "startdate",
                     "plannedenddate", "eventtype", "latitude", "longitude"],
            conflict_constraint="uq_evenements_update",
        ),
        Ontario511Fetcher(
            name="constructions",
            endpoint="constructionprojects",
            table="constructions",
            columns=["id", "sourceid", "organization", "roadwayname", "directionoftravel",
                     "description", "reported", "lastupdated", "startdate", "plannedenddate",
                     "lanesaffected", "latitude", "longitude", "latitudesecondary",
                     "longitudesecondary", "eventtype", "isfullclosure", "comment",
                     "encodedpolyline", "recurrence", "recurrenceschedules", "linkid"],
            conflict_constraint="uq_constructions_update",
        ),
        Ontario511Fetcher(
            name="caméras",
            endpoint="cameras",
            table="cameras",
            columns=["baseid", "source", "sourceid", "roadway", "direction", "location",
                     "latitude", "longitude", "viewid", "url", "status", "description"],
            conflict_constraint="uq_cameras_viewid",
            transform_row=transform_camera,
            do_update=True,
        ),
        Ontario511Fetcher(
            name="conditions routières",
            endpoint="roadconditions",
            table="roadconditions",
            columns=["locationdescription", "condition", "visibility", "drifting",
                     "region", "roadwayname", "encodedpolyline", "lastupdated"],
            conflict_constraint="uq_roadconditions_update",
            transform_row=transform_roadcondition,
        ),
        Ontario511Fetcher(
            name="charges saisonnières",
            endpoint="seasonalloadapi",
            table="seasonalloads",
            columns=["segmentname", "routedescription", "status", "restriction_date",
                     "latitude", "longitude"],
            conflict_constraint="uq_seasonalloads_update",
        ),
        Ontario511Fetcher(
            name="alertes",
            endpoint="alerts",
            table="alerts",
            columns=["id", "message", "notes", "starttime", "endtime", "lastupdated",
                     "regions", "highimportance", "sendnotification"],
            conflict_constraint="uq_alerts_id",
            transform_row=transform_alert,
            do_update=True,
        ),
    ]


def main() -> None:
    for fetcher in build_fetchers():
        fetcher.run()


if __name__ == "__main__":
    main()