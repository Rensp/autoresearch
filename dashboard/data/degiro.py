"""
DEGIRO real-time price feed via the unofficial quotecast API.

Uses degiro-connector (reverse-engineered DEGIRO WebSocket).
Credentials are loaded from a .env file or environment variables:
    DEGIRO_USERNAME=jouw@email.nl
    DEGIRO_PASSWORD=jouwwachtwoord
    DEGIRO_TOTP_SECRET=   (optioneel, alleen bij 2FA)

Start the feed with start_feed(). It runs a background thread that
polls DEGIRO's quotecast every ~2 seconds and writes prices to a
module-level cache. Streamlit reads from get_price() without blocking.
"""

import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

from degiro_connector.trading.actions.action_connect import ActionConnect
from degiro_connector.trading.actions.action_get_client_details import ActionGetClientDetails
from degiro_connector.trading.actions.action_product_search import ActionProductSearch
from degiro_connector.trading.models.credentials import Credentials
from degiro_connector.trading.models.product_search import LookupRequest
from degiro_connector.quotecast.tools.ticker_fetcher import TickerFetcher
from degiro_connector.quotecast.tools.ticker_to_metric_list import TickerToMetricList
from degiro_connector.quotecast.models.ticker import TickerRequest
from degiro_connector.quotecast.models.metric import MetricType

load_dotenv()

logger = logging.getLogger(__name__)
logging.getLogger("degiro_connector").setLevel(logging.WARNING)

# Known VWD ID for the DAX Performance Index on DEGIRO
DAX_VWD_ID = "360015751"
POLL_INTERVAL = 2.0  # seconds between quotecast polls
RECONNECT_DELAY = 10.0  # seconds before reconnecting on failure

_METRICS = [MetricType.LastPrice, MetricType.LastDate, MetricType.LastTime]

# ── Shared state (thread-safe) ────────────────────────────────────────────────
_lock = threading.Lock()
_state: dict = {
    "prices": {},        # vwd_id (str) -> float
    "connected": False,
    "error": None,
    "last_update": None,
}
_stop_event = threading.Event()
_feed_thread: Optional[threading.Thread] = None

# ISIN -> vwd_id lookup cache (populated during search)
_isin_to_vwd: dict[str, str] = {}


def get_price(vwd_id: str) -> Optional[float]:
    """Return latest price for a VWD product ID, or None if unavailable."""
    with _lock:
        return _state["prices"].get(vwd_id)


def get_dax_price() -> Optional[float]:
    return get_price(DAX_VWD_ID)


def get_status() -> dict:
    with _lock:
        return {
            "connected": _state["connected"],
            "error": _state["error"],
            "last_update": _state["last_update"],
            "n_products": len(_state["prices"]),
        }


def get_vwd_id_for_isin(isin: str) -> Optional[str]:
    """Return cached VWD ID for an ISIN (populated after product search)."""
    return _isin_to_vwd.get(isin)


def is_running() -> bool:
    return _feed_thread is not None and _feed_thread.is_alive()


def start_feed(extra_isins: list[str] | None = None) -> bool:
    """
    Start the background feed thread.
    Returns True if started, False if credentials are missing.
    extra_isins: list of product ISINs to track in addition to DAX.
    """
    global _feed_thread

    username = os.environ.get("DEGIRO_USERNAME", "")
    password = os.environ.get("DEGIRO_PASSWORD", "")

    if not username or not password:
        with _lock:
            _state["error"] = "Geen DEGIRO inloggegevens gevonden. Maak een .env bestand aan."
        return False

    if _feed_thread and _feed_thread.is_alive():
        return True

    _stop_event.clear()
    _feed_thread = threading.Thread(
        target=_run_feed,
        args=(username, password, extra_isins or []),
        daemon=True,
        name="degiro-feed",
    )
    _feed_thread.start()
    return True


def stop_feed() -> None:
    _stop_event.set()


class CredentialsError(Exception):
    """Raised when DEGIRO rejects username/password. Do not retry."""
    pass


def _run_feed(username: str, password: str, extra_isins: list[str]) -> None:
    """Main background thread: login → search products → stream prices."""
    while not _stop_event.is_set():
        try:
            _stream(username, password, extra_isins)
        except CredentialsError as exc:
            # Wrong password — stop retrying to avoid account lockout
            with _lock:
                _state["connected"] = False
                _state["error"] = str(exc)
            logger.error("DEGIRO credentials error (not retrying): %s", exc)
            return  # Exit thread permanently
        except Exception as exc:
            with _lock:
                _state["connected"] = False
                _state["error"] = f"Verbindingsfout: {exc}"
            logger.error("DEGIRO feed error: %s", exc)
            _stop_event.wait(RECONNECT_DELAY)


