# scripts/convert_logs_to_jst.py
import csv
import os
from datetime import datetime, timedelta, timezone

LOGS_DIR = "logs"

def convert_file(path: str):
    tmp_path = path + ".tmp"
    JST = timezone(timedelta(hours=9))

    with open(path, "r") as infile, open(tmp_path, "w", newline="") as outfile:
        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        headers = next(reader, None)
        if headers:
            writer.writerow(headers)

        for row in reader:
            if not row:
                continue
            try:
                # 日次集計ファイル
                if row[0] and "T" in row[0] and not row[0].endswith("+09:00"):
                    dt = datetime.fromisoformat(row[0])
                    row[0] = dt.astimezone(JST).isoformat(timespec="seconds")
            except Exception:
                pass
            writer.writerow(row)

    os.replace(tmp_path, path)
    print(f"✅ Converted {path}")

def main():
    for fname in os.listdir(LOGS_DIR):
        if fname.startswith("trades_") and fname.endswith(".csv"):
            path = os.path.join(LOGS_DIR, fname)
            convert_file(path)

if __name__ == "__main__":
    main()
