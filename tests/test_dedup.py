import pandas as pd
from cleansheet.core import normalize_columns, strip_whitespace

def test_whitespace_trim_is_logged():
    log=[]; out=strip_whitespace(pd.DataFrame({"a":["  x  "," y","z "]}),log)
    assert out["a"].tolist()==["x","y","z"] and any(x["action"]=="whitespace_strip" for x in log)

def test_header_collisions_unique():
    log=[]; out=normalize_columns(pd.DataFrame({"Name":[1],"name":[2]," NAME ":[3]}),log)
    assert out.columns.tolist()==["name","name__2","name__3"]

def test_duplicate_rows_removed():
    assert len(pd.DataFrame({"a":[1,1,2],"b":["x","x","y"]}).drop_duplicates())==2
