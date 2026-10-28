import pandas as pd
from cleansheet.core import scan_pii

def test_email_detected():
    assert (scan_pii(pd.DataFrame({"contact":[f"user{i}@example.com" for i in range(20)]}))["pii_type"]=="email").any()

def test_phone_detected():
    assert (scan_pii(pd.DataFrame({"phone":["+1-555-123-4567"]*20}))["pii_type"]=="phone").any()

def test_ssn_detected():
    assert (scan_pii(pd.DataFrame({"ssn":["123-45-6789"]*20}))["pii_type"]=="ssn").any()

def test_clean_amounts_not_flagged():
    assert scan_pii(pd.DataFrame({"amount":[f"${i}.00" for i in range(20)]})).empty
