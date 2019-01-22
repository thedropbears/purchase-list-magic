import json
import re
import urllib.parse

import hug
import lxml.html
import requests

DOMAIN_TO_SUPPLIER_NAME = {
    "www.vexrobotics.com": "VEX Robotics",
    "au.rs-online.com": "RS Components",
    "www.ctr-electronics.com": "Cross the Road Electronics",
}

SUPPLIER_CURRENCY = {"www.ctr-electronics.com": "USD", "www.andymark.com": "USD"}


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
    if "currency" not in data and u.hostname in SUPPLIER_CURRENCY:
        data["currency"] = SUPPLIER_CURRENCY[u.hostname]

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


def do_vex(r: requests.Response) -> dict:
    data = scrape_jsonld(r)
    if not re.match(r"^\d{3}-\d{4}$", data.get("sku", "")):
        # page probably lists multiple parts
        data["has_aggregate"] = True
    return data


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


def scrape_bigcommerce(r: requests.Response) -> dict:
    return normalise_bc(find_bigcommerce_info(r.text))


def find_bigcommerce_info(page: str) -> dict:
    """Scrape a BigCommerce site page HTML for product info."""
    ...


def normalise_bc(data: dict) -> dict:
    ...


def scrape_workarea(r: requests.Response) -> dict:
    html = lxml.html.document_fromstring(r.text)
    product_containers = html.cssselect(".product-detail-container")
    assert len(product_containers) == 1
    product_container = product_containers[0]
    return json.loads(product_container.get("data-analytics"))["payload"]


def scrape_magento(r: requests.Response) -> dict:
    html = lxml.html.document_fromstring(r.text)
    product_views = html.cssselect(".product-view")
    assert len(product_views) == 1
    product_view = product_views[0]
    data = {
        "price": product_view.cssselect(".regular-price .price")[0].text.lstrip("$")
    }
    names = product_view.cssselect(".product-name h1 div")
    for name_el in names:
        if name_el.text.startswith("P/N: "):
            data["sku"] = name_el.text[5:]
        else:
            data["name"] = name_el.text
    return data


DOMAIN_TO_SITE_TYPE = {
    "www.vexrobotics.com": do_vex,
    "au.rs-online.com": scrape_jsonld,
    "www.ctr-electronics.com": scrape_magento,
    "www.andymark.com": scrape_workarea,
}
