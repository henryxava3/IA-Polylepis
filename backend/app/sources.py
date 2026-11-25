"""Source adapters. Provider content is untrusted data, never executable instructions."""
import hashlib
import ipaddress
import re
import socket
import time
import unicodedata
from urllib.parse import unquote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from .config import settings

AGENT = "PolylepisLocal/0.1"
OPEN_LICENSES = {"cc-by", "cc-by-sa", "cc0", "public-domain"}
TERMS = ("polylepis", "quenual", "quenua", "queuna", "quinual", "quewina", "yagual")


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", value))


def doi_value(value: str | None) -> str | None:
    if not value:
        return None
    value = unquote(value.strip()).lower()
    value = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:\s*)", "", value)
    return value if re.fullmatch(r"10\.\d{4,9}/\S+", value) else None


def license_value(value: str | None) -> str | None:
    if not value:
        return None
    value = value.lower().strip().rstrip("/")
    if value in OPEN_LICENSES:
        return value
    parsed = urlparse(value)
    if parsed.hostname in {"creativecommons.org", "www.creativecommons.org"}:
        if re.fullmatch(r"/licenses/by/\d\.\d", parsed.path):
            return "cc-by"
        if re.fullmatch(r"/licenses/by-sa/\d\.\d", parsed.path):
            return "cc-by-sa"
        if re.fullmatch(r"/publicdomain/zero/1\.0", parsed.path):
            return "cc0"
    return None


def relevant(title: str, abstract: str = "") -> bool:
    # "polylepis" is also a species epithet in unrelated genera (algae, fish, etc.).
    text = re.sub(r"<[^>]+>", " ", title + " " + abstract)
    text = re.sub(r"\b(?:Chrysochromulina|Prymnesium|Telestes|Dendroaspis|Rhododendron)\s+polylepis\b", " ", text, flags=re.I)
    text = re.sub(r"\b(?!Polylepis\b)[A-Z][a-z]{3,}\s+polylepis\b", " ", text)
    return bool(re.search(r"\bpolylepis\b", normalized(text)))


def reconstruct_abstract(index: dict | None) -> str:
    if not index:
        return ""
    positions = [(p, word) for word, indices in index.items() for p in indices]
    return " ".join(word for _, word in sorted(positions))


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SourceError(Exception):
    pass


def client():
    return httpx.Client(timeout=40, headers={"User-Agent": AGENT + (
        f" (mailto:{settings.contact_email})" if settings.contact_email else "")}, follow_redirects=False)


