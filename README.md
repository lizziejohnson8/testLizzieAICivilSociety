# Internship Tracker & Alerts: AI and civil society

This repo checks the careers pages of organizations in your field once a day.
It keeps every internship and fellowship it finds in a spreadsheet and alerts you
when a new one appears.

```
organizations.csv ──►  tracker.py  ──►  data/internships.xlsx   (formatted spreadsheet)
config.yaml       ──►  (daily, via  ──►  data/postings.csv       (same data, editable)
                        GitHub         ──►  data/run_report.md      (what worked / what failed)
                        Actions)       ──►  🔔 GitHub issue (+ optional email / Slack)
```

## How it works

1. **`organizations.csv`** lists the organizations you want to watch. Edit it on GitHub
   to add or remove organizations.
2. Every day, **GitHub Actions** runs `tracker.py`, which pulls each organization's job
   listings and keeps only titles that match your keywords in **`config.yaml`**
   (intern, fellowship, summer, and so on).
3. Anything it hasn't seen before is added to the spreadsheet with today's date.
   It also triggers an **alert**:
   - A **GitHub issue** labelled `internship-alert` and assigned to you. GitHub emails
     you about issues assigned to you by default. On a phone, the GitHub app sends a
     push notification.
   - Optionally, an **email** or a **Slack message**. See the setup section below.
4. Postings that disappear from a site stay in the spreadsheet, marked `Still Listed = No`.
   You keep the history.

## The spreadsheet

Download `data/internships.xlsx` from GitHub. It has two sheets:

- **Postings**: organization, title, location, link, first seen, last seen, and
  whether it's still listed. New rows are highlighted in green.
- **Organizations**: every organization you track, how many open matches each has,
  and whether the last check worked.

`data/postings.csv` holds the same data in a simpler format. It also has two columns
for you, **`my_status`** (for example Interested, Applied, Interviewing or Rejected)
and **`my_notes`**. The tracker never overwrites those two columns. Edit them in
`postings.csv` (directly on GitHub or in Excel or Sheets, saved as CSV). Your edits
then carry over into the `.xlsx` on the next run.

> Tip: if the repo is public, Google Sheets can show the data live:
> `=IMPORTDATA("https://raw.githubusercontent.com/<you>/<repo>/main/data/postings.csv")`

## Adding organizations

Each row in `organizations.csv` has a `source_type` and a `source`:

| source_type  | Use when the jobs link looks like…                 | `source` value               |
|--------------|----------------------------------------------------|------------------------------|
| `greenhouse` | `boards.greenhouse.io/anthropic` or `job-boards.greenhouse.io/anthropic` | `anthropic`                  |
| `lever`      | `jobs.lever.co/acme`                               | `acme`                       |
| `ashby`      | `jobs.ashbyhq.com/openai`                          | `openai`                     |
| `workable`   | `apply.workable.com/acme`                          | `acme`                       |
| `page`       | Anything else: an ordinary careers or internships page | the full URL                 |

To find out which type an organization uses, click **Apply** on any of its job listings
and look at the web address. Greenhouse, Lever, Ashby and Workable are the most reliable
sources because they return structured data. `page` works on any site: it reads the
page's links and headings and keeps the ones that match your keywords. For a
`page` source, point at the most specific page you can find, such as the internships
page rather than the homepage.

If a URL is wrong or a site blocks the request, the run still finishes. The problem
appears in `data/run_report.md` and in the **Organizations** sheet so you can fix it.

## Changing which jobs match

Edit `config.yaml`:

- `include_keywords`: a title must contain at least one of these (whole words,
  case-insensitive).
- `exclude_keywords`: a title containing any of these is dropped (for example `senior`).
- `locations`: optionally keep only postings in, for example, `Washington`, `Boston`
  or `Remote`.

## Setup (one time)

1. **Turn on Actions.** Open the repo's **Actions** tab, select *Internship alerts*,
   then click **Run workflow** to do the first check now. The first run reports every
   currently open matching posting as new. After that, you only hear about new ones.
2. **Allow it to save the spreadsheet.** If the run fails on the "Save" step, go to
   **Settings → Actions → General → Workflow permissions** and choose
   **Read and write permissions**.
3. **Make sure you get the alert emails.** At github.com/settings/notifications, check
   that email is on for issues and that you're *watching* this repo.
4. *(Optional)* **Email alerts directly.** Under **Settings → Secrets and variables → Actions**,
   add these secrets: `SMTP_HOST` (for example `smtp.gmail.com`), `SMTP_PORT` (`587`),
   `SMTP_USER`, `SMTP_PASSWORD` (for Gmail, an
   [app password](https://myaccount.google.com/apppasswords)), and `ALERT_EMAIL_TO`.
5. *(Optional)* **Slack alerts.** Add a `SLACK_WEBHOOK_URL` secret (an incoming webhook).

To change how often it runs, edit the `cron` line in
`.github/workflows/internship-alerts.yml`. For example, `17 12 * * 1-5` runs on weekdays only.

## Running it on your own computer

```bash
pip install -r requirements.txt
python tracker.py --no-alerts       # updates data/ without sending email/Slack
python -m unittest discover -s tests
```

## Limits

- `page` sources can only see postings that appear in the page's HTML. A few sites
  load their listings with JavaScript, and those may show no matches. If an organization
  never seems to match, open its listing and check whether it uses one of the
  job-board types above.
- Many fellowships (for example TechCongress, university summer programs, and
  government programs like PMF) are only announced once a year. Add their pages anyway:
  the tracker alerts you when wording like "2027 Fellowship" appears.
- Good places to find more organizations: the 80,000 Hours job board (AI policy filter),
  Tech Policy Press, the All Tech Is Human job board, and HKS's career office listings.
