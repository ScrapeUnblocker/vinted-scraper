"""Vinted country sites ("markets") and item conditions.

Vinted runs one site per country. Each has its own catalogue, currency and
interface language, and they all share the same page layout, so one parser
covers every market. Requests are routed through the market's own country.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Market:
    """One Vinted country site."""

    code: str
    domain: str
    country: str
    currency: str
    language: str

    @property
    def base_url(self) -> str:
        return f"https://www.{self.domain}"


_MARKETS = (
    Market("fr", "vinted.fr", "FR", "EUR", "fr"),
    Market("be", "vinted.be", "BE", "EUR", "fr"),
    Market("lu", "vinted.lu", "LU", "EUR", "fr"),
    Market("nl", "vinted.nl", "NL", "EUR", "nl"),
    Market("de", "vinted.de", "DE", "EUR", "de"),
    Market("at", "vinted.at", "AT", "EUR", "de"),
    Market("it", "vinted.it", "IT", "EUR", "it"),
    Market("es", "vinted.es", "ES", "EUR", "es"),
    Market("pt", "vinted.pt", "PT", "EUR", "pt"),
    Market("uk", "vinted.co.uk", "GB", "GBP", "en"),
    Market("ie", "vinted.ie", "IE", "EUR", "en"),
    Market("us", "vinted.com", "US", "USD", "en"),
    Market("pl", "vinted.pl", "PL", "PLN", "pl"),
    Market("lt", "vinted.lt", "LT", "EUR", "lt"),
    Market("cz", "vinted.cz", "CZ", "CZK", "cs"),
    Market("sk", "vinted.sk", "SK", "EUR", "sk"),
    Market("hu", "vinted.hu", "HU", "HUF", "hu"),
    Market("ro", "vinted.ro", "RO", "RON", "ro"),
    Market("se", "vinted.se", "SE", "SEK", "sv"),
    Market("dk", "vinted.dk", "DK", "DKK", "da"),
    Market("fi", "vinted.fi", "FI", "EUR", "fi"),
    Market("gr", "vinted.gr", "GR", "EUR", "el"),
    Market("hr", "vinted.hr", "HR", "EUR", "hr"),
)

#: Every supported market, keyed by its short code.
MARKETS: dict[str, Market] = {m.code: m for m in _MARKETS}

DEFAULT_MARKET = "fr"

_ALIASES = {"gb": "uk", "co.uk": "uk", "com": "us", "cs": "cz"}
_BY_DOMAIN = {m.domain: m for m in _MARKETS}


def get_market(value: str | Market) -> Market:
    """Resolve a market from a code (``fr``, ``uk``, ``gb``), a domain
    (``vinted.co.uk``) or a full Vinted URL.

    Raises:
        ValueError: The value does not name a Vinted market.
    """
    if isinstance(value, Market):
        return value
    text = str(value).strip().lower()
    if "/" in text:
        text = urlsplit(text if "://" in text else f"https://{text}").netloc
    if text.startswith("www."):
        text = text[4:]
    if text in _BY_DOMAIN:
        return _BY_DOMAIN[text]
    if text.startswith("vinted."):
        text = text[len("vinted.") :]
    text = _ALIASES.get(text, text)
    if text in MARKETS:
        return MARKETS[text]
    raise ValueError(f"unknown Vinted market {value!r}; choose one of: {', '.join(MARKETS)}")


def market_from_url(url: str) -> Market | None:
    """The market a Vinted URL belongs to, or ``None`` for a non-Vinted URL."""
    host = urlsplit(url if "://" in url else f"https://{url}").netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return _BY_DOMAIN.get(host)


# --------------------------------------------------------------------------- #
# Item conditions
# --------------------------------------------------------------------------- #

#: Vinted's condition filter IDs (the ``status_ids[]`` URL parameter).
CONDITIONS: dict[str, int] = {
    "new_with_tags": 6,
    "new_without_tags": 1,
    "very_good": 2,
    "good": 3,
    "satisfactory": 4,
}

# The label Vinted prints on each listing, per interface language. Labels for
# en/fr/de/it/es/nl/pl were matched against the status filter; the rest are the
# labels the other country sites print.
_CONDITION_LABELS: dict[str, tuple[str, ...]] = {
    "new_with_tags": (
        "New with tags",
        "Neuf avec étiquette",
        "Neu, mit Etikett",
        "Nuovo con cartellino",
        "Nuevo con etiquetas",
        "Nieuw met prijskaartje",
        "Nowy z metką",
        "Novo com etiquetas",
        "Nauja su etiketėmis",
        "Nový s visačkou",
        "Nové s visačkou",
        "Új, címkékkel",
        "Nou cu etichetă",
        "Ny med prislapp",
        "Ny med prismærker",
        "Uusi, jossa hintalappu",
        "Νέο με ετικέτες",
        "Novo s etiketama",
    ),
    "new_without_tags": (
        "New without tags",
        "Neuf sans étiquette",
        "Neu",
        "Nuovo senza cartellino",
        "Nuevo sin etiquetas",
        "Nieuw zonder prijskaartje",
        "Nowy bez metki",
        "Novo sem etiquetas",
        "Nauja be etikečių",
        "Nový bez visačky",
        "Nové bez visačky",
        "Új, címkék nélkül",
        "Nou fără etichetă",
        "Ny utan prislapp",
        "Ny uden prismærker",
        "Uusi ilman hintalappua",
        "Νέο χωρίς ετικέτες",
        "Novo bez etiketa",
    ),
    "very_good": (
        "Very good",
        "Très bon état",
        "Sehr gut",
        "Ottime",
        "Muy bueno",
        "Heel goed",
        "Bardzo dobry",
        "Muito bom",
        "Labai gera",
        "Velmi dobrý",
        "Veľmi dobré",
        "Kiváló",
        "Foarte bună",
        "Mycket bra",
        "Meget god",
        "Erittäin hyvä",
        "Πολύ καλό",
        "Veoma dobro",
    ),
    "good": (
        "Good",
        "Bon état",
        "Gut",
        "Buone",
        "Bueno",
        "Goed",
        "Dobry",
        "Bom",
        "Gera",
        "Dobrý",
        "Dobré",
        "Jó",
        "Bună",
        "Bra",
        "God",
        "Hyvä",
        "Καλό",
        "Dobro",
    ),
    "satisfactory": (
        "Satisfactory",
        "Satisfaisant",
        "Zufriedenstellend",
        "Discrete",
        "Satisfactorio",
        "Veelgebruikt",
        "Zadowalający",
        "Satisfatório",
        "Patenkinama",
        "Kielégítő",
        "Satisfăcătoare",
    ),
}

_LABEL_TO_CODE = {
    label.casefold(): code for code, labels in _CONDITION_LABELS.items() for label in labels
}


def condition_code(label: str | None) -> str | None:
    """Map a localized condition label (``"Très bon état"``) to a code
    (``"very_good"``). Returns ``None`` for labels it does not know."""
    if not label:
        return None
    return _LABEL_TO_CODE.get(" ".join(label.split()).casefold())


def condition_ids(conditions: str | list[str] | tuple[str, ...] | None) -> list[int]:
    """Turn condition names (``"very_good"``, ``"new"``, ``"good,very_good"``)
    or raw IDs into Vinted ``status_ids``. ``"new"`` means both "new" conditions.

    Raises:
        ValueError: A name is not a known condition.
    """
    if not conditions:
        return []
    if isinstance(conditions, str):
        conditions = [conditions]
    ids: list[int] = []
    for raw in conditions:
        for part in str(raw).split(","):
            name = part.strip().lower().replace("-", "_").replace(" ", "_")
            if not name:
                continue
            if name == "new":
                found = [CONDITIONS["new_with_tags"], CONDITIONS["new_without_tags"]]
            elif name.isdigit():
                found = [int(name)]
            elif name in CONDITIONS:
                found = [CONDITIONS[name]]
            else:
                choices = ", ".join(["new", *CONDITIONS])
                raise ValueError(f"unknown condition {part.strip()!r}; choose from: {choices}")
            ids.extend(i for i in found if i not in ids)
    return ids
