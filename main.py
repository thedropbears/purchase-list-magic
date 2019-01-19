import json
import urllib.parse

import hug
import lxml.html
import requests

DOMAIN_TO_SUPPLIER_NAME = {
    "www.vexrobotics.com": "VEX Robotics",
}


@hug.cli()
@hug.get()
@hug.local()
def info_from(url: hug.types.text):
    u = urllib.parse.urlparse(url)
    if u.hostname not in DOMAIN_TO_SITE_TYPE:
        return

    r = requests.get(url)
    data = DOMAIN_TO_SITE_TYPE[u.hostname](r)
    if u.hostname in DOMAIN_TO_SUPPLIER_NAME:
        data["supplier"] = DOMAIN_TO_SUPPLIER_NAME[u.hostname]
    return data


def scrape_jsonld(r: requests.Response) -> dict:
    return normalise_jsonld(find_jsonld_product(r.text))


def find_jsonld_product(page: str) -> dict:
    """Find a schema.org/Product JSON-LD document from an HTML document."""
    html = lxml.html.document_fromstring(page)
    jsonld_docs = html.cssselect("script[type='application/ld+json']")
    for doc in jsonld_docs:
        doc = json.loads(doc.text)
        if doc.get("@type") == "Product":
            return doc


def normalise_jsonld(data: dict) -> dict:
    new_data = {}
    for key in ("name", "sku"):
        if key in data:
            new_data[key] = data[key]
    if "offers" in data:
        offers = data["offers"]
        if offers.get("@type") == "AggregateOffer":
            new_data["has_aggregate"] = True
        new_data["currency"] = offers.get("priceCurrency")
        new_data["price"] = offers.get("price")
    return new_data


def do_scrape_bigcommerce(r: requests.Response) -> dict:
    return normalise_bc(find_bigcommerce_info(r.text))


def find_bigcommerce_info(page: str) -> dict:
    """Scrape a BigCommerce site page HTML for product info."""
    ...


def normalise_bc(data: dict) -> dict:
    ...


DOMAIN_TO_SITE_TYPE = {
    "www.vexrobotics.com": scrape_jsonld,
}
