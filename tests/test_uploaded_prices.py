import pytest

from modeling.uploaded_prices import prepare_uploaded_2022_prices


GOLD = b"Date,USD (PM)\n2022-01-07,1800\n2022-01-10,1810\n"
BTC = b"Date,Value\n2022-01-07,40000\n2022-01-08,40100\n2022-01-09,40200\n2022-01-10,40300\n"


def test_aligns_gold_market_closures_without_forward_looking_fill():
    result = prepare_uploaded_2022_prices(GOLD, BTC)
    assert len(result.bars) == 4
    assert [b.gold for b in result.bars] == [1800, None, None, 1810]
    assert result.bars[1].weekday == 5
    assert result.source == "uploaded_2022_mcm_c_csv"
    assert len(result.gold_sha256) == 64


@pytest.mark.parametrize("gold,btc", [
    (GOLD, b"Date,Value\n2022-01-07,40000\n2022-01-07,40100\n"),
    (GOLD, b"Date,Value\n2022-01-07,-1\n"),
    (b"Date,USD (PM)\n2022-01-07,\n", BTC),
    (b"Date,USD (PM)\n2022-01-07,0\n", BTC),
])
def test_rejects_ambiguous_or_invalid_market_data(gold, btc):
    with pytest.raises(ValueError):
        prepare_uploaded_2022_prices(gold, btc)


def test_first_bitcoin_date_precedes_first_gold_quote_without_future_fill():
    btc = b"Date,Value\n2022-01-06,40000\n2022-01-07,40100\n"
    output = prepare_uploaded_2022_prices(GOLD, btc)
    assert output.bars[0].gold is None
    assert output.bars[1].gold == 1800