def _stream(username: str, password: str, extra_isins: list[str]) -> None:
    """Single connection lifecycle: login, subscribe, poll until error."""
    session = TickerFetcher.build_session()

    # ── Step 1: Login via trading API ─────────────────────────────────────────
    with _lock:
        _state["error"] = "Inloggen bij DEGIRO..."

    totp_secret = os.environ.get("DEGIRO_TOTP_SECRET") or None
    credentials = Credentials(
        username=username,
        password=password,
        totp_secret_key=totp_secret,
    )

    try:
        trading_session_id = ActionConnect.get_session_id(
            credentials=credentials,
            session=session,
        )
    except Exception as exc:
        err_str = str(exc)
        if "badCredentials" in err_str or "bad_credentials" in err_str.lower():
            msg = "❌ Verkeerde gebruikersnaam of wachtwoord. Pas je .env aan en herstart de app."
            with _lock:
                _state["error"] = msg
            raise CredentialsError(msg) from exc
        with _lock:
            _state["error"] = f"Login mislukt: {exc}"
        raise

    if not trading_session_id:
        msg = "❌ Verkeerde gebruikersnaam of wachtwoord. Pas je .env aan en herstart de app."
        with _lock:
            _state["error"] = msg
        raise CredentialsError(msg)

    # ── Step 2: Get user_token (int) for quotecast ────────────────────────────
    client_details = ActionGetClientDetails.get_client_details(
        session_id=trading_session_id,
        session=session,
    )
    if not client_details:
        raise ConnectionError("Could not get client details")

    user_token = client_details.get("data", {}).get("id")
    if not user_token:
        raise ConnectionError("Could not extract user_token from client details")

    # ── Step 3: Resolve extra ISINs to VWD IDs ────────────────────────────────
    vwd_ids_to_track = {DAX_VWD_ID}
    for isin in extra_isins:
        vwd_id = _search_vwd_id(isin, trading_session_id, credentials, session)
        if vwd_id:
            _isin_to_vwd[isin] = vwd_id
            vwd_ids_to_track.add(vwd_id)

    # ── Step 4: Get quotecast session_id ─────────────────────────────────────
    qc_session_id = TickerFetcher.get_session_id(
        user_token=int(user_token),
        session=session,
    )
    if not qc_session_id:
        raise ConnectionError("Could not get quotecast session_id")

    # ── Step 5: Subscribe to product metrics ──────────────────────────────────
    ticker_request = TickerRequest(
        request_type="subscription",
        request_map={vwd_id: _METRICS for vwd_id in vwd_ids_to_track},
    )
    TickerFetcher.subscribe(
        ticker_request=ticker_request,
        session_id=qc_session_id,
        session=session,
    )

    with _lock:
        _state["connected"] = True
        _state["error"] = None

    metric_parser = TickerToMetricList()
    stored_prices: dict[str, float] = {}

    # ── Step 6: Poll loop ─────────────────────────────────────────────────────
    while not _stop_event.is_set():
        try:
            ticker = TickerFetcher.fetch_ticker(
                session_id=qc_session_id,
                session=session,
            )
        except BrokenPipeError:
            # Session expired — need new quotecast session_id
            qc_session_id = TickerFetcher.get_session_id(
                user_token=int(user_token),
                session=session,
            )
            if qc_session_id:
                TickerFetcher.subscribe(
                    ticker_request=ticker_request,
                    session_id=qc_session_id,
                    session=session,
                )
            continue
        except Exception as exc:
            with _lock:
                _state["connected"] = False
                _state["error"] = str(exc)
            raise

        if ticker and ticker.json_text != '[{"m":"h"}]':
            metrics = metric_parser.parse(ticker=ticker)
            for metric in metrics:
                if metric.metric_type == MetricType.LastPrice:
                    try:
                        stored_prices[metric.product_id] = float(metric.value)
                    except (ValueError, TypeError):
                        pass

            with _lock:
                _state["prices"].update(stored_prices)
                _state["last_update"] = datetime.now()

        _stop_event.wait(POLL_INTERVAL)


def _search_vwd_id(
    isin: str,
    session_id: str,
    credentials: Credentials,
    session: requests.Session,
) -> Optional[str]:
    """Find the VWD product ID for a given ISIN via trading API product search."""
    try:
        request = LookupRequest(
            search_text=isin,
            limit=5,
            offset=0,
        )
        result = ActionProductSearch.product_search(
            product_request=request,
            session_id=session_id,
            credentials=credentials,
            raw=True,
            session=session,
        )
        if not result:
            return None

        products = result.get("products", [])
        for product in products:
            if product.get("isin") == isin:
                # vwdId is the field used for quotecast subscriptions
                return str(product.get("vwdId") or product.get("id", ""))
        if products:
            return str(products[0].get("vwdId") or products[0].get("id", ""))
    except Exception as exc:
        logger.warning("Product search failed for %s: %s", isin, exc)
    return None
