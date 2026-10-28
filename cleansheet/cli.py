"""CLI entry point, with optional Colab upload support."""
import argparse
from .core import run

def main(argv=None):
    parser=argparse.ArgumentParser(prog="cleansheet",description="Clean CSV/Excel data and create an auditable report bundle.")
    parser.add_argument("input",nargs="?",help="CSV, XLSX, or XLS file")
    parser.add_argument("--out",default="cleansheet_bundle.zip",help="Output ZIP path")
    args=parser.parse_args(argv)
    if args.input is None:
        try: from google.colab import files
        except ImportError: parser.error("An input file is required outside Google Colab.")
        uploaded=files.upload()
        if not uploaded: parser.error("No file was uploaded.")
        args.input=next(iter(uploaded))
    result=run(args.input,args.out)
    try:
        from google.colab import files
        files.download(result["bundle"])
    except ImportError: pass

if __name__=="__main__": main()
