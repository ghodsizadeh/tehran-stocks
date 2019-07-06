from tehran_stocks import downloader

SAIPA = "44891482026867833"


class TestNames:
    def test_id_from_group(self):
        ids = downloader.get_stock_ids(34)
        assert ids

    def test_saipa_in_that(self):
        ids = downloader.get_stock_ids(34)

        assert SAIPA in ids

    def test_get_groups(self):
        groups = downloader.get_stock_groups()
        size = len(groups)
        assert size > 10


class TestStockDetail:
    def test_get_detail(self):
        data = downloader.get_stock_detail(SAIPA, 34)
        if isinstance(data, dict):
            assert data["code"] == SAIPA
        if isinstance(data, str):
            assert data == "exist"
