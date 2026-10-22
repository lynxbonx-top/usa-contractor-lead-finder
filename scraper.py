"""Public Google Maps listing extraction. No login, CAPTCHA bypass, or proxy rotation."""
import re, time, random
from datetime import datetime, timezone
from urllib.parse import quote, urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse as parse_date

HEADERS={'User-Agent':'Mozilla/5.0 (compatible; BusinessResearchTool/1.0)'}
EMAIL_RE=re.compile(r'(?<![\w.])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.])',re.I)
PHONE_RE=re.compile(r'(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}')
DATE_RE=re.compile(r'(?:20(?:1[9]|2[0-9]))[-/]\d{1,2}[-/]\d{1,2}')


def safe_site(url):
    try:
        p=urlparse(url)
        return p.scheme in ('http','https') and bool(p.hostname) and not (p.hostname in ('localhost','127.0.0.1') or p.hostname.endswith('.local'))
    except Exception:return False


def enrich_website(url, cutoff):
    """Only public site pages, best-effort extraction; site date is not proof phone/email freshness."""
    result={'email':'','website_recent_evidence':'','freshness':'Unverified'}
    if not safe_site(url):return result
    session=requests.Session(); session.headers.update(HEADERS)
    pages=[url]
    try:
        response=session.get(url,timeout=10,allow_redirects=True)
        if not safe_site(response.url) or 'text/html' not in response.headers.get('content-type',''):return result
        soup=BeautifulSoup(response.text[:700000],'html.parser')
        for a in soup.select('a[href]'):
            href=a.get('href','')
            if any(x in href.lower() for x in ('contact','about','team')):
                link=urljoin(response.url,href)
                if safe_site(link) and urlparse(link).hostname==urlparse(response.url).hostname and link not in pages:
                    pages.append(link)
                    if len(pages)>=3:break
        htmls=[response.text]
        for link in pages[1:]:
            try:
                r=session.get(link,timeout=8)
                if 'text/html' in r.headers.get('content-type',''):htmls.append(r.text[:500000])
            except requests.RequestException:pass
        emails=[]; dates=[]
        for html in htmls:
            soup=BeautifulSoup(html,'html.parser')
            for a in soup.select('a[href^="mailto:"]'):
                emails+=EMAIL_RE.findall(a.get('href',''))
            emails+=EMAIL_RE.findall(soup.get_text(' ',strip=True))
            for tag in soup.select('time[datetime],meta[property="article:published_time"],meta[property="article:modified_time"],meta[itemprop="dateModified"]'):
                v=tag.get('datetime') or tag.get('content') or ''
                try:dates.append(parse_date(v).date())
                except (ValueError,TypeError,OverflowError):pass
        emails=[e.lower() for e in emails if not any(x in e.lower() for x in ('example.com','sentry.io','wixpress.com'))]
        result['email']=next(iter(dict.fromkeys(emails)),'')
        recent=[d for d in dates if cutoff<=d<=datetime.now(timezone.utc).date()]
        if recent:
            result['website_recent_evidence']=max(recent).isoformat()
            result['freshness']='Recent website evidence (contact not verified)'
    except requests.RequestException:pass
    return result


def scrape_maps(query, city, state, limit=30, scrolls=12):
    """Google Maps visible UI; selectors can change. Return records and error info."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    rows=[]; error=''
    search=f'{query} in {city}, {state}, USA'
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1400,'height':900},locale='en-US')
        try:
            page.goto('https://www.google.com/maps/search/'+quote(search),wait_until='domcontentloaded',timeout=45000)
            page.wait_for_timeout(2200)
            if page.locator('text=/unusual traffic|verify you are human|captcha/i').count():
                return [],'Google requested verification. Stop and try later; no bypass is implemented.'
            feed=page.locator('[role="feed"]')
            if feed.count():
                for _ in range(scrolls):
                    feed.evaluate('(el) => el.scrollBy(0, el.clientHeight * 2)')
                    page.wait_for_timeout(850)
                    if page.locator('a[href*="/maps/place/"]').count()>=limit:break
            links=page.locator('a[href*="/maps/place/"]').evaluate_all('(els) => [...new Set(els.map(e=>e.href))]')[:limit]
            if not links:
                return [],'No listings appeared. Try a different city/keyword, or Google Maps may have blocked automated access.'
            for link in links:
                try:
                    page.goto(link,wait_until='domcontentloaded',timeout=25000)
                    page.wait_for_timeout(650)
                    title=page.locator('h1').first.inner_text(timeout=3500).strip()
                    def text_for(selector):
                        el=page.locator(selector).first
                        return (el.get_attribute('aria-label') or el.inner_text(timeout=1200)).strip() if el.count() else ''
                    address=text_for('button[data-item-id="address"]')
                    phone=text_for('button[data-item-id^="phone:"]')
                    website_el=page.locator('a[data-item-id="authority"]').first
                    website=website_el.get_attribute('href') if website_el.count() else ''
                    rating=''; reviews=''
                    rating_el=page.locator('div[role="img"][aria-label*="star"]').first
                    if rating_el.count():
                        label=rating_el.get_attribute('aria-label') or ''
                        m=re.search(r'([0-5](?:\.\d)?)\s*star',label,re.I)
                        if m:rating=m.group(1)
                        n=re.search(r'([\d,]+)\s*reviews?',label,re.I)
                        if n:reviews=n.group(1).replace(',','')
                    rows.append({'business_name':title,'category':query,'city':city,'state':state,'address':address.replace('Address:','').strip(),'phone':phone.replace('Phone:','').strip(),'website':website or '', 'email':'','owner_name':'','rating':rating,'review_count':reviews,'google_maps_url':link,'website_recent_evidence':'','freshness':'Unverified','source':'Google Maps public listing'})
                except Exception:
                    continue
        except PWTimeout:
            error='Google Maps timed out. Try a smaller query or another city.'
        finally:browser.close()
    return rows,error


def dedupe(df):
    import pandas as pd
    if df.empty:return df
    df=df.copy()
    def key(row):
        phone=re.sub(r'\D','',str(row.get('phone','')))
        if len(phone)>=10:return 'phone:'+phone[-10:]
        url=str(row.get('website',''))
        host=urlparse(url).hostname or ''
        if host:return 'site:'+host.lower().removeprefix('www.')
        return 'name:'+re.sub(r'\W','',str(row.get('business_name','')).lower())+'|'+str(row.get('city','')).lower()+'|'+str(row.get('state','')).lower()
    df['_key']=df.apply(key,axis=1)
    return df.drop_duplicates('_key').drop(columns='_key').reset_index(drop=True)
