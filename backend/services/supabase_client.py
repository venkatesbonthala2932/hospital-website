"""
supabase_client.py — Supabase connection helpers

WHY NO SINGLETON FOR ADMIN CLIENT:
  supabase-py 2.x uses httpx with HTTP/2 enabled (via the h2 package).
  When multiple Flask routes fire concurrently (e.g. admin dashboard
  loads 5 endpoints at once), sharing a single httpx.Client causes
  HTTP/2 stream-multiplexing errors:
    "Trailers must have END_STREAM set."
  Creating a fresh client per call avoids this entirely.
  create_client() is cheap — it only instantiates Python objects;
  no network connection is made until .execute() is called.

TWO KEY CLIENTS:
  get_supabase()       → anon key; only used in auth_service.py for JWT validation
  get_admin_supabase() → service-role key; used for all DB reads/writes
"""
from supabase import create_client, Client
from config import Config

# Anon client stays as a singleton — auth_service uses it sequentially
_anon_client: Client | None = None


def get_supabase() -> Client:
    """Anon key client — only used for JWT validation in auth_service.py"""
    global _anon_client
    if _anon_client is None:
        try:
            _anon_client = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
        except Exception as e:
            raise RuntimeError(
                f"Could not connect to Supabase with anon key. "
                f"Check SUPABASE_URL and SUPABASE_ANON_KEY in your .env file.\n"
                f"Original error: {e}"
            )
    return _anon_client


def get_admin_supabase() -> Client:
    """
    Service role client — fresh instance per call to prevent HTTP/2
    concurrent-stream errors when multiple routes execute in parallel.
    """
    try:
        return create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY)
    except Exception as e:
        raise RuntimeError(
            f"Could not connect to Supabase with service key. "
            f"Check SUPABASE_SERVICE_KEY in your .env file.\n"
            f"Original error: {e}"
        )
