"""Core local data-cleaning and analytics pipeline."""
from __future__ import annotations
import json, re, tempfile, zipfile
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

NUMERIC_PARSE_THRESHOLD = 0.90
DATE_PARSE_THRESHOLD = 0.90
PII_SAMPLE_SIZE = 500
PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?<!\d)(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

def load_data(path):
    p = Path(path)
    if not p.is_file(): raise FileNotFoundError(f"Input file not found: {p}")
    if p.suffix.lower() == ".csv":
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try: return pd.read_csv(p, encoding=enc, low_memory=False)
            except UnicodeDecodeError: pass
        raise ValueError("Could not decode CSV.")
    if p.suffix.lower() in {".xlsx", ".xls"}: return pd.read_excel(p)
    raise ValueError(f"Unsupported file type: {p.suffix}. Use CSV, XLSX, or XLS.")

def normalize_columns(df, log):
    seen, cols = {}, []
    for old in df.columns:
        base = re.sub(r"[^\w]+", "_", str(old).strip().lower()).strip("_") or "col"
        n = seen.get(base, 0) + 1; seen[base] = n
        new = base if n == 1 else f"{base}__{n}"
        if new != str(old):
            log.append({"column": str(old), "action": "column_rename", "detail": f"renamed to '{new}'", "values_affected": 0})
        cols.append(new)
    out = df.copy(); out.columns = cols
    return out

def strip_whitespace(df, log):
    out = df.copy()
    for col in out.columns:
        if not (pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col])): continue
        before = out[col]
        after = before.map(lambda x: x.strip() if isinstance(x, str) else x)
        changed = int((before.notna() & before.astype(str).ne(after.astype(str))).sum())
        out[col] = after
        if changed: log.append({"column": col, "action": "whitespace_strip", "detail": "trimmed surrounding whitespace", "values_affected": changed})
    return out

def maybe_coerce_numeric(series, col, log):
    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)) or series.notna().sum() < 3: return series
    s = series.astype("string").str.strip()
    s = s.str.replace(r"^\((.*)\)$", r"-\1", regex=True).str.replace(r"[$€£¥₹%\s\u00a0]", "", regex=True)
    sample = s.dropna()
    eu = (not sample.empty and sample.str.match(r"^-?\d{1,3}(?:\.\d{3})+(?:,\d+)?$").mean() >= 0.5)
    if eu: s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False); note = " (EU decimal format)"
    else: s = s.str.replace(",", "", regex=False); note = ""
    parsed = pd.to_numeric(s, errors="coerce"); mask = series.notna()
    total, good = int(mask.sum()), int(parsed[mask].notna().sum())
    if total and good / total >= NUMERIC_PARSE_THRESHOLD:
        lost = total-good
        log.append({"column": col, "action": "numeric_coerce", "detail": f"parsed {good}/{total} values{note}" + (f"; {lost} unparseable -> NaN" if lost else ""), "values_affected": lost})
        return parsed
    return series

def maybe_coerce_datetime(series, col, log):
    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)) or series.notna().sum() < 3: return series
    mask = series.notna(); values = series[mask].astype(str).str.strip()
    if values.str.fullmatch(r"\d+(?:\.\d+)?").mean() >= 0.9 or values.str.contains(r"[-/.]", regex=True).mean() < 0.5: return series
    try: parsed = pd.to_datetime(series, errors="coerce", format="mixed")
    except (TypeError, ValueError): parsed = pd.to_datetime(series, errors="coerce")
    total, good = int(mask.sum()), int(parsed[mask].notna().sum())
    if not total or good/total < DATE_PARSE_THRESHOLD: return series
    years = parsed[mask].dropna().dt.year
    if years.empty or years.between(1900, 2100).mean() < 0.9: return series
    log.append({"column": col, "action": "datetime_parse", "detail": f"parsed {good}/{total} values as dates", "values_affected": total-good})
    return parsed

def scan_pii(df):
    rows = []
    for col in df.columns:
        sample = df[col].dropna().astype(str).head(PII_SAMPLE_SIZE)
        if sample.empty: continue
        for kind, pat in PII_PATTERNS.items():
            hits = int(sample.str.contains(pat, na=False).sum())
            if hits >= max(3, int(np.ceil(.10*len(sample)))):
                rows.append({"column": col, "pii_type": kind, "sample_hits": hits, "sample_size": len(sample)}); break
    return pd.DataFrame(rows, columns=["column", "pii_type", "sample_hits", "sample_size"])

