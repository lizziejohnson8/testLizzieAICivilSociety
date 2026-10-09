"""Offline tests: network calls are replaced with canned responses."""

import csv
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tracker

GREENHOUSE = {"jobs": [
    {"title": "Policy Intern, Summer 2027", "absolute_url": "https://example.com/gh/1",
     "location": {"name": "Washington, DC"}},
    {"title": "Senior Research Engineer", "absolute_url": "https://example.com/gh/2",
     "location": {"name": "San Francisco"}},
    {"title": "AI Policy Fellowship", "absolute_url": "https://example.com/gh/3",
     "location": {"name": "Remote"}},
    {"title": "Chief of Staff, Public Sector", "absolute_url": "https://example.com/gh/4",
     "location": {"name": "Washington, DC"}},
    {"title": "Software Engineering Intern", "absolute_url": "https://example.com/gh/5",
     "location": {"name": "New York"}},
    {"title": "Senior Fellow, Economic Studies", "absolute_url": "https://example.com/gh/6",
     "location": {"name": "Washington, DC"}},
]}
ASHBY = {"jobs": [
    {"title": "Research Internship – Societal Impacts", "jobUrl": "https://example.com/a/1",
     "location": "London"},
    {"title": "Internal Tools Engineer", "jobUrl": "https://example.com/a/2", "location": "SF"},
]}
PAGE = """<html><body><nav><a href="/about">Internships menu</a></nav>
<h2>Open positions</h2>
<ul><li><a href="/jobs/summer-legal-intern">Summer 2027 Legal Internship</a></li>
<li><a href="/jobs/comms">Communications Manager</a></li></ul>
<h3>Technology Policy Fellowship (application opens soon)</h3>
<script>var intern = 1;</script></body></html>"""


def fake_get_json(url):
    return GREENHOUSE if "greenhouse" in url else ASHBY


ORGS = """name,track,source_type,source,notes
Lab A,AI & tech policy,greenhouse,laba,
Lab B,AI & tech policy,ashby,labb,
Civil Org,Women's rights & advocacy,page,https://civil.example.org/careers/,
Broken Org,Workforce & labor,page,https://broken.example.org/,
Federal: Labor,Workforce & labor,usajobs,Department of Labor,
# Commented Org,x,page,https://x,
"""


class TrackerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.patches = [
            mock.patch.object(tracker, "DATA", self.tmp),
            mock.patch.object(tracker, "POSTINGS_CSV", self.tmp / "postings.csv"),
            mock.patch.object(tracker, "POSTINGS_XLSX", self.tmp / "internships.xlsx"),
            mock.patch.object(tracker, "NEW_POSTINGS_MD", self.tmp / "new_postings.md"),
            mock.patch.object(tracker, "RUN_REPORT_MD", self.tmp / "run_report.md"),
            mock.patch.object(tracker, "ROOT", self.tmp),
            mock.patch.object(tracker, "get_json", side_effect=fake_get_json),
            mock.patch.object(tracker, "get_text", side_effect=self.fake_get_text),
        ]
        for p in self.patches:
            p.start()
        self.orgs = self.tmp / "orgs.csv"
        self.orgs.write_text(ORGS)
        self.config = Path(tracker.__file__).parent / "config.yaml"
        self.page = PAGE

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def fake_get_text(self, url):
        if "broken" in url:
            raise ConnectionError("404 Not Found")
        return self.page

    def rows(self):
        with (self.tmp / "postings.csv").open() as f:
            return list(csv.DictReader(f))

    def test_first_run_finds_matches_and_reports_errors(self):
        tracker.run(self.config, self.orgs, alerts=False)
        titles = {r["title"] for r in self.rows()}
        self.assertEqual(titles, {
            "Policy Intern, Summer 2027", "AI Policy Fellowship",
            "Research Internship – Societal Impacts", "Summer 2027 Legal Internship",
            "Technology Policy Fellowship (application opens soon)",
            "Chief of Staff, Public Sector",
        })
        by_title = {r["title"]: r for r in self.rows()}
        self.assertEqual(by_title["Chief of Staff, Public Sector"]["role_type"], "Chief of staff")
        self.assertEqual(by_title["AI Policy Fellowship"]["role_type"], "Fellowship")
        self.assertEqual(by_title["Summer 2027 Legal Internship"]["track"], "Women's rights & advocacy")
        legal = next(r for r in self.rows() if r["title"].startswith("Summer 2027 Legal"))
        self.assertEqual(legal["url"], "https://civil.example.org/jobs/summer-legal-intern")
        report = (self.tmp / "run_report.md").read_text()
        self.assertIn("Broken Org", report)
        self.assertIn("Federal: Labor**: skipped", report)  # no USAJOBS key in tests
        alert = (self.tmp / "new_postings.md").read_text()
        self.assertIn("6 new", alert)
        self.assertIn("## Women's rights & advocacy", alert)
        self.assertTrue((self.tmp / "internships.xlsx").exists())

    def test_second_run_only_alerts_on_new_and_keeps_user_notes(self):
        tracker.run(self.config, self.orgs, alerts=False)
        rows = self.rows()
        rows[0]["my_status"] = "Applied"
        with (self.tmp / "postings.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=tracker.COLUMNS)
            w.writeheader()
            w.writerows(rows)
        applied_id = rows[0]["id"]

        # The civil org takes one posting down and adds a new one.
        self.page = PAGE.replace("Summer 2027 Legal Internship", "Fall 2027 Research Intern")
        tracker.run(self.config, self.orgs, alerts=False)

        by_title = {r["title"]: r for r in self.rows()}
        self.assertEqual(by_title["Summer 2027 Legal Internship"]["still_listed"], "No")
        self.assertEqual(by_title["Fall 2027 Research Intern"]["still_listed"], "Yes")
        self.assertEqual({r["id"]: r for r in self.rows()}[applied_id]["my_status"], "Applied")
        alert = (self.tmp / "new_postings.md").read_text()
        self.assertIn("1 new", alert)
        self.assertIn("Fall 2027 Research Intern", alert)

    def test_usajobs_parses_results_when_key_is_set(self):
        payload = {"SearchResult": {"SearchResultItems": [
            {"MatchedObjectDescriptor": {
                "PositionTitle": "Student Trainee (Economist)", "OrganizationName": "Bureau of Labor Statistics",
                "PositionURI": "https://www.usajobs.gov/job/1", "PositionLocationDisplay": "Washington, DC"}},
            {"MatchedObjectDescriptor": {
                "PositionTitle": "Supervisory Economist", "OrganizationName": "Bureau of Labor Statistics",
                "PositionURI": "https://www.usajobs.gov/job/2", "PositionLocationDisplay": "Washington, DC"}},
        ]}}
        resp = mock.Mock(**{"json.return_value": payload})
        env = {"USAJOBS_API_KEY": "k", "USAJOBS_EMAIL": "me@example.com"}
        with mock.patch.dict("os.environ", env), mock.patch.object(tracker.requests, "get", return_value=resp):
            tracker.run(self.config, self.orgs, alerts=False)
        fed = [r for r in self.rows() if r["organization"] == "Federal: Labor"]
        self.assertEqual([r["title"] for r in fed], ["Student Trainee (Economist) (Bureau of Labor Statistics)"])
        self.assertEqual(fed[0]["role_type"], "Internship")

    def test_no_new_postings_removes_alert_file(self):
        tracker.run(self.config, self.orgs, alerts=False)
        tracker.run(self.config, self.orgs, alerts=False)
        self.assertFalse((self.tmp / "new_postings.md").exists())


if __name__ == "__main__":
    unittest.main()
