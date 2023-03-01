import json
import math
import re
import unicodedata
import urllib
from typing import List
from urllib.request import urlopen

import pandas
import requests
from bs4 import BeautifulSoup


def scrape_categories(landing_page, categories_page) -> List[str]:
    """
    Parses the categories within each store, in order to get the links to all categories.

    Parameters:
        landing_page (Literal): Indicates the landing page of a particular store.
        categories_page (Literal): Indicates the categories page within the website.

    Returns:
        TODO
    """
    categories = []
    response = requests.get(categories_page)
    soup = BeautifulSoup(response.text, "html.parser")
    ul_mainNav = soup.find("ul", {"class": "mainNav_ul"})
    lis = ul_mainNav.find_all("li")

    for li in lis:
        ul_mainNav_sub = li.find("ul", {"class": "mainNav_sub"})
        if ul_mainNav_sub:
            a_tags = ul_mainNav_sub.find_all("a")
            for a in a_tags:
                categories.append(landing_page + a["href"])
    return categories


def scrape_products(prefix, category, products):
    """
    Iterates all pages within a category, necessary due to pagination.
    Breaks when there are no more product links provided.

    Parameters:
        prefix (Literal): The category url that contains all objects that will be scraped for data.
        category (str): A particular category that will be parsed for all its products' data to be scraped.
        products (Queue): A queue to temporarily hold the data, because of thread locking.
    """

    i = 1
    has_products = True

    while has_products:
        response = requests.get(category + f"?pg={i}")
        soup = BeautifulSoup(response.content, "html.parser")
        products_list = soup.find_all("div", class_=re.compile("^product prGa_"))

        if not products_list:
            has_products = False
            continue

        for product in products_list:
            scrape_data(prefix, products, product)

        i += 1


def scrape_data(prefix, products, product):
    """
    Scrapes product link, name, flat price and price per unit.

    Parameters:
        prefix (Literal): The prefix to add to the url for each particular product.
        products (Queue): A queue to temporarily hold the data, because of thread locking.
        product (BeautifulSoup): A particular product's soup variable, to extract the data from.
    """

    if "sklavenitis" in prefix:
        shop = "Σκλαβενίτης"
    elif "mymarket" in prefix:
        shop = "My Market"
    else:
        shop = "ΑΒ Βασιλόπουλος"

    element = product.find("a", class_="absLink")["href"]
    if element:
        link = prefix + element

    element = product.find("h4", class_="product__title")
    if element:
        d = {ord("\N{COMBINING ACUTE ACCENT}"): None}
        product_name = unicodedata.normalize("NFD", element.text).upper().translate(d)

    element = product.find("div", class_="price")
    if element:
        flat_price = element.text

    element = product.find("div", class_="hightlight")
    if element:
        price_per_unit = element.text
    else:
        element = product.find("div", class_="priceKil")
        if element and element.text.strip():
            price_per_unit = element.text
        else:
            price_per_unit = flat_price

    new_row = {"shop": shop, "link": link, "product_name": product_name, "flat_price": flat_price.strip(), "price_per_unit": price_per_unit.strip()}
    products.put(new_row)


def scrape_categories_ab(url):
    """
    Parses the categories within each store, in order to get the links to all categories.

    Parameters:
        landing_page (Literal): Indicates the landing page of a particular store.

    Returns:
        TODO
    """

    categories = pandas.DataFrame(columns=["category", "pages"])
    ignore_list = ["Νέα Προϊόντα", "Καλάθι", "κατοικίδια", "μωρό", "Προσφορές"]
    response = urlopen(url)
    data_json = json.loads(response.read())
    data = [item for item in data_json["data"]["leftHandNavigationBar"]["levelInfo"] if not any(word in item.get("name") for word in ignore_list)]

    for entry in data:
        categories.loc[len(categories)] = [entry["code"], math.ceil(entry["productCount"] / 50)]

    return categories


def scrape_products_ab(landing_page, url, products, exceptions):
    """
    Iterates all pages within a category, necessary due to pagination.
    Breaks when there are no more product links provided.

    Parameters:
        url (str): The category url that will be parsed for all its products' data to be scraped.
        products (Queue): A queue to temporarily hold the data, because of thread locking.
    """
    try:
        response = urlopen(url)
        data_json = json.loads(response.read())
        data = [item for item in data_json["data"]["categoryProductSearch"]["products"]]

        for entry in data:
            if entry["price"]["discountedPriceFormatted"] != entry["price"]["unitPriceFormatted"]:
                price_per_unit = entry["price"]["discountedUnitPriceFormatted"]
            else:
                price_per_unit = entry["price"]["supplementaryPriceLabel1"]

            new_row = {
                "shop": "ΑΒ Βασιλόπουλος",
                "link": landing_page + entry["url"],
                "product_name": entry["name"],
                "flat_price": entry["price"]["discountedPriceFormatted"].strip(),
                "price_per_unit": price_per_unit,
            }
            products.put(new_row)
    except urllib.error.URLError as e:
        exceptions.append(url)


def scrape_product_exceptions_ab_recursive(url_list, products, exceptions):
    exceptions_new = []
    for url in url_list:
        try:
            scrape_products_ab("https://www.ab.gr", url, products, exceptions_new)
        except (urllib.error.URLError, KeyError):
            exceptions.append(url)

    if exceptions_new:
        scrape_product_exceptions_ab_recursive(exceptions_new, products, exceptions)
