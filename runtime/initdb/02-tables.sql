-- Tabelas usadas pelo backend FastAPI.
-- Roda automaticamente na primeira vez que o container postgis sobe (via docker-entrypoint-initdb.d).
-- Para aplicar em um postgis ja existente, ver docs/04-infraestrutura.md (psql -f).

-- =============================================================================
-- alagamentos_realtime: snapshot dos pontos ativos do CGE-SP
-- =============================================================================
CREATE TABLE IF NOT EXISTS alagamentos_realtime (
    id              SERIAL PRIMARY KEY,
    endereco_raw    TEXT,
    bairro          TEXT,
    referencia      TEXT,
    sentido         TEXT,
    lat             DOUBLE PRECISION NOT NULL,
    lng             DOUBLE PRECISION NOT NULL,
    geom            GEOMETRY(Point, 4326) GENERATED ALWAYS AS
                        (ST_SetSRID(ST_MakePoint(lng, lat), 4326)) STORED,
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alagamentos_geom
    ON alagamentos_realtime USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_alagamentos_active
    ON alagamentos_realtime (resolved_at)
    WHERE resolved_at IS NULL;

-- =============================================================================
-- geocode_cache: resultados do Nominatim cacheados por endereco normalizado
-- =============================================================================
CREATE TABLE IF NOT EXISTS geocode_cache (
    endereco_norm   TEXT PRIMARY KEY,
    endereco_raw    TEXT NOT NULL,
    lat             DOUBLE PRECISION NOT NULL,
    lng             DOUBLE PRECISION NOT NULL,
    display_name    TEXT,
    source          TEXT NOT NULL DEFAULT 'nominatim',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
