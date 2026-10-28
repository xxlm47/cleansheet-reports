import pandas as pd
from cleansheet.core import maybe_coerce_numeric

def parse(values):
    log = []
    return maybe_coerce_numeric(pd.Series(values), "value", log), log

def test_currency_and_us_grouping():
    out, log = parse(["$1,200.50", "$250.00", "$99.99"])
    assert out.tolist() == [1200.5, 250.0, 99.99]
    assert log[0]["action"] == "numeric_coerce"

def test_names_are_not_coerced():
    values = ["Smith, John 123", "Doe, Jane 456", "Roe, Rick 789"]
    out, log = parse(values)
    assert out.astype(str).tolist() == values
    assert not pd.api.types.is_numeric_dtype(out)
    assert not any(x["action"] == "numeric_coerce" for x in log)

def test_units_remain_text():
    values = ["1,234 kg", "2,345 kg", "3,456 kg"]
    out, _ = parse(values)
    assert out.astype(str).tolist() == values
    assert not pd.api.types.is_numeric_dtype(out)

def test_accounting_negatives():
    out, _ = parse(["(1,200)", "(50.25)", "100"])
    assert out.tolist() == [-1200.0, -50.25, 100.0]

def test_eu_decimal():
    out, _ = parse(["1.234,56", "2.345,67", "10.000,00"])
    assert out.tolist() == [1234.56, 2345.67, 10000.0]
