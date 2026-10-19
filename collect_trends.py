from pathlib import Path
from datetime import datetime, timezone
import time
import pandas as pd
from pytrends.request import TrendReq

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS_FILE = ROOT / "config" / "trend_keywords.txt"
DATA_DIR = ROOT / "data"
HISTORY_FILE = DATA_DIR / "trends_history.csv"
LATEST_FILE = DATA_DIR / "trends_latest.csv"

def main():
    DATA_DIR.mkdir(exist_ok=True)
    keywords = [x.strip() for x in KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
                if x.strip() and not x.strip().startswith("#")]
    if not keywords:
        print("No keywords configured.")
        return

    try:
        pytrends = TrendReq(hl="ru-RU", tz=180, timeout=(10, 25), retries=1, backoff_factor=1)
    except Exception as exc:
        raise SystemExit(f"Could not initialize Google Trends client: {exc}")

    date = datetime.now(timezone.utc).date().isoformat()
    records = []
    # Google Trends supports only a small batch of terms; compare within batches, not across them.
    for keyword in keywords:
        try:
            pytrends.build_payload([keyword], cat=0, timeframe="today 12-m", geo="RU", gprop="")
            frame = pytrends.interest_over_time()
            if frame.empty or keyword not in frame.columns:
                records.append({"date": date, "keyword": keyword, "trend_index": None,
                                "source": "Google Trends", "status": "no_data"})
            else:
                values = pd.to_numeric(frame[keyword], errors="coerce").dropna()
                records.append({"date": date, "keyword": keyword,
                                "trend_index": int(values.tail(4).mean()) if len(values) else None,
                                "source": "Google Trends", "status": "ok"})
            print(f"Collected: {keyword}")
        except Exception as exc:
            print(f"Skipped {keyword}: {exc}")
            records.append({"date": date, "keyword": keyword, "trend_index": None,
                            "source": "Google Trends", "status": "error"})
        time.sleep(3)

    today = pd.DataFrame(records)
    if HISTORY_FILE.exists():
        history = pd.read_csv(HISTORY_FILE)
        history = pd.concat([history, today], ignore_index=True)
    else:
        history = today
    history = history.drop_duplicates(subset=["date", "keyword"], keep="last")
    history.to_csv(HISTORY_FILE, index=False)
    today.to_csv(LATEST_FILE, index=False)
    print(f"Saved {len(today)} keyword rows.")

if __name__ == "__main__":
    main()
