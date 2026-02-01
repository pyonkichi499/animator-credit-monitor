from pathlib import Path

import pytest
import responses

from animator_credit_monitor.scraper import BangumiScraper, SakugaWikiScraper

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestBangumiScraper:
    @responses.activate
    def test_Bangumi作品リストをパースできる(self) -> None:
        html = (FIXTURES_DIR / "bangumi_works.html").read_text()
        responses.add(
            responses.GET,
            "https://bangumi.tv/person/12345/works",
            body=html,
            status=200,
        )

        scraper = BangumiScraper(request_interval=0)
        works = scraper.fetch_works("12345")

        assert len(works) == 3
        assert works[0]["id"] == "100001"
        assert works[0]["title"] == "テスト作品A"
        assert works[0]["role"] == "原画"
        assert works[0]["info"] == "2026-01 / テストスタジオ"

    @responses.activate
    def test_Bangumiページネーションを全ページ取得できる(self) -> None:
        page1_html = (FIXTURES_DIR / "bangumi_works.html").read_text()
        # Modify page1 to have pagination link to page 2
        page1_html = page1_html.replace(
            '<span class="p_edge">( 1 / 1 )</span>',
            '<a class="p" href="?sort=date&amp;page=2">2</a>'
            '<span class="p_edge">( 1 / 2 )</span>',
        )
        page2_html = (FIXTURES_DIR / "bangumi_works_page2.html").read_text()

        responses.add(
            responses.GET,
            "https://bangumi.tv/person/12345/works",
            body=page1_html,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://bangumi.tv/person/12345/works",
            body=page2_html,
            status=200,
        )

        scraper = BangumiScraper(request_interval=0)
        works = scraper.fetch_works("12345")

        assert len(works) == 4
        assert works[3]["id"] == "200001"
        assert works[3]["title"] == "テスト作品D"

    @responses.activate
    def test_BangumiでHTTPエラー時に空リストを返す(self) -> None:
        responses.add(
            responses.GET,
            "https://bangumi.tv/person/99999/works",
            status=404,
        )

        scraper = BangumiScraper(request_interval=0)
        works = scraper.fetch_works("99999")

        assert works == []

    @responses.activate
    def test_Bangumiで接続エラー時に空リストを返す(self) -> None:
        responses.add(
            responses.GET,
            "https://bangumi.tv/person/12345/works",
            body=ConnectionError("Connection refused"),
        )

        scraper = BangumiScraper(request_interval=0)
        works = scraper.fetch_works("12345")

        assert works == []


class TestSakugaWikiScraper:
    @responses.activate
    def test_作画wiki検索結果をパースできる(self) -> None:
        html = (FIXTURES_DIR / "sakugawiki_search.html").read_text()
        responses.add(
            responses.GET,
            "https://w.atwiki.jp/sakuga/search",
            body=html,
            status=200,
        )

        scraper = SakugaWikiScraper()
        results = scraper.search("テストアニメーター")

        assert len(results) == 3
        assert results[0]["title"] == "テスト作品A（TV）"
        assert results[0]["url"] == "https://w.atwiki.jp/sakuga/pages/101.html"

    @responses.activate
    def test_作画wikiで403エラー時に空リストを返す(self) -> None:
        responses.add(
            responses.GET,
            "https://w.atwiki.jp/sakuga/search",
            status=403,
        )

        scraper = SakugaWikiScraper()
        results = scraper.search("テスト")

        assert results == []

    @responses.activate
    def test_作画wikiで接続エラー時に空リストを返す(self) -> None:
        responses.add(
            responses.GET,
            "https://w.atwiki.jp/sakuga/search",
            body=ConnectionError("Connection refused"),
        )

        scraper = SakugaWikiScraper()
        results = scraper.search("テスト")

        assert results == []
