from pathlib import Path

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
        assert works[0]["title_cn"] == "测试作品A"
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
    def test_Bangumi日本語タイトルがない場合は中国語タイトルにフォールバックする(self) -> None:
        html = (FIXTURES_DIR / "bangumi_works.html").read_text()
        responses.add(
            responses.GET,
            "https://bangumi.tv/person/12345/works",
            body=html,
            status=200,
        )

        scraper = BangumiScraper(request_interval=0)
        works = scraper.fetch_works("12345")

        # 3件目はsmallタグなし → 中国語タイトルがtitleに入る
        assert works[2]["title"] == "测试作品C"
        assert works[2]["title_cn"] == "测试作品C"

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


class TestAniListScraper:
    @responses.activate
    def test_AniListスタッフ検索で作品リストを取得できる(self) -> None:
        api_response = {
            "data": {
                "Staff": {
                    "id": 12345,
                    "name": {"full": "Test Animator", "native": "テストアニメーター"},
                    "staffMedia": {
                        "edges": [
                            {
                                "staffRole": "Key Animation (ep 1)",
                                "node": {
                                    "id": 100,
                                    "title": {"romaji": "Test Anime A", "native": "テスト作品A"},
                                    "startDate": {"year": 2026, "month": 1},
                                },
                            },
                            {
                                "staffRole": "2nd Key Animation",
                                "node": {
                                    "id": 200,
                                    "title": {"romaji": "Test Anime B", "native": "テスト作品B"},
                                    "startDate": {"year": 2025, "month": 10},
                                },
                            },
                        ]
                    },
                }
            }
        }
        responses.add(
            responses.POST,
            "https://graphql.anilist.co",
            json=api_response,
            status=200,
        )

        from animator_credit_monitor.scraper import AniListScraper
        scraper = AniListScraper()
        results = scraper.fetch_works("テストアニメーター")

        assert len(results) == 2
        assert results[0]["title"] == "テスト作品A"
        assert results[0]["title_romaji"] == "Test Anime A"
        assert results[0]["role"] == "Key Animation (ep 1)"
        assert results[0]["id"] == "100"
        assert results[0]["date"] == "2026-01"

    @responses.activate
    def test_AniListでスタッフが見つからない場合は空リストを返す(self) -> None:
        api_response = {"data": {"Staff": None}}
        responses.add(
            responses.POST,
            "https://graphql.anilist.co",
            json=api_response,
            status=200,
        )

        from animator_credit_monitor.scraper import AniListScraper
        scraper = AniListScraper()
        results = scraper.fetch_works("存在しない人")

        assert results == []

    @responses.activate
    def test_AniListで接続エラー時に空リストを返す(self) -> None:
        responses.add(
            responses.POST,
            "https://graphql.anilist.co",
            body=ConnectionError("Connection refused"),
        )

        from animator_credit_monitor.scraper import AniListScraper
        scraper = AniListScraper()
        results = scraper.fetch_works("テスト")

        assert results == []
