import time, json, datetime, uuid

from bs4.element import Tag
from utils import is_url_root, link_of, url_spliter, list_counter, element_with_key , topics_ok
import crawl_utils
from text_process_utils import TextSimilarity
from concurrent.futures import ThreadPoolExecutor
import re
from hazm import *

class PageCard:
    def __init__(self, card_tag: Tag, root_url: str) -> None:
        self.tag = card_tag
        self.url = root_url

    def all_texted_links(self):
        return self.tag.find_all("a", href=True, text=True)

    def main_link_tag(self):
        main_h = self.tag.find("h2") or self.tag.find("h3") or self.tag.find("h4")
        a = main_h.find("a", href=True, text=True) if main_h else None
        return a

    def main_link_href(self):
        return link_of(self.main_link_tag(), self.url)

    def topic_link_tag(self):
        all_links = self.all_texted_links()
        all_except_main = [a for a in all_links if a.text != self.main_link_tag().text]
        if len(all_except_main) < 1 : return None
        return all_except_main[0]
    
    def topic_link_href(self):
        return link_of(self.topic_link_tag(), self.url)

    def __str__(self) -> str:
        ml = self.main_link_tag()
        return (
            ml.text
            + f"\n{self.main_link_href()}\n{self.topic_link_tag().text if self.topic_link_tag() else None}\n{self.topic_link_href()}"
            if ml
            else "No title"
        )

class ArticleTag:
    def __init__(self , soup) -> None:
        self.soup = soup
        # most_h2_el = sorted(soup.body.find_all('div') , key=lambda x : len(x.contents) ,reverse=True)[0]
        # print(most_h2_el.get('class' , most_h2_el.get('id' , most_h2_el)))
        self.tag = soup.find('article')

    def text(self) -> str:
        text = self.tag.text.strip() if self.tag else None
        return text

    def images(self, key: str = None):
        _all = self.tag.find_all("img")
        return element_with_key(_all, key)

    def headlines(self, key: str = None):
        _all = self.tag.find_all("h2")
        return element_with_key(_all, key)

    def a_tags(self):
        tags = [t for t in self.tag.find_all('a' , href=True) if '/' in t['href']]
        return tags

    def topics(self):
        nav = self.tag.find("ul") or self.soup.body.select('*[class*="breadcrumb"]')[0]
        print(nav)
        def name(n:str)->str:
            n = n.split(" ")
            bads = ['اخبار']
            ok = [w for w in n if w not in bads]
            return " ".join(ok)
        tags = [name(t.text) for t in nav.find_all('a' , href=True) if '/' in t['href']]
        if topics_ok(tags) : return tags
        else:
            # That was not a topics ul (go to topics_ok()) let's try els with breadcrumb contained class
            nav = self.soup.body.select('*[class*="breadcrumb"]')[0]
            tags = [name(t.text) for t in nav.find_all('a' , href=True) if '/' in t['href']]
            if topics_ok(tags) : return tags
            

    def save_locally(self , path : str = None):
        _path = path or (self.title + ".txt")
        with open(_path, mode="w", encoding="utf-8") as f:
            f.write(self.article_content())
        print("Article saved in "+ _path)

    def ok(self) -> bool:
        if self.tag is None:
            return False
        article_content_length_is_enough = len(self.text()) >= 350
        return article_content_length_is_enough
    

