import pandas as pd
from cleansheet.core import maybe_coerce_datetime

def test_plain_integers_not_dates():
    assert maybe_coerce_datetime(pd.Series(["1","2","3"]),"v",[]).dtype==object

def test_sku_not_dates():
    values=["SKU-12-34-5678","SKU-12-34-5679","SKU-12-34-5680"]
    assert maybe_coerce_datetime(pd.Series(values),"v",[]).dtype==object

def test_real_dates_parse():
    out=maybe_coerce_datetime(pd.Series(["2024-01-15","2024-01-16","2024-01-17"]),"date",[])
    assert pd.api.types.is_datetime64_any_dtype(out)
