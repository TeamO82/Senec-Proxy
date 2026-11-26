#!/usr/bin/env python3

import configparser
import json
import logging
import ssl
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


BASE_DIR = "/usr/local/senec-proxy"
CONFIG_FILE = f"{BASE_DIR}/senec-proxy.conf"
LOG_FILE = f"{BASE_DIR}/senec-proxy.log"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

SENEC_HOST = config.get("SENEC", "host")
SENEC_PORT = config.getint("SENEC", "port", fallback=443)
SSL_VERIFY = config.getboolean("SENEC", "ssl_verify", fallback=False)
POLL_INTERVAL = config.getfloat("SENEC", "poll_interval", fallback=10)
SECTION_REFRESH_INTERVAL = config.getfloat(
    "SENEC", "section_refresh_interval", fallback=300
)
TIMEOUT = config.getfloat("SENEC", "timeout", fallback=5)

LISTEN_HOST = config.get("PROXY", "listen_host", fallback="0.0.0.0")
LISTEN_PORT = config.getint("PROXY", "listen_port", fallback=8765)

SENEC_URL = f"https://{SENEC_HOST}:{SENEC_PORT}/lala.cgi"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger("senec-proxy")

# ---------------------------------------------------------------------------
# Cache and dynamic section list
# ---------------------------------------------------------------------------

cache_data = None
cache_timestamp = None
last_success = None
last_error = None

known_sections = []
last_section_refresh = None
last_section_refresh_monotonic = None

cache_lock = threading.Lock()

# ---------------------------------------------------------------------------
# SENEC communication
# ---------------------------------------------------------------------------


def create_ssl_context():
    if SSL_VERIFY:
        return ssl.create_default_context()

    return ssl._create_unverified_context()


def senec_request(request_data):
    """Send a JSON POST request to the SENEC lala.cgi interface."""

    payload = json.dumps(request_data).encode("utf-8")

    request = urllib.request.Request(
        SENEC_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT,
        context=create_ssl_context(),
    ) as response:
        raw_data = response.read()

    result = json.loads(raw_data.decode("utf-8"))

    if not isinstance(result, dict):
        raise ValueError("SENEC returned no JSON object")

    return result, len(raw_data)


def discover_sections():
    """Discover all available SENEC sections dynamically."""

    request_data = {
        "DEBUG": {"SECTIONS": ""},
        "PLAIN": {"SECTIONS": ""},
        "V": {"SECTIONS": ""},
    }

    response, response_size = senec_request(request_data)

    sections = []

    for category in ("DEBUG", "PLAIN", "V"):
        category_data = response.get(category)

        if not isinstance(category_data, dict):
            raise ValueError(
                f"Invalid section discovery response: {category}"
            )

        section_list = category_data.get("SECTIONS")

        if not isinstance(section_list, list):
            raise ValueError(
                f"Missing or invalid {category}.SECTIONS"
            )

        for entry in section_list:

            if not isinstance(entry, str):
                raise ValueError(
                    f"Invalid section name in {category}.SECTIONS"
                )

            if category in ("DEBUG", "PLAIN"):
                if not entry.startswith("st_"):
                    raise ValueError(
                        f"Unexpected section prefix: {entry}"
                    )

                section_name = entry[3:]

            else:
                section_name = "V_" + entry

            if not section_name:
                raise ValueError("Empty section name received")

            if section_name not in sections:
                sections.append(section_name)

    if not sections:
        raise ValueError("SENEC returned an empty section list")

    logger.info(
        "Section discovery OK: %d sections, %d bytes",
        len(sections),
        response_size,
    )

    return sections


def poll_senec():
    global cache_data
    global cache_timestamp
    global last_success
    global last_error
    global known_sections
    global last_section_refresh
    global last_section_refresh_monotonic

    start = time.monotonic()
    discovery_error = None

    # -------------------------------------------------------
    # Refresh the section list when required.
    # -------------------------------------------------------

    refresh_required = (
        last_section_refresh_monotonic is None
        or time.monotonic() - last_section_refresh_monotonic
        >= SECTION_REFRESH_INTERVAL
    )

    if refresh_required:

        try:
            new_sections = discover_sections()

            known_sections = new_sections
            last_section_refresh = time.time()
            last_section_refresh_monotonic = time.monotonic()

            logger.info(
                "Updated section list: %d sections",
                len(known_sections),
            )

        except Exception as exc:
            discovery_error = str(exc)

            logger.error(
                "Section discovery FAILED: %s",
                exc,
            )

    # No usable section list available yet.
    if not known_sections:
        error_message = (
            f"Section discovery failed: {discovery_error}"
            if discovery_error
            else "No sections available"
        )

        with cache_lock:
            last_error = error_message

        return

    # -------------------------------------------------------
    # Request all discovered sections.
    # -------------------------------------------------------

    request_data = {
        section: {}
        for section in known_sections
    }

    try:
        new_data, response_size = senec_request(request_data)

        # Verify that the response contains every requested
        # section and that every section has an object structure.
        for section in known_sections:

            if section not in new_data:
                raise ValueError(
                    f"Incomplete SENEC response: missing section {section}"
                )

            if not isinstance(new_data[section], dict):
                raise ValueError(
                    f"Invalid data structure in section {section}"
                )

        duration = time.monotonic() - start
        success_time = time.time()

        # Replace the complete cache atomically.
        with cache_lock:
            cache_data = new_data
            cache_timestamp = success_time
            last_success = success_time
            last_error = discovery_error

        logger.info(
            "SENEC poll OK: %d sections, %d bytes, %.3fs",
            len(new_data),
            response_size,
            duration,
        )

        if discovery_error:
            logger.warning(
                "Data updated using previous section list; "
                "section discovery error: %s",
                discovery_error,
            )

    except Exception as exc:
        duration = time.monotonic() - start

        error_message = str(exc)

        if discovery_error:
            error_message = (
                f"{error_message}; section discovery: {discovery_error}"
            )

        with cache_lock:
            last_error = error_message

        logger.error(
            "SENEC poll FAILED after %.3fs: %s",
            duration,
            error_message,
        )


