import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

def ensure_chromium():
    with sync_playwright() as p:
        browser_path = Path(p.chromium.executable_path)

    if not browser_path.exists():
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
        )

ensure_chromium()


import streamlit as st
import pandas as pd
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from scraper import scrape_maps, enrich_website, dedupe

st.set_page_config(page_title='USA Contractor Lead Finder',page_icon='🏠',layout='wide')
st.title('🏠 USA Contractor Lead Finder')
st.caption('Public Google Maps listings + public business websites • No paid API key • Respect site terms and usage limits')
cutoff=date(2019,10,22)
st.info('7-year freshness rule: cutoff October 22, 2019. Google Maps does not expose reliable record-update dates. A dated webpage is evidence of site activity, NOT proof that an email or phone is current. Unverified contacts are labeled clearly.')
CATEGORIES=['Roofing contractors','HVAC contractors','Plumbers','Electricians','Landscaping contractors','Tree service','Painting contractors','Pest control companies','General contractors','Pool service','Garage door repair','Cleaning services','Concrete contractors','Solar installers']
STATES=['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC']
with st.sidebar:
    st.header('Search settings')
    category=st.selectbox('Contractor category',CATEGORIES)
    city=st.text_input('City',value='Houston')
    state=st.selectbox('State',STATES,index=STATES.index('TX'))
    limit=st.slider('Maximum businesses per search',5,100,30,5)
    st.caption('Search one city at a time. Repeat for other cities/states; accumulated leads remain in this session.')
    search=st.button('🔎 Find businesses',type='primary',use_container_width=True)
if 'leads' not in st.session_state:st.session_state.leads=pd.DataFrame()
if search:
    if not city.strip():st.error('Enter a city.')
    else:
        with st.spinner('Searching public Google Maps listings…'):
            try:rows,error=scrape_maps(category,city.strip(),state,limit)
            except Exception as e:rows,error=[],f'Browser failed: {type(e).__name__}: {e}. Install Playwright Chromium as described in README.'
        if error:st.warning(error)
        if rows:
            combined=pd.concat([st.session_state.leads,pd.DataFrame(rows)],ignore_index=True)
            st.session_state.leads=dedupe(combined)
            st.success(f'Found {len(rows)} listings. {len(st.session_state.leads)} unique leads in session.')
st.subheader('Your leads')
file=st.file_uploader('Import existing CSV (optional)',type=['csv'])
if file is not None:
    if st.button('Merge imported CSV'):
        try:
            incoming=pd.read_csv(file).fillna('')
            st.session_state.leads=dedupe(pd.concat([st.session_state.leads,incoming],ignore_index=True))
            st.success('CSV merged and deduplicated.')
        except Exception as e:st.error(str(e))
df=st.session_state.leads
if not df.empty:
    col1,col2,col3=st.columns(3)
    col1.metric('Unique businesses',len(df))
    col2.metric('Business phones',int(df.get('phone',pd.Series(dtype=str)).fillna('').astype(str).str.len().gt(0).sum()))
    col3.metric('Business emails',int(df.get('email',pd.Series(dtype=str)).fillna('').astype(str).str.len().gt(0).sum()))
    if st.button('✉️ Find public website emails & dated evidence'):
        urls=df.get('website',pd.Series(dtype=str)).fillna('').astype(str)
        todo=[(idx,url) for idx,url in urls.items() if url.startswith(('http://','https://'))]
        bar=st.progress(0)
        with ThreadPoolExecutor(max_workers=3) as pool:
            tasks={pool.submit(enrich_website,url,cutoff):idx for idx,url in todo}
            for n,future in enumerate(as_completed(tasks)):
                idx=tasks[future]
                try:
                    for k,v in future.result().items():
                        if v:df.loc[idx,k]=v
                except Exception:pass
                bar.progress((n+1)/max(1,len(tasks)))
        st.session_state.leads=df
        st.success('Website enrichment completed. Review accuracy before outreach.')
    show=st.selectbox('Freshness filter',['All records','Recent website evidence','Unverified only'])
    filtered=df.copy()
    if show=='Recent website evidence':filtered=filtered[filtered.get('freshness','').astype(str).str.startswith('Recent')]
    elif show=='Unverified only':filtered=filtered[~filtered.get('freshness','').astype(str).str.startswith('Recent')]
    st.dataframe(filtered,hide_index=True,use_container_width=True)
    st.download_button('⬇️ Export filtered CSV',filtered.to_csv(index=False).encode('utf-8-sig'),'usa_contractors.csv','text/csv',use_container_width=True)
    if st.button('Clear session leads'):st.session_state.leads=pd.DataFrame();st.rerun()
else:st.info('Choose a category, city and state, then click Find businesses.')
st.caption('No Google API keys or paid services required. Automated Maps access may be restricted by Google. Use reasonable volumes and comply with applicable website terms and outreach laws.')
