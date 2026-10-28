import zipfile
import pandas as pd
from cleansheet.core import run

def test_pipeline_creates_bundle(tmp_path):
    source=tmp_path/"dirty.csv"
    pd.DataFrame({"Customer Name":[" Alice ","Bob","Bob","Carol"],"Amount":["$10.00","$20.00","$20.00","$30.00"],"Email":["a@example.com","b@example.com","b@example.com","c@example.com"]}).to_csv(source,index=False)
    bundle=tmp_path/"bundle.zip"; result=run(source,bundle)
    assert bundle.exists() and result["quality"]["score"]>=0
    with zipfile.ZipFile(bundle) as z:
        names=set(z.namelist())
        assert {"cleansheet_cleaned.csv","cleansheet_report.md","cleansheet_transformations.csv","cleansheet_pii_flags.csv","cleansheet_quality.json","cleansheet_dashboard.png"}<=names
        clean=pd.read_csv(z.open("cleansheet_cleaned.csv"))
        assert len(clean)==3 and clean["customer_name"].tolist()==["Alice","Bob","Carol"]
