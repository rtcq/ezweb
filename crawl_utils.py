import requests
from bs4 import BeautifulSoup
from exceptions import RequestBadStatusCode
from utils import link_of

def safe_get(url: str) -> requests.Response:
    response = requests.get(url)
    if response.status_code != 200:
        raise RequestBadStatusCode(url, response)
    return response


def page_soup(response: requests.Response) -> BeautifulSoup:
    soup = BeautifulSoup(response.text, features="html.parser")
    return soup


def all_links_of(soup: BeautifulSoup, root_url: str, mode: bool = "dict") -> list:
    if root_url[-1] == "/":
        root_url = root_url[0:-1]
    a_tags = soup.find_all("a", href=True)

    links = []
    if mode == "dict":
        links = [
            {"title": a_tag.text, "href": link_of(a_tag, root_url)} for a_tag in a_tags
        ]
    else:
        links = [link_of(a_tag, root_url) for a_tag in a_tags]
    return links