def polling_loop():
    while True:
        time.sleep(POLL_INTERVAL)
        poll_senec()


# ---------------------------------------------------------------------------
# Cache access
# ---------------------------------------------------------------------------


def get_cached_value(section, key):
    if cache_data is None:
        return "VARIABLE_NOT_FOUND"

    section_data = cache_data.get(section)

    if not isinstance(section_data, dict):
        return "VARIABLE_NOT_FOUND"

    if key not in section_data:
        return "VARIABLE_NOT_FOUND"

    return section_data[key]



def build_client_response(request_data):
    result = {}

    if not isinstance(request_data, dict):
        return result

    with cache_lock:
        for section, requested_values in request_data.items():

            if not isinstance(requested_values, dict):
                continue

            # Abschnitt im Cache suchen
            section_data = (
                cache_data.get(section)
                if isinstance(cache_data, dict)
                else None
            )

            # Unbekannter Abschnitt
            if not isinstance(section_data, dict):
                result[section] = {
                    "OBJECT_NOT_FOUND": ""
                }
                continue

            # Leeres Objekt bedeutet: gesamten Abschnitt liefern
            if not requested_values:
                result[section] = dict(section_data)
                continue

            # Einzelne Variablen aus dem Cache liefern
            result[section] = {}

            for key in requested_values:
                if key in section_data:
                    result[section][key] = section_data[key]
                else:
                    result[section][key] = "VARIABLE_NOT_FOUND"

    return result



# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------


class ProxyHandler(BaseHTTPRequestHandler):

    def log_message(self, format_string, *args):
        logger.info(
            "%s - %s",
            self.client_address[0],
            format_string % args,
        )

    def send_json(self, data, status=200):
        payload = json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        self.wfile.write(payload)

    def do_GET(self):

        if self.path == "/status":

            with cache_lock:
                now = time.time()

                cache_age = None
                if cache_timestamp is not None:
                    cache_age = round(now - cache_timestamp, 3)

                status = {
                    "status": (
                        "ok" if cache_data is not None else "starting"
                    ),
                    "senec_host": SENEC_HOST,
                    "senec_port": SENEC_PORT,
                    "poll_interval": POLL_INTERVAL,
                    "section_refresh_interval": SECTION_REFRESH_INTERVAL,
                    "cache_age": cache_age,
                    "last_success": last_success,
                    "last_error": last_error,
                    "sections": (
                        len(cache_data) if cache_data else 0
                    ),
                    "known_sections": len(known_sections),
                    "last_section_refresh": last_section_refresh,
                }

            self.send_json(status)
            return

        if self.path == "/cache":

            with cache_lock:
                data = cache_data

            if data is None:
                self.send_json({}, status=503)
            else:
                self.send_json(data)

            return

        self.send_json(
            {"error": "Not Found"},
            status=404,
        )

    def do_POST(self):

        if self.path != "/lala.cgi":
            self.send_json(
                {"error": "Not Found"},
                status=404,
            )
            return

        try:
            content_length = int(
                self.headers.get("Content-Length", "0")
            )

            raw_body = self.rfile.read(content_length)
            request_data = json.loads(raw_body.decode("utf-8"))

        except Exception:
            self.send_json(
                {"error": "Invalid JSON"},
                status=400,
            )
            return

        response_data = build_client_response(request_data)

        self.send_json(response_data)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():

    logger.info("Starting SENEC proxy")
    logger.info("SENEC URL: %s", SENEC_URL)
    logger.info("Poll interval: %.1fs", POLL_INTERVAL)
    logger.info(
        "Section refresh interval: %.1fs",
        SECTION_REFRESH_INTERVAL,
    )
    logger.info(
        "Listen: %s:%d",
        LISTEN_HOST,
        LISTEN_PORT,
    )

    # Initial section discovery and data poll before
    # accepting client connections.
    poll_senec()

    polling_thread = threading.Thread(
        target=polling_loop,
        daemon=True,
    )

    polling_thread.start()

    server = ThreadingHTTPServer(
        (LISTEN_HOST, LISTEN_PORT),
        ProxyHandler,
    )

    logger.info(
        "HTTP server listening on %s:%d",
        LISTEN_HOST,
        LISTEN_PORT,
    )

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        logger.info("Stopping SENEC proxy")

    finally:
        server.server_close()


if __name__ == "__main__":
    main()
