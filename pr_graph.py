import os
import requests
from datetime import datetime
from collections import Counter
import matplotlib.pyplot as plt

# ======= 설정 부분 =======
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # 미리 export 해두면 편함
OWNER = "onearmedoflepanto"
REPO = "pr_test"

# 필요하면 특정 기간만 보고 싶을 때 사용 (UTC 기준)
# START_ISO = "2025-11-18T00:00:00Z"
START_ISO = None
END_ISO = None
# =========================

session = requests.Session()
if GITHUB_TOKEN:
    session.headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
session.headers["Accept"] = "application/vnd.github+json"

BASE = "https://api.github.com"

import json
import csv
from pathlib import Path

OUTPUT_DIR = Path("dump")
OUTPUT_DIR.mkdir(exist_ok=True)


def dump_results(times, counts):
    # CSV 저장
    csv_path = OUTPUT_DIR / "comment_buckets.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["bucket_time_utc", "count"])
        for t, c in zip(times, counts):
            writer.writerow([t.isoformat(), c])
    print(f"[+] CSV saved: {csv_path}")

    # JSON 저장
    json_path = OUTPUT_DIR / "comment_buckets.json"
    data = [
        {"bucket_time_utc": t.isoformat(), "count": c} for t, c in zip(times, counts)
    ]
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[+] JSON saved: {json_path}")


def fetch_all(url, params=None):
    """GitHub API pagination 처리"""
    results = []
    params = params or {}
    per_page = 100
    page = 1
    while True:
        params.update({"per_page": per_page, "page": page})
        resp = session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        results.extend(data)
        if len(data) < per_page:
            break
        page += 1
    return results


def get_open_prs(owner, repo):
    url = f"{BASE}/repos/{owner}/{repo}/pulls"
    return fetch_all(url, params={"state": "open"})


def get_issue_comments(owner, repo, issue_number):
    url = f"{BASE}/repos/{owner}/{repo}/issues/{issue_number}/comments"
    return fetch_all(url)


def get_review_comments(owner, repo, pr_number):
    url = f"{BASE}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
    return fetch_all(url)


def parse_iso(iso_str):
    # "2025-11-19T10:23:45Z" → datetime (UTC)
    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))


def in_range(dt):
    if START_ISO:
        if dt < parse_iso(START_ISO):
            return False
    if END_ISO:
        if dt > parse_iso(END_ISO):
            return False
    return True


def floor_to_5min(dt):
    # dt: aware datetime
    minute_bucket = (dt.minute // 5) * 5
    return dt.replace(minute=minute_bucket, second=0, microsecond=0)


def main():
    print(f"Fetching open PRs from {OWNER}/{REPO} ...")
    prs = get_open_prs(OWNER, REPO)
    print(f"Open PR count: {len(prs)}")

    buckets = Counter()

    for pr in prs:
        number = pr["number"]
        print(f"  -> PR #{number}: collecting comments")

        # issue comments
        issue_comments = get_issue_comments(OWNER, REPO, number)
        # review comments
        review_comments = get_review_comments(OWNER, REPO, number)

        all_comments = issue_comments + review_comments

        for c in all_comments:
            created = parse_iso(c["created_at"])
            if not in_range(created):
                continue
            # 필요하면 KST로 보고 싶으면 아래처럼 변경:
            # created = created.astimezone(timezone(timedelta(hours=9)))
            bucket_time = floor_to_5min(created)
            buckets[bucket_time] += 1

    if not buckets:
        print("No comments found in open PRs (or in selected time range).")
        return

    # 시간 순으로 정렬
    times = sorted(buckets.keys())
    counts = [buckets[t] for t in times]

    dump_results(times, counts)

    # 그래프 그리기
    plt.figure(figsize=(12, 6))
    plt.plot(times, counts, marker="o")
    plt.xlabel("Time (5-minute buckets, UTC)")
    plt.ylabel("# of comments")
    plt.title(f"Comments per 5 minutes for open PRs in {OWNER}/{REPO}")
    plt.grid(True)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