class WebPage:
    def __init__(
        self,
        url: str,
        topics: list = None
        # crawl_pages : bool = False
    ) -> None:
        is_first_site_page = False

        if is_url_root(url):
            is_first_site_page = True

        t1 = time.time()
        soup = crawl_utils.page_soup(url)
        if not is_first_site_page : self.article = ArticleTag(soup)
        title = soup.title.string
        meta_tag_description = (
            soup.find("meta", {"name": "description"})["content"].strip()
            if soup.find("meta", {"name": "description"})
            else None
        )
        crawl_time_in_seconds = round(time.time() - t1, 3)

        self.id = str(uuid.uuid4()).replace("-", "")
        self.topics = topics
        self.title = title
        self.meta_tag_description = meta_tag_description
        self.ready_title = title.split("-")[0].strip()
        self.url = url
        self.crawl_time_seconds = crawl_time_in_seconds
        self.is_first_site_page = is_first_site_page
        self.soup = soup
        self.crawled_date = datetime.datetime.now()
        self._children = []
        self.children_crawl_time_seconds = None

    def links(self):
        links = crawl_utils.all_links_of(self.soup, root_url=self.url)
        return links

    def just_links(self, limit: int = None):
        all_links = self.links() if limit is None else self.links()[0:limit]
        links = [link["href"] for link in all_links]
        return links
    
    def main_image(self) -> Tag:
        meta_og_img = self.soup.find("meta", {"property": "og:image"})
        if meta_og_img is not None:
            return meta_og_img

        all_images = self.all_images()
        ts = TextSimilarity()
        for img in all_images:
            img_alt = img.get("alt", "").strip()
            _title = self.main_h1().text if self.main_h1() else None or self.ready_title
            is_similar, similarity = ts.is_similar_to(img_alt, _title)
            self.img_alt_similarity_with_title = round(similarity * 100)
            if img_alt != "" and is_similar:
                return img

        return self.article.images()[0] if len(self.article.images()) > 0 else None


    def most_repeated_paths(self, length: int = 5):
        second_url_children = [
            url_spliter(url)[0]
            for url in self.just_links()
            if len(url_spliter(url)) > 0
        ]
        return list_counter(second_url_children)[:length]

    def all_images(self, key: str = None):
        _all = self.soup.find_all("img")
        return element_with_key(_all, key)

    def all_videos(self, key: str = None):
        _all = self.soup.find_all("video")
        return element_with_key(_all, key)
 
    def main_img_src(self):
        img = self.main_image()
        return img.get("src", img.get("content", ""))
    
    def main_h1(self) -> Tag:
        all_h1 = self.soup.find_all("h1")
        ts = TextSimilarity()
        for h1 in all_h1:
            h1_text = h1.text.strip() if h1 and h1.text else None
            if h1_text is not None:
                _title = self.ready_title
                is_similar, similarity = ts.is_similar_to(h1_text, _title)
                self.h1_similarity_with_title = round(similarity * 100)
                if is_similar:
                    return h1
        return None
    
    def page_root_name(self):
        meta_og_site_name = self.soup.find("meta", {"property": "og:site_name"})
        if (meta_og_site_name is not None) and (
            meta_og_site_name.get("content", None) is not None
        ):
            return meta_og_site_name["content"]

        title = self.title
        splited = (
            title.split("-")
            if "-" in title
            else title.split("|")
            if "|" in title
            else title.split(":")
            if ":" in title
            else title.split("،")
        )
        name = splited[1] if len(splited) >= 2 else None
        return name

    def page_keywords(self):
        all_links = self.soup.find_all("a", href=True)
        max_limit = 15

        result = []

        def ok(t: str):
            bad_words = "درباره ما1پیشنهاد1فرصت های شغلی1ثبت نام1ورود1وارد1نگاه1استخدام1آگهی1عضو1تبلیغات1تماشا1کاربر1خرید1بایگانی1تماس".split(
                "1"
            )
            for w in bad_words:
                if re.search(w, t):
                    return False
            length_con = len(t) >= 3 and len(t) <= max_limit
            return length_con

        for l in all_links:
            if l.text is not None:
                t = l.text.strip().replace("\n", "").replace("اخبار", "")
                if ok(t):
                    result.append(t)

        return set(result)

    def crawl_children(self, multithread: bool = True, limit: int = None):
        t1 = time.time()
        _links = self.just_links(limit=limit)
        if not multithread:
            self._children = [WebPage(link) for link in _links]
        else:

            def maper(url: str):
                page = WebPage(url)
                self._children.append(page)

            with ThreadPoolExecutor() as executor:
                executor.map(maper, _links)
        self.children_crawl_time_seconds = round(time.time() - t1, 3)

    def children(self, multithread: bool = True, limit: int = None) -> list:
        self.crawl_children(multithread=multithread, limit=limit)
        return self._children

    def json(self):
        main_img = self.main_image()
        main_img_src = main_img["src"] if main_img else None
        _dict = {
            "id": self.id,
            "url": self.url,
            "title": self.ready_title,
            "title_h1": self.main_h1().text,
            "links_count": len(self.just_links()),
            "img": [main_img_src] if main_img_src else None,
            "videos": self.all_videos(key="src"),
            "is_root_page": self.is_first_site_page,
            "crawl_time_seconds": self.crawl_time_seconds,
            "crawled_date": self.crawled_date,
            "img_alt_similarity_with_title": self.img_alt_similarity_with_title,
            "meta_tag_desc": self.meta_tag_description
            # "article_content": self.article_content(),
        }
        return json.dumps(_dict, indent=4, default=str)

    def title_keywords(self):
        t = time.time()
        title = self.main_h1().text
        tagger = POSTagger(model='resources/postagger.model')
        tags = tagger.tag(word_tokenize(title))
        print(tags)
        detect_time_seconds = round(time.time() - t , 3)
        print(detect_time_seconds)
        allowed = ['N', 'Ne' , 'AJ']
        return [t[0] for t in tags if t[1] in allowed] , detect_time_seconds


URL_zoomit = "https://www.zoomit.ir/"
URL_shahr = "https://www.shahrsakhtafzar.com/fa/"
URL_digiato = "https://digiato.com/"
URL_vigiato = "https://vigiato.net/"
page_zoomit = "https://www.zoomit.ir/tech-iran/372798-digikala-customers-corona-99/"
page_digiato = "https://digiato.com/article/2021/07/17/%d9%85%d9%85%d9%86%d9%88%d8%b9%db%8c%d8%aa-%d9%88%d8%a7%d8%b1%d8%af%d8%a7%d8%aa-%da%af%d9%88%d8%b4%db%8c%e2%80%8c%d9%87%d8%a7%db%8c-%d8%b4%db%8c%d8%a7%d8%a6%d9%88%d9%85%db%8c/"
page_shahr = "https://www.shahrsakhtafzar.com/fa/price-list/10386-powerbank-price-list"
page_dgmag = "https://www.digikala.com/mag/top-ghibli-studio-memorable-characters/"
URL_WITH_VIDEO = "https://www.zoomg.ir/game-articles/330159-xbox-series-x-games-spec-release-date-buy/"

p = WebPage(url=page_zoomit)
r = p.article.topics()
print(r)