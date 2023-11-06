from tehran_stocks.data.groups import IndustryGroup
import pytest


@pytest.mark.offline
def test_group():
    assert IndustryGroup.INDEX.value == "X1"
    assert IndustryGroup.INDEX.name == "INDEX"
    assert IndustryGroup.INDEX.farsi_name == "شاخص"
