import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from collect_notices import SOURCES, collect, parse_column


DAY = date(2026, 11, 27)


def row(href, day="2026-11-26", title="期末&nbsp;复习安排"):
    return f"""<li><span class="news_title"><a href='{href}' title='{title}'>截断标题</a></span>
    <span class="news_meta">{day}</span></li>"""


def column(*rows):
    return '<ul class="news_list list2">' + "".join(rows) + "</ul>"


class NoticeTests(unittest.TestCase):
    def test_dated_list_uses_original_title_and_only_canonical_articles(self):
        href = "/2026/1126/c1a2/page.htm"
        text = """<script>const fake = '<ul class="news_list list2">fake</ul>'</script>"""
        text += column(
            row(href + "?from=list#top"),
            row(href),
            row("https://www.usst.edu.cn.evil.invalid" + href),
            row("https://www.usst.edu.cn:443" + href),
            row("/2026/1128/c1a3/page.htm", "2026-11-28"),
            row("/2026/1131/c1a4/page.htm", "2026-11-31"),
        )
        self.assertEqual(parse_column(text, "school", DAY), [{
            "title": "期末 复习安排", "date": "2026-11-26", "url": "https://www.usst.edu.cn" + href,
        }])
        with self.assertRaises(ValueError):
            parse_column(column(row(href)) * 2, "school", DAY)

    def test_initial_partial_batch_and_malformed_update_keep_prior_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "feed.json"
            old = column(row("/2026/1126/c1a2/page.htm"))
            changed = column(row("/2026/1127/c1a3/page.htm", "2026-11-27"))

            def partial(url):
                return "<html>changed layout</html>" if url == SOURCES["school"] else changed

            with self.assertRaises(ValueError):
                collect(output, DAY, partial)
            self.assertFalse(output.exists())
            collect(output, DAY, lambda _: old)
            previous = json.loads(output.read_bytes())["sources"]
            collect(output, DAY, partial)
            current = json.loads(output.read_bytes())["sources"]
            self.assertEqual(previous["school"], current["school"])
            self.assertNotEqual(previous["teaching"], current["teaching"])
            unchanged = output.read_bytes()
            with self.assertRaises(ValueError):
                collect(output, DAY, lambda _: "<html></html>")
            self.assertEqual(output.read_bytes(), unchanged)
            collect(output, DAY, partial)
            self.assertEqual(output.read_bytes(), unchanged)


if __name__ == "__main__":
    unittest.main()
