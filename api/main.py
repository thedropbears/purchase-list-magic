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
    "core-electronics.com.au": "Core Electronics",
    "www.bunnings.com.au": "Bunnings",
    "www.digikey.com": "Digi-Key",
    "www.digikey.com.au": "Digi-Key Australia",
    "www.revrobotics.com": "REV Robotics",
}
SUPPLIERS_INC_GST = {"Core Electronics"}
SUPPLIER_CURRENCY = {"www.ctr-electronics.com": "USD", "www.andymark.com": "USD"}

sesh = requests.Session()
sesh.headers["User-Agent"] = "https://github.com/thedropbears/purchase-list-magic"


@hug.cli()
@hug.get()
@hug.local()
def info_from(url: hug.types.text):
    u = urllib.parse.urlparse(url)

    if u.hostname in DOMAIN_TO_SITE_TYPE:
        r = sesh.get(url)
        data = DOMAIN_TO_SITE_TYPE[u.hostname](r)
    else:
        return  # TODO battle test below
        # try all the generic things
        r = sesh.get(url)
        jsonld = find_jsonld_product(r.text)
        if jsonld is not None:
            data = normalise_jsonld(jsonld)
        else:
            data = scrape_html_schema(r)
            if data is None:
                return

    if u.hostname in DOMAIN_TO_SUPPLIER_NAME:
        data["supplier"] = DOMAIN_TO_SUPPLIER_NAME[u.hostname]
    if "currency" not in data and u.hostname in SUPPLIER_CURRENCY:
        data["currency"] = SUPPLIER_CURRENCY[u.hostname]
    if data.get("supplier") in SUPPLIERS_INC_GST:
        data["inc_gst"] = True

    return data


def scrape_jsonld(r: requests.Response) -> dict:
    return normalise_jsonld(find_jsonld_product(r.text))


def find_jsonld_product(page: str) -> dict:
    """Find a schema.org/Product JSON-LD document from an HTML document."""
    html = lxml.html.document_fromstring(page)
    jsonld_docs = html.cssselect("script[type='application/ld+json']")
    for doc in jsonld_docs:
        doc = json.loads(doc.text.rstrip().rstrip(";"))  # some websites don't know what JSON is
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
        if "seller" in offers:
            new_data["supplier"] = offers["seller"]["name"]
    return new_data


def scrape_html_schema(r: requests.Response) -> dict:
    """Try to find a schema.org/Product in the HTML."""
    html = lxml.html.document_fromstring(r.text)
    for selector in (
        "[itemtype='http://schema.org/Product'][itemprop='mainEntity']",
        "[itemtype='http://schema.org/Product']",
    ):
        products = html.cssselect(selector)
        if len(products) == 1:
            return find_schema_info(products[0])


def find_schema_info(prod: lxml.etree.ElementBase) -> dict:
    """Given a schema.org/Product HTML element, try to grab relevant info."""
    # why did I ever choose this life

    data = {}

    sku_els = prod.cssselect("[itemprop='sku']")
    if len(sku_els) == 1:
        data["sku"] = sku_els[0].get("content")
    else:
        prodid_els = prod.cssselect("[itemprop='productID']")
        if len(prodid_els) == 1:
            prodid = prodid_els[0].get("content")
            if prodid.startswith("sku:"):
                data["sku"] = prodid[4:]

    # Bunnings slightly screwed up the schema URI
    offers_els = prod.cssselect("[itemprop='offers'][itemtype$='//schema.org/Offer']")
    if len(offers_els) == 1:
        offers = offers_els[0]

        price_els = offers.cssselect("[itemprop='price']")
        if len(price_els) == 1:
            data["price"] = price_els[0].get("content") or price_els[0].text

        currency_els = offers.cssselect("[itemprop='priceCurrency']")
        if len(currency_els) == 1:
            data["currency"] = currency_els[0].get("content") or currency_els[0].text

    if "price" not in data:
        # try a bit harder
        price_els = prod.cssselect("[itemprop='price']")
        if len(price_els) == 1:
            data["price"] = price_els[0].get("content") or price_els[0].text

    # TODO find the name better - exclude children of other itemprops/itemscopes
    for selector in ("h1[itemprop='name']", "[itemprop='name']"):
        name_els = prod.cssselect(selector)
        if len(name_els) == 1:
            name = name_els[0].text
            if name:
                data["name"] = name
            break

    return data


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
    "www.banggood.com": scrape_jsonld,
    "www.littlebird.com.au": scrape_jsonld,
    "au.rs-online.com": scrape_jsonld,
    "www.vexrobotics.com": do_vex,
    "www.ctr-electronics.com": scrape_magento,
    "www.andymark.com": scrape_workarea,
    "www.bunnings.com.au": scrape_html_schema,
    "core-electronics.com.au": scrape_html_schema,
    "www.digikey.com": scrape_html_schema,
    "www.digikey.com.au": scrape_html_schema,
    "www.revrobotics.com": scrape_html_schema,
}
