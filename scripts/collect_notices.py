import argparse
import html
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo


SOURCES = {
    "school": "https://www.usst.edu.cn/xw/list.htm",
    "teaching": "https://jwc.usst.edu.cn/10239/list.htm",
    "oece": "https://oece.usst.edu.cn/xs/list.htm",
    "mechanical": "https://me.usst.edu.cn/tzgg_12289/list.htm",
}
HOSTS = {urlsplit(url).hostname for url in SOURCES.values()}
SHANGHAI = ZoneInfo("Asia/Shanghai")
MAX_HTML = 256 * 1024
MAX_ROWS = 40
ARTICLE = re.compile(r"/(?:_[st][0-9]+/)?[0-9]{4}/[0-9]{4}/c[0-9]+a[0-9]+/page\.(?:htm|psp)")
MAIN_LIST = re.compile(
    r"""<ul\b[^>]*\sclass\s*=\s*(['"])\s*news_list\s+list2\s*\1[^>]*>(.*?)</ul\s*>""",
    re.I | re.S,
)
ANCHOR = re.compile(r"""<a\b((?:[^>"']|"[^"]*"|'[^']*')*)>(.*?)</a\s*>""", re.I | re.S)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_html(url):
    request = Request(url, headers={"Accept": "text/html", "User-Agent": "Like-Campus-Notices/1.0"})
    with build_opener(NoRedirect()).open(request, timeout=8) as response:
        if response.status != 200 or response.url != url or response.headers.get_content_type() != "text/html":
            raise ValueError("unexpected column response")
        body = response.read(MAX_HTML + 1)
    if len(body) > MAX_HTML:
        raise ValueError("column exceeds size limit")
    return body.decode("utf-8-sig")


def attribute(name, tag):
    match = re.search(rf"""(?:^|\s){name}\s*=\s*(?:"([^"]*)"|'([^']*)')""", tag, re.I)
    return (match[1] if match[1] is not None else match[2]) if match else None


def element(name, row):
    match = re.search(
        rf"""<(div|span)\b[^>]*\sclass\s*=\s*['"][^'"]*\b{name}\b[^'"]*['"][^>]*>(.*?)</\1\s*>""",
        row, re.I | re.S,
    )
    return match[2] if match else ""


def clean(value):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", value)).split())


def valid_title(value):
    return isinstance(value, str) and 4 <= len(value) <= 320 and value.isprintable() and value == value.strip()


def article_url(value, source):
    try:
        parts = urlsplit(urljoin(SOURCES[source], value))
        if parts.scheme == "https" and parts.netloc.lower() in HOSTS and ARTICLE.fullmatch(parts.path):
            return f"https://{parts.hostname}{parts.path}"
    except ValueError:
        pass
    return None


def calendar_day(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_column(page, source, today):
    page = re.sub(r"<!--.*?-->|<(script|style)\b[^>]*>.*?</\1\s*>", "", page, flags=re.I | re.S)
    lists = MAIN_LIST.findall(page)
    if len(lists) != 1:
        raise ValueError("expected one dated list")
    rows = re.findall(r"<li\b[^>]*>(.*?)</li\s*>", lists[0][1], re.I | re.S)
    notices = {}
    for row in rows[:MAX_ROWS]:
        anchor = ANCHOR.search(element("news_title", row))
        if not anchor:
            continue
        url = article_url(html.unescape(attribute("href", anchor[1]) or ""), source)
        title = clean(attribute("title", anchor[1]) or anchor[2])
        year_month = clean(element("news_years", row))
        day_of_month = clean(element("news_days", row))
        if year_month and re.fullmatch(r"[0-9]{1,2}", day_of_month):
            published = calendar_day(f"{year_month}-{int(day_of_month):02d}")
        else:
            published = calendar_day(clean(element("news_meta", row) or element("news_date", row)))
        if url and valid_title(title) and published and published <= today and url not in notices:
            notices[url] = {"title": title, "date": published.isoformat(), "url": url}
    if not notices:
        raise ValueError("no valid article in the dated list")
    return list(notices.values())


def validate_feed(feed):
    if not isinstance(feed, dict) or set(feed) != {"version", "sources"} or type(feed["version"]) is not int or feed["version"] != 1:
        raise ValueError("invalid notice feed version")
    sources = feed["sources"]
    if not isinstance(sources, dict) or set(sources) != set(SOURCES):
        raise ValueError("wrong source set")
    for source, rows in sources.items():
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            raise ValueError(f"invalid row count for {source}")
        urls = set()
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"title", "date", "url"}
                    or not valid_title(row["title"]) or calendar_day(row["date"]) is None
                    or not isinstance(row["url"], str) or article_url(row["url"], source) != row["url"]
                    or row["url"] in urls):
                raise ValueError(f"invalid article for {source}")
            urls.add(row["url"])
    return sources


def collect(output, today, fetch=fetch_html):
    previous = validate_feed(json.loads(output.read_text(encoding="utf-8"))) if output.exists() else {}
    current = {}
    successes = 0
    since = (today - timedelta(days=120)).isoformat()
    for source, url in SOURCES.items():
        try:
            parsed = parse_column(fetch(url), source, today)
        except (OSError, ValueError) as error:
            if source in previous:
                current[source] = previous[source]
            print(f"{source}: {type(error).__name__}; {'kept prior list' if source in previous else 'no prior list'}")
        else:
            recent = [row for row in parsed if row["date"] >= since]
            current[source] = sorted(recent, key=lambda row: (row["date"], row["url"]), reverse=True)
            successes += 1
            print(f"{source}: {len(parsed)} valid, {len(recent)} recent")
    if len(current) != len(SOURCES) or not successes:
        raise ValueError("no complete new snapshot; existing feed left in place")
    feed = {"version": 1, "sources": current}
    validate_feed(feed)
    content = json.dumps(feed, ensure_ascii=False, indent=2) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") == content:
        print("feed unchanged")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(output)


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", type=Path, default=Path("notices/v1/feed.json"))
    options = cli.parse_args()
    collect(options.output, datetime.now(SHANGHAI).date())
