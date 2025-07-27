import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

# -----------------------------
# 📊 Scrape Premarket Data
# -----------------------------
def parse_float_shares(text):
    text = text.strip().upper()
    number = float(re.sub(r'[^\d\.]', '', text))
    if 'B' in text:
        return number * 1_000_000_000
    elif 'M' in text:
        return number * 1_000_000
    return number

def get_stock_float(ticker):
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        soup = BeautifulSoup(requests.get(url, headers=headers, timeout=10).text, "html.parser")
        tables = soup.find_all("table")
        value = None
        for tbl in tables:
            txt = tbl.get_text(separator="|")
            if "Shs Float" in txt:
                cells = txt.split("|")
                for i, cell in enumerate(cells):
                    if cell.strip() == "Shs Float":
                        value = cells[i+1]
                        break
                break
        return parse_float_shares(value) if value else None
    except:
        return None

def get_premarket_data():
    url = "https://www.benzinga.com/premarket"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        if not table:
            return None, "Could not find the premarket table. Website structure may have changed."

        rows = table.find_all("tr")
        header = [th.text.strip().lower() for th in rows[0].find_all("th")]
        try:
            idx_symbol = header.index("ticker")
            idx_name = header.index("company")
            idx_price = header.index("close▲▼")
            idx_change = header.index("±%")
            idx_volume = header.index("avg. vol▲▼")
        except ValueError as e:
            return None, f"Header parsing failed: {e}"

        data = []
        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < max(idx_symbol, idx_name, idx_price, idx_change, idx_volume) + 1:
                continue
            try:
                symbol = cols[idx_symbol].text.strip()
                name = cols[idx_name].text.strip()
                price = float(cols[idx_price].text.strip().replace("$", "").replace(",", ""))
                percent_change = float(cols[idx_change].text.strip().replace("%", "").replace("+", "").replace(",", ""))
                volume_text = cols[idx_volume].text.strip().replace(",", "").upper()

                if "K" in volume_text:
                    volume = float(volume_text.replace("K", "")) * 1_000
                elif "M" in volume_text:
                    volume = float(volume_text.replace("M", "")) * 1_000_000
                elif "B" in volume_text:
                    volume = float(volume_text.replace("B", "")) * 1_000_000_000
                else:
                    volume = int(volume_text)

                if 1 <= price <= 25 and percent_change >= 5 and volume >= 100_000:
                    float_shares = get_stock_float(symbol)
                    if float_shares is not None and float_shares <= 5_000_000:  # Ross prefers low float < 5M
                        data.append({
                            "Symbol": symbol,
                            "Name": name,
                            "Price": price,
                            "% Change": percent_change,
                            "Volume": int(volume),
                            "Float": int(float_shares)
                        })
            except ValueError:
                continue

        return pd.DataFrame(data), None
    except Exception as e:
        return None, f"Request failed: {e}"

# -----------------------------
# 🧠 Reason for Move (from Finviz)
# -----------------------------
def get_reason_for_move(ticker):
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        news_table = soup.find("table", class_="fullview-news-outer")
        if not news_table:
            return "No recent news", []
        rows = news_table.find_all("tr")
        headlines = []
        for row in rows[:5]:
            cols = row.find_all("td")
            if len(cols) < 2:
                continue
            time_text = cols[0].text.strip()
            headline = cols[1].text.strip()
            headlines.append(f"{headline} ({time_text})")

        full_text = " ".join(headlines).lower()
        if "fda" in full_text or "approval" in full_text:
            reason = "FDA Approval or Clinical Results"
        elif "beats" in full_text or "earnings" in full_text:
            reason = "Earnings Beat"
        elif "upgrade" in full_text or "initiated" in full_text:
            reason = "Analyst Upgrade"
        elif "merger" in full_text or "acquire" in full_text:
            reason = "Merger or Acquisition"
        elif "contract" in full_text or "deal" in full_text:
            reason = "New Contract"
        elif "lawsuit" in full_text or "sec" in full_text:
            reason = "Legal/Regulatory"
        elif "offering" in full_text or "dilution" in full_text:
            reason = "Share Offering"
        else:
            reason = "News-driven move"

        return reason, headlines
    except Exception as e:
        return f"Error: {str(e)}", []

# -----------------------------
# 🚀 Streamlit App
# -----------------------------
st.set_page_config(page_title="Momentum Gap Scanner", layout="wide")
st.title("📈 Momentum Gap Scanner – Powered by AI")

if st.button("🔄 Refresh Premarket Data"):
    st.rerun()

df, error = get_premarket_data()

if error:
    st.error(error)
elif df is not None and not df.empty:
    st.success(f"✅ Found {len(df)} qualifying gappers")

    st.subheader("📊 Summary Table")
    st.dataframe(df)

    st.subheader("Top Gappers with Reason for Move")
    for i, row in df.iterrows():
        with st.expander(f"🔎 {row['Symbol']} | {row['Name']} | {row['% Change']}%"):
            st.write(f"💵 Price: ${row['Price']}")
            st.write(f"📊 Volume: {row['Volume']:,}")
            st.write(f"🧮 Float: {row['Float']:,}")
            reason, headlines = get_reason_for_move(row['Symbol'])
            st.write(f"📢 Reason for Move: {reason}")
            if headlines:
                st.markdown("**📰 Latest Headlines:**")
                for h in headlines:
                    st.write(f"- {h}")
else:
    st.warning("No stocks met the criteria today.")
