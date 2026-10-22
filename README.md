# USA Contractor Lead Finder

A Streamlit dashboard for researching publicly listed US home service contractors via Google Maps' visible pages and their business websites. No paid API required.

## Run locally (recommended for reliability)

Python 3.10+ required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
streamlit run app.py
```

On Windows, activate with `.venv\\Scripts\\activate`.

## Deploy online (experimental)

Push `app.py`, `scraper.py`, `requirements.txt`, `packages.txt`, and `README.md` to GitHub. Deploy `app.py` at https://share.streamlit.io. Browser installation is not guaranteed by Streamlit Cloud; if browser executable is missing, use the included Dockerfile on a host that supports containers. Google may restrict requests from cloud IPs.

## Docker (web app)

```bash
docker build -t contractor-leads .
docker run --rm -p 8501:8501 contractor-leads
```

Open http://localhost:8501. Deploy the Docker image on any container host, subject to its plan and restrictions.

## Freshness and accuracy

The requested 7-year cutoff is **October 22, 2019**. Google Maps does not provide a reliable last-updated date for each business. This app labels records as `Unverified` unless a business website includes a dated HTML time/meta tag within the last 7 years. That is evidence of recent website activity, not confirmation of when a phone/email was updated. No owner names are guessed. No guarantee of coverage, currentness, or deliverability.

## Compliance and limits

Use only public business details. Do not bypass CAPTCHAs, login restrictions, or blocks. Google Maps automated extraction may violate its terms; check before using. Do not use scraped numbers for unsolicited SMS without required consent. Respect website terms and local law. No proxies or CAPTCHA-solving features are included. Searches are city-by-city, not an unattended nationwide crawl. Data stays in your Streamlit session until exported.