def get_json(url: str, params: dict | None = None, auth=None):
    with client() as http:
        for attempt in range(4):
            try:
                response = http.get(url, params=params, auth=auth)
            except httpx.TransportError:
                if attempt == 3:
                    raise SourceError(f"No se pudo conectar con {urlparse(url).hostname}.") from None
                time.sleep(2 ** attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                try:
                    delay = min(30, max(1, int(response.headers.get("Retry-After", 2 ** attempt))))
                except ValueError:
                    delay = 2 ** attempt
                time.sleep(delay)
                continue
            if response.is_error:
                raise SourceError(f"{urlparse(url).hostname}: HTTP {response.status_code}.")
            return response.json()
    raise SourceError(f"{urlparse(url).hostname}: límite temporal o servicio no disponible.")


def public_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    if parsed.port not in {None, 443}:
        return False
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (ValueError, OSError):
        return False


def download_pdf(url: str) -> bytes:
    with client() as http:
        for _ in range(5):
            if not public_url(url):
                raise SourceError("URL del PDF no autorizada: se requiere HTTPS y un servidor público.")
            robots_url = urljoin(url, "/robots.txt")
            robots = http.get(robots_url)
            if robots.status_code == 200:
                rules = RobotFileParser()
                rules.parse(robots.text.splitlines())
                if not rules.can_fetch(AGENT, url):
                    raise SourceError("El sitio no permite esta descarga en robots.txt.")
            elif robots.status_code not in {404, 410}:
                raise SourceError("No se pudo verificar robots.txt; descarga aplazada.")
            with http.stream("GET", url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["location"])
                    continue
                if response.status_code != 200:
                    raise SourceError(f"PDF: HTTP {response.status_code}.")
                content = bytearray()
                for block in response.iter_bytes():
                    content.extend(block)
                    if len(content) > 25 * 1024 * 1024:
                        raise SourceError("PDF mayor que el límite local de 25 MB.")
                if not content.startswith(b"%PDF-"):
                    raise SourceError("La fuente no devolvió un PDF.")
                return bytes(content)
    raise SourceError("Demasiadas redirecciones al descargar PDF.")


def openalex(limit: int):
    cursor = "*"
    collected = 0
    while collected < limit:
        params = {"search": 'Polylepis NOT Chrysochromulina NOT Dendroaspis NOT Rhododendron NOT Telestes',
                  "per-page": min(100, limit - collected), "sort": "cited_by_count:desc",
                  "filter": "title.search:Polylepis,from_publication_date:1990-01-01,type:article|review|book-chapter|dissertation|report|book|preprint", "cursor": cursor}
        if settings.openalex_api_key:
            params["api_key"] = settings.openalex_api_key
        data = get_json("https://api.openalex.org/works", params)
        for raw in data.get("results", []):
            collected += 1
            title = raw.get("title") or ""
            abstract = reconstruct_abstract(raw.get("abstract_inverted_index"))
            if not relevant(title, abstract):
                continue
            primary = raw.get("primary_location") or {}
            locations = [primary, raw.get("best_oa_location") or {}] + (raw.get("locations") or [])
            licensed = next((loc for loc in locations if license_value(loc.get("license"))
                             and loc.get("pdf_url")), None)
            licensed = licensed or (primary if license_value(primary.get("license")) else {})
            # Only retain abstract if the primary version is explicitly licensed.
            abstract_ok = license_value(primary.get("license")) and licensed == primary
            yield {"source": "openalex", "external_id": raw["id"], "source_url": raw["id"],
                   "doi": doi_value(raw.get("doi")), "title": title,
                   "year": raw.get("publication_year"), "language": raw.get("language"),
                   "journal": (primary.get("source") or {}).get("display_name"),
                   "authors": [a["author"]["display_name"] for a in raw.get("authorships", [])],
                   "abstract": abstract if abstract_ok else None,
                   "license": license_value(licensed.get("license")),
                   "license_evidence": raw["id"] if licensed else None,
                   "pdf_url": licensed.get("pdf_url")}
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor or not data.get("results") or not settings.openalex_api_key:
            break
        time.sleep(0.5)


def crossref(limit: int):
    cursor = "*"
    collected = 0
    while collected < limit:
        params = {"query.title": "Polylepis", "rows": min(100, limit - collected),
                  "filter": "from-pub-date:1990-01-01", "cursor": cursor}
        if settings.contact_email:
            params["mailto"] = settings.contact_email
        data = get_json("https://api.crossref.org/works", params)["message"]
        for raw in data.get("items", []):
            collected += 1
            title = " ".join(raw.get("title", []))
            if not relevant(title):
                continue
            date = (raw.get("published") or {}).get("date-parts", [[None]])
            yield {"source": "crossref", "external_id": raw["DOI"].lower(),
                   "source_url": "https://doi.org/" + raw["DOI"],
                   "doi": doi_value(raw["DOI"]), "title": title, "year": date[0][0],
                   "authors": [" ".join(filter(None, [a.get("given"), a.get("family")]))
                               for a in raw.get("author", [])], "language": raw.get("language"),
                   "journal": "; ".join(raw.get("container-title", [])),
                   "abstract": None, "license": None, "license_evidence": None, "pdf_url": None}
        new_cursor = data.get("next-cursor")
        if not new_cursor or new_cursor == cursor or not data.get("items"):
            break
        cursor = new_cursor
        time.sleep(0.5)


def genus_key() -> int:
    match = get_json("https://api.gbif.org/v1/species/match", {"name": "Polylepis", "rank": "GENUS",
                                                              "kingdom": "Plantae", "strict": "true"})
    if match.get("matchType") != "EXACT" or match.get("rank") != "GENUS" or match.get("genus") != "Polylepis":
        raise SourceError("GBIF no devolvió una correspondencia exacta para el género Polylepis.")
    return int(match["usageKey"])


def gbif_records(limit: int, key: int):
    offset = 0
    while offset < limit:
        data = get_json("https://api.gbif.org/v1/occurrence/search", {
            "taxonKey": key, "hasCoordinate": "true", "hasGeospatialIssue": "false",
            "occurrenceStatus": "PRESENT", "limit": min(300, limit - offset), "offset": offset})
        yield from data.get("results", [])
        offset += len(data.get("results", []))
        if data.get("endOfRecords") or not data.get("results"):
            break
        time.sleep(0.3)