def compute_quality(df, original_rows, dupes_removed):
    if df.empty or len(df.columns) == 0: return {"score": 0.0, "components": {}, "note": "no rows or columns after cleaning"}
    complete = float(1-df.isna().sum().sum()/(len(df)*len(df.columns)))
    unique = float(1-dupes_removed/max(original_rows, 1)); consist = []
    for col in df.columns:
        s = df[col].dropna().astype(str)
        consist.append(1.0 if s.empty else float((~s.str.contains(r"^\s|\s$|[\x00-\x1f]", regex=True)).mean()))
    consistency = float(np.mean(consist)) if consist else 1.0
    score = 100*(.4*complete+.3*unique+.3*consistency)
    return {"score": round(score,1), "components": {"completeness": round(100*complete,1), "uniqueness": round(100*unique,1), "consistency": round(100*consistency,1)}}

def _looks_like_id(col, s):
    name = str(col).lower()
    if name == "id" or name.endswith("_id") or name.endswith("id") or name in {"zip","zipcode","postcode","phone","ssn"}: return True
    v = s.dropna()
    return pd.api.types.is_numeric_dtype(s) and len(v)>10 and v.is_unique and v.nunique()>.9*len(v)

def make_dashboard(df, quality, missing, numeric, path):
    fig, axes = plt.subplots(2,2,figsize=(13,9)); fig.suptitle("CleanSheet Data Quality Dashboard",fontweight="bold")
    ax=axes[0,0]
    if missing.empty: ax.text(.5,.5,"No missing values",ha="center",va="center",transform=ax.transAxes); ax.axis("off")
    else: v=missing.sort_values(); ax.barh(v.index.astype(str),v.values); ax.set_xlabel("% missing")
    ax.set_title("Missing values by column")
    ax=axes[0,1]; ax.barh(["Quality"],[quality["score"]]); ax.set_xlim(0,100); ax.set_title(f"Quality score: {quality['score']}/100")
    cols=[c for c in numeric if not _looks_like_id(c,df[c])]
    ax=axes[1,0]
    if len(cols)>=2: sns.heatmap(df[cols].corr(),annot=len(cols)<=8,fmt=".2f",cmap="coolwarm",vmin=-1,vmax=1,ax=ax); ax.set_title("Numeric correlations")
    elif numeric: sns.histplot(df[numeric[0]].dropna(),ax=ax); ax.set_title(f"Distribution: {numeric[0]}")
    else: ax.text(.5,.5,"No numeric columns",ha="center",va="center",transform=ax.transAxes); ax.axis("off")
    ax=axes[1,1]; cols=[c for c in numeric[:4] if df[c].notna().any()]
    if cols: ax.boxplot([df[c].dropna().values for c in cols]); ax.set_xticks(range(1,len(cols)+1),cols,rotation=15); ax.set_title("Numeric distributions (outliers retained)")
    else: ax.text(.5,.5,"No numeric distributions",ha="center",va="center",transform=ax.transAxes); ax.axis("off")
    fig.tight_layout(rect=[0,0,1,.96]); fig.savefig(path,dpi=160,bbox_inches="tight"); plt.close(fig)

