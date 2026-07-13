-- Ontario 511 — Initialisation des schémas et tables Bronze
-- Architecture : append-only, déduplication via contrainte UNIQUE (même pattern que le projet Vélib)

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- ─── bronze.evenements ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bronze.evenements (
    row_id BIGSERIAL PRIMARY KEY,
    id BIGINT NOT NULL,
    sourceid TEXT,
    organization TEXT,
    roadwayname TEXT,
    direction TEXT,
    description TEXT,
    reported TIMESTAMPTZ,
    lastupdated TIMESTAMPTZ,
    startdate TIMESTAMPTZ,
    plannedenddate TIMESTAMPTZ,
    eventtype TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_evenements_update UNIQUE (id, lastupdated)
);

CREATE INDEX IF NOT EXISTS idx_evenements_lastupdated ON bronze.evenements USING BRIN (lastupdated);
CREATE INDEX IF NOT EXISTS idx_evenements_id ON bronze.evenements (id);

-- ─── bronze.constructions ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bronze.constructions (
    row_id BIGSERIAL PRIMARY KEY,
    id BIGINT NOT NULL,
    sourceid TEXT,
    organization TEXT,
    roadwayname TEXT,
    directionoftravel TEXT,
    description TEXT,
    reported TIMESTAMPTZ,
    lastupdated TIMESTAMPTZ,
    startdate TIMESTAMPTZ,
    plannedenddate TIMESTAMPTZ,
    lanesaffected TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    latitudesecondary DOUBLE PRECISION,
    longitudesecondary DOUBLE PRECISION,
    eventtype TEXT,
    isfullclosure BOOLEAN,
    comment TEXT,
    encodedpolyline TEXT,
    recurrence TEXT,
    recurrenceschedules TEXT,
    linkid TEXT,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_constructions_update UNIQUE (id, lastupdated)
);

CREATE INDEX IF NOT EXISTS idx_constructions_lastupdated ON bronze.constructions USING BRIN (lastupdated);
CREATE INDEX IF NOT EXISTS idx_constructions_id ON bronze.constructions (id);

-- ─── bronze.cameras ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bronze.cameras (
    row_id BIGSERIAL PRIMARY KEY,
    baseid BIGINT,
    source TEXT,
    sourceid TEXT,
    roadway TEXT,
    direction TEXT,
    location TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    viewid BIGINT NOT NULL,
    url TEXT,
    status TEXT,
    description TEXT,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_cameras_viewid UNIQUE (viewid)
);

CREATE INDEX IF NOT EXISTS idx_cameras_roadway ON bronze.cameras (roadway);

-- ─── bronze.roadconditions ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bronze.roadconditions (
    row_id BIGSERIAL PRIMARY KEY,
    locationdescription TEXT NOT NULL,
    condition TEXT,
    visibility TEXT,
    drifting TEXT,
    region TEXT,
    roadwayname TEXT NOT NULL,
    encodedpolyline TEXT,
    lastupdated TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_roadconditions_update UNIQUE (locationdescription, roadwayname, lastupdated)
);

CREATE INDEX IF NOT EXISTS idx_roadconditions_lastupdated ON bronze.roadconditions USING BRIN (lastupdated);
CREATE INDEX IF NOT EXISTS idx_roadconditions_region ON bronze.roadconditions (region);

-- ─── bronze.seasonalloads ───────────────────────────────────────────────────
-- Pas d'ID unique en source : dédup sur (segmentname, restriction_date),
-- puisqu'un même segment peut avoir plusieurs périodes de restriction dans le temps.

CREATE TABLE IF NOT EXISTS bronze.seasonalloads (
    row_id BIGSERIAL PRIMARY KEY,
    segmentname TEXT NOT NULL,
    routedescription TEXT,
    status TEXT,
    restriction_date DATE,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_seasonalloads_update UNIQUE (segmentname, restriction_date)
);

CREATE INDEX IF NOT EXISTS idx_seasonalloads_segment ON bronze.seasonalloads (segmentname);

-- ─── bronze.alerts ──────────────────────────────────────────────────────────
-- LastUpdated peut être NULL en source : pas fiable pour la dédup par snapshot.
-- On garde donc l'état courant (upsert sur id), pas d'historique accumulé ici.

CREATE TABLE IF NOT EXISTS bronze.alerts (
    id BIGINT PRIMARY KEY,
    message TEXT,
    notes TEXT,
    starttime TIMESTAMPTZ,
    endtime TIMESTAMPTZ,
    lastupdated TIMESTAMPTZ,
    regions TEXT,
    highimportance BOOLEAN,
    sendnotification BOOLEAN,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_alerts_id UNIQUE (id)
);

CREATE INDEX IF NOT EXISTS idx_alerts_highimportance ON bronze.alerts (highimportance);