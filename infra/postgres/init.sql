-- =============================================================================
-- Awaaz — Postgres bootstrap.  Runs once on cluster initialisation.
-- =============================================================================

-- Extensions used across the codebase.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";       -- pgvector
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Two databases — main app and a separate one for Langfuse self-hosted.
SELECT 'CREATE DATABASE langfuse'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'langfuse')\gexec

-- Application role.  Kept separate from the superuser so RLS FORCE blocks bypass.
DO
$$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'awaaz_app') THEN
        CREATE ROLE awaaz_app NOLOGIN;
    END IF;
END
$$;

-- The runtime DB user is the role configured in DATABASE_URL.  It inherits
-- awaaz_app so RLS policies fire.
DO
$$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = current_user) THEN
        EXECUTE format('CREATE ROLE %I LOGIN INHERIT', current_user);
    END IF;
END
$$;

GRANT awaaz_app TO CURRENT_USER;

-- Multi-tenant context GUCs (read in RLS predicates).  Defaults are an empty
-- string so any unprivileged session that forgets to set them sees zero rows.
ALTER DATABASE awaaz SET app.current_org   = '';
ALTER DATABASE awaaz SET app.current_store = '';
ALTER DATABASE awaaz SET app.current_user  = '';
ALTER DATABASE awaaz SET app.bypass_rls    = 'off';
