# signet/cli.py
import os, argparse, json, pandas as pd
from .cleaner import SignetCleaner, infer_report_month

def main():
    ap = argparse.ArgumentParser("signet-clean")
    ap.add_argument("input_path")
    ap.add_argument("--out-csv", default=None)
    ap.add_argument("--report-month", default=None)
    ap.add_argument("--master-parquet", default=None)
    ap.add_argument("--no-replace", action="store_true")
    args = ap.parse_args()

    sc = SignetCleaner()
    raw = sc.load_raw(args.input_path)
    clean = sc.clean(raw)
    month = args.report_month or infer_report_month(args.input_path)
    clean["report_month"] = month
    clean = sc.dedupe_within_month(clean)

    out_csv = args.out_csv or os.path.splitext(args.input_path)[0] + f"_CLEAN_{month}.csv"
    clean.to_csv(out_csv, index=False)

    result = {"clean_csv": out_csv, "report_month": month, "rows": int(len(clean))}
    if args.master_parquet:
        if os.path.exists(args.master_parquet):
            master = pd.read_parquet(args.master_parquet)
            if not args.no_replace:
                master = master[master["report_month"] != month]
            master = pd.concat([master, clean], ignore_index=True)
        else:
            os.makedirs(os.path.dirname(args.master_parquet), exist_ok=True)
            master = clean
        master.to_parquet(args.master_parquet, index=False)
        result.update({"master_parquet": args.master_parquet, "master_rows": int(len(master))})

    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
