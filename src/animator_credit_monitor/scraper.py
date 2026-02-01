import logging
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

BASE_URL_BANGUMI = "https://bangumi.tv"
BASE_URL_SAKUGAWIKI = "https://w.atwiki.jp"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
}


class BangumiScraper:
    def __init__(self, request_interval: float = 2.0) -> None:
        self._interval = request_interval
        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)

    def fetch_works(self, person_id: str) -> list[dict]:
        """Fetch all works for a person from Bangumi, handling pagination."""
        all_works: list[dict] = []
        url: str | None = f"{BASE_URL_BANGUMI}/person/{person_id}/works"

        try:
            page = 1
            while url:
                if page > 1:
                    time.sleep(self._interval)

                logger.info("Fetching Bangumi page %d: %s", page, url)
                resp = self._session.get(url, timeout=30)
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding

                soup = BeautifulSoup(resp.text, "html.parser")
                works = self._parse_works(soup)
                all_works.extend(works)

                url = self._get_next_page_url(soup, person_id)
                page += 1

        except (requests.RequestException, ConnectionError) as e:
            logger.error("Failed to fetch Bangumi works: %s", e)
            return all_works if all_works else []

        return all_works

    def _parse_works(self, soup: BeautifulSoup) -> list[dict]:
        """Parse works from a single page."""
        works: list[dict] = []
        browser_list = soup.find("ul", class_="browserFull")
        if not browser_list:
            return works

        for item in browser_list.find_all("li", class_="item"):
            work = self._parse_item(item)
            if work:
                works.append(work)

        return works

    def _parse_item(self, item: Tag) -> dict | None:
        """Parse a single work item."""
        item_id = item.get("id", "")
        if isinstance(item_id, str):
            subject_id = item_id.replace("item_", "")
        else:
            return None

        inner = item.find("div", class_="inner")
        if not inner:
            return None

        title_tag = inner.find("h3")
        title_link = title_tag.find("a", class_="l") if title_tag else None
        title_cn = title_link.get_text(strip=True) if title_link else ""

        # Japanese title from <small> tag (falls back to Chinese title)
        small_tag = title_tag.find("small") if title_tag else None
        title = small_tag.get_text(strip=True) if small_tag else title_cn

        info_tag = inner.find("p", class_="info")
        info = info_tag.get_text(strip=True) if info_tag else ""

        role_tag = inner.find("span", class_="badge_job")
        role = role_tag.get_text(strip=True) if role_tag else ""

        return {
            "id": subject_id,
            "title": title,
            "title_cn": title_cn,
            "role": role,
            "info": info,
        }

    def _get_next_page_url(self, soup: BeautifulSoup, person_id: str) -> str | None:
        """Get the URL for the next page, if it exists."""
        pager = soup.find("div", class_="page_inner")
        if not pager:
            return None

        edge = pager.find("span", class_="p_edge")
        if not edge:
            return None

        match = re.search(r"\(\s*(\d+)\s*/\s*(\d+)\s*\)", edge.get_text())
        if not match:
            return None

        current_page = int(match.group(1))
        total_pages = int(match.group(2))

        if current_page >= total_pages:
            return None

        next_page = current_page + 1
        return f"{BASE_URL_BANGUMI}/person/{person_id}/works?sort=date&page={next_page}"


class SakugaWikiScraper:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(DEFAULT_HEADERS)

    def search(self, name: str) -> list[dict]:
        """Search for an animator on Sakuga@wiki."""
        url = f"{BASE_URL_SAKUGAWIKI}/sakuga/search"
        params = {"keyword": name}

        try:
            logger.info("Searching Sakuga@wiki for: %s", name)
            resp = self._session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding

            soup = BeautifulSoup(resp.text, "html.parser")
            return self._parse_search_results(soup)

        except (requests.RequestException, ConnectionError) as e:
            logger.error("Failed to search Sakuga@wiki: %s", e)
            return []

    def _parse_search_results(self, soup: BeautifulSoup) -> list[dict]:
        """Parse search results from Sakuga@wiki."""
        results: list[dict] = []
        search_list = soup.find("ul", class_="search-list")
        if not search_list:
            return results

        for li in search_list.find_all("li"):
            link = li.find("a")
            if not link:
                continue

            href = str(link.get("href", ""))
            full_url = urljoin(f"{BASE_URL_SAKUGAWIKI}/", href)
            title = link.get_text(strip=True)

            results.append({
                "title": title,
                "url": full_url,
            })

        return results


ANILIST_ROLE_MAP: dict[str, str] = {
    "Key Animation": "原画",
    "2nd Key Animation": "第二原画",
    "Animation Director": "作画監督",
    "Chief Animation Director": "総作画監督",
    "Assistant Animation Director": "作画監督補佐",
    "In-Between Animation": "動画",
    "Character Design": "キャラクターデザイン",
    "Sub Character Design": "サブキャラクターデザイン",
    "Director": "監督",
    "Episode Director": "演出",
    "Storyboard": "絵コンテ",
    "Design": "デザイン",
    "Action Animation Director": "アクション作画監督",
    "Mechanical Animation Director": "メカ作画監督",
    "Effects Animation": "エフェクト作画",
}

ANILIST_API_URL = "https://graphql.anilist.co"

ANILIST_QUERY = """
query ($search: String!) {
  Staff(search: $search) {
    id
    name {
      full
      native
    }
    staffMedia(sort: START_DATE_DESC, perPage: 25) {
      edges {
        staffRole
        node {
          id
          title {
            romaji
            native
          }
          startDate {
            year
            month
          }
        }
      }
    }
  }
}
"""


class AniListScraper:
    def fetch_works(self, name: str) -> list[dict]:
        """Fetch staff credits from AniList GraphQL API."""
        try:
            logger.info("Fetching AniList credits for: %s", name)
            resp = requests.post(
                ANILIST_API_URL,
                json={"query": ANILIST_QUERY, "variables": {"search": name}},
                timeout=30,
            )
            resp.raise_for_status()

            data = resp.json()
            staff = data.get("data", {}).get("Staff")
            if not staff:
                logger.warning("No staff found on AniList for: %s", name)
                return []

            return self._parse_edges(staff["staffMedia"]["edges"])

        except (requests.RequestException, ConnectionError) as e:
            logger.error("Failed to fetch AniList credits: %s", e)
            return []

    def _parse_edges(self, edges: list[dict]) -> list[dict]:
        """Parse staff media edges into a flat list."""
        results: list[dict] = []
        for edge in edges:
            node = edge.get("node", {})
            title_data = node.get("title", {})
            start_date = node.get("startDate", {})

            year = start_date.get("year")
            month = start_date.get("month")
            date = f"{year}-{month:02d}" if year and month else ""

            results.append({
                "id": str(node.get("id", "")),
                "title": title_data.get("native", "") or title_data.get("romaji", ""),
                "title_romaji": title_data.get("romaji", ""),
                "role": self._translate_role(edge.get("staffRole", "")),
                "date": date,
            })

        return results

    @staticmethod
    def _translate_role(role: str) -> str:
        """Translate AniList English role name to Japanese."""
        if not role:
            return role

        match = re.match(r"^(.+?)\s*(\(.+\))$", role)
        if match:
            base, suffix = match.group(1), match.group(2)
            translated = ANILIST_ROLE_MAP.get(base, base)
            return f"{translated} {suffix}"

        return ANILIST_ROLE_MAP.get(role, role)