def build_report_markdown(source, df, original_rows, original_cols, dupes, log, missing, quality, pii):
    lines=[f"# CleanSheet Report — {Path(source).name}","",f"**Generated:** {pd.Timestamp.now():%Y-%m-%d %H:%M}","","## Quality score","",f"**{quality['score']} / 100**","","| Component | Score |","|---|---:|"]
    lines += [f"| {k.title()} | {v} |" for k,v in quality.get("components",{}).items()]
    lines += ["","## Shape","","| Metric | Value |","|---|---:|",f"| Original rows | {original_rows} |",f"| Cleaned rows | {len(df)} |",f"| Duplicates removed | {dupes} |",f"| Original columns | {original_cols} |","","## Transformation log",""]
    if log:
        lines += ["| Column | Action | Detail | Values affected |","|---|---|---|---:|"]
        for x in log:
            detail = str(x["detail"]).replace("|", "\\|")
            lines.append(f"| {x['column']} | {x['action']} | {detail} | {x.get('values_affected',0)} |")
    else: lines.append("_No transformations were necessary._")
    lines += ["","## Missing values",""]
    if missing.empty: lines.append("_No missing values detected._")
    else:
        lines += ["| Column | % missing |","|---|---:|"]+[f"| {c} | {v:.2f}% |" for c,v in missing.items()]
    lines += ["","## PII pattern scan",""]
    if pii.empty: lines.append("_No patterns met the sample threshold. This does not prove PII is absent._")
    else: lines += ["| Column | Pattern | Sample hits |","|---|---|---:|"]+[f"| {r['column']} | {r['pii_type']} | {r['sample_hits']}/{r['sample_size']} |" for _,r in pii.iterrows()]
    lines += ["","## Column dictionary","","| Column | Type | Non-null | Null % | Unique | Example |","|---|---|---:|---:|---:|---|"]
    for c in df.columns:
        s=df[c]; nn=int(s.notna().sum()); ex=str(s.dropna().iloc[0]).replace("|","\\|").replace("\n"," ")[:40] if nn else ""
        lines.append(f"| {c} | {s.dtype} | {nn} | {100*(1-nn/max(len(df),1)):.1f}% | {s.nunique(dropna=True)} | {ex} |")
    return "\n".join(lines)+"\n"

def run(input_path, out_zip="cleansheet_bundle.zip"):
    print("=== CleanSheet Reports ==="); print(f"Input: {input_path}"); log=[]
    df=load_data(input_path); rows,cols=len(df),len(df.columns); print(f"Loaded {rows:,} rows × {cols} columns.")
    df=strip_whitespace(normalize_columns(df,log),log); before=len(df); df=df.drop_duplicates().copy(); dupes=before-len(df)
    if dupes: log.append({"column":"*","action":"drop_duplicates","detail":f"removed {dupes} duplicate rows","values_affected":dupes})
    for c in list(df.columns):
        try: df[c]=maybe_coerce_numeric(df[c],c,log); df[c]=maybe_coerce_datetime(df[c],c,log)
        except (TypeError,ValueError,OverflowError) as e: log.append({"column":c,"action":"coerce_error","detail":f"{type(e).__name__}: {e}","values_affected":0})
    pii=scan_pii(df); quality=compute_quality(df,rows,dupes); missing=(df.isna().mean()*100).round(2); missing=missing[missing>0].sort_values(ascending=False); numeric=df.select_dtypes(include=[np.number]).columns.tolist()
    with tempfile.TemporaryDirectory(prefix="cleansheet-") as tmp:
        root=Path(tmp); csv=root/"cleansheet_cleaned.csv"; img=root/"cleansheet_dashboard.png"; tx=root/"cleansheet_transformations.csv"; flags=root/"cleansheet_pii_flags.csv"; q=root/"cleansheet_quality.json"; report=root/"cleansheet_report.md"
        df.to_csv(csv,index=False,encoding="utf-8-sig"); pd.DataFrame(log,columns=["column","action","detail","values_affected"]).to_csv(tx,index=False,encoding="utf-8-sig"); pii.to_csv(flags,index=False,encoding="utf-8-sig"); q.write_text(json.dumps(quality,indent=2),encoding="utf-8"); report.write_text(build_report_markdown(input_path,df,rows,cols,dupes,log,missing,quality,pii),encoding="utf-8")
        try: make_dashboard(df,quality,missing,numeric,img)
        except (ValueError,TypeError,IndexError) as e: print(f"Warning: dashboard generation failed: {e}")
        Path(out_zip).expanduser().resolve().parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(out_zip,"w",zipfile.ZIP_DEFLATED) as z:
            for p in [csv,img,report,tx,flags,q]:
                if p.is_file(): z.write(p,arcname=p.name)
    print(f"Rows: {rows:,} → {len(df):,} (duplicates removed: {dupes})"); print(f"Quality: {quality['score']}/100; transformations: {len(log)}; PII flags: {len(pii)}"); print(f"Bundle: {out_zip}")
    return {"bundle":str(out_zip),"quality":quality,"log":log,"pii":pii}
