import FinanceDataReader as fdr
import pandas as pd
import os
from datetime import datetime

import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import json

# Define the name of your Google Sheet
SHEET_NAME = "MyStockData"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_gspread_client():
    if "gcp_service_account" not in st.secrets:
        st.error("Google Cloud credentials not found in secrets. Please set up `.streamlit/secrets.toml` with `[gcp_service_account]` section.")
        st.stop()
        
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    client = gspread.authorize(creds)
    return client

def get_worksheet(worksheet_name):
    client = get_gspread_client()
    try:
        sheet = client.open(SHEET_NAME)
    except gspread.SpreadsheetNotFound:
        st.error(f"Spreadsheet '{SHEET_NAME}' not found. Please create it in your Google Drive and share it with the service account email.")
        st.stop()
        
    try:
        worksheet = sheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)
    return worksheet

def clean_numeric(val):
    if pd.isna(val) or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace(',', '').replace('원', '').replace('KRW', '').replace('$', '').strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    return 0.0

def load_portfolio():
    try:
        worksheet = get_worksheet("Portfolio")
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["Account", "Name", "Ticker", "Quantity", "AvgPrice"])
        
        df = pd.DataFrame(data)
        # Ensure Ticker is string (sometimes it reads as int like 5930 instead of 005930)
        if 'Ticker' in df.columns:
            df['Ticker'] = df['Ticker'].astype(str).str.zfill(6)

        # Convert numeric columns safely
        numeric_cols = ["Quantity", "AvgPrice", "CurrentPrice", "DailyChange", "DailyChangeRate", "PeriodChangeRate", "CurrentValue", "InvestedAmount", "ProfitLoss", "ReturnRate"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].apply(clean_numeric)

        return df
    except Exception as e:
        print(f"Error loading portfolio from sheets: {e}")
        return pd.DataFrame(columns=["Account", "Name", "Ticker", "Quantity", "AvgPrice"])


def save_portfolio(df):
    try:
        worksheet = get_worksheet("Portfolio")
        worksheet.clear()
        
        # Replace NaNs with empty string for JSON serialization
        clean_df = df.fillna("")
        
        data_to_write = [clean_df.columns.values.tolist()] + clean_df.values.tolist()
        worksheet.update(values=data_to_write, range_name="A1")
    except Exception as e:
        st.error(f"Error saving portfolio to Google Sheets: {e}")


from datetime import timedelta
import concurrent.futures

def get_price_data(ticker, lookback_days=20):
    """
    Returns (current_price, previous_close, start_price_of_window)
    """
    try:
        # Fetch only recent data to speed up.
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        df = fdr.DataReader(ticker, start=start_date)
        
        if df.empty:
            return None, None, None
            
        if len(df) < 2:
            return df.iloc[-1]['Close'], df.iloc[-1]['Close'], df.iloc[0]['Close'] # Fallback
            
        current_price = df.iloc[-1]['Close']
        previous_close = df.iloc[-2]['Close']
        start_price = df.iloc[0]['Close']
        
        return current_price, previous_close, start_price
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
        return None, None, None

def fetch_price_wrapper(args):
    """Helper for parallel execution"""
    ticker, lookback_days = args
    curr, prev, start = get_price_data(ticker, lookback_days)
    return curr, prev, start

def update_portfolio_prices(portfolio_df, lookback_days=20):
    if portfolio_df.empty:
        return portfolio_df

    portfolio_df['Quantity'] = portfolio_df['Quantity'].apply(clean_numeric)
    portfolio_df['AvgPrice'] = portfolio_df['AvgPrice'].apply(clean_numeric)
    
    current_prices = []
    daily_changes = []
    daily_change_rates = []
    period_change_rates = []
    
    # Use ThreadPoolExecutor for parallel fetching
    # This significantly speeds up updates when tracking many stocks
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Map the helper function to the dataframe rows
        # We need to pass lookback_days to the wrapper, so we zip it
        tickers = portfolio_df['Ticker'].tolist()
        args = [(t, lookback_days) for t in tickers]
        results = list(executor.map(fetch_price_wrapper, args))
        
    # Unpack results
    for curr, prev, start in results:
        if curr is None:
            curr = 0
            prev = 0
            start = 0
            
        # Calculate Daily Change
        change = curr - prev
        rate = (change / prev * 100) if prev != 0 else 0
        
        # Calculate Period Change
        p_rate = ((curr - start) / start * 100) if start != 0 else 0
        
        current_prices.append(curr)
        daily_changes.append(change)
        daily_change_rates.append(rate)
        period_change_rates.append(p_rate)
        
    
    portfolio_df['CurrentPrice'] = current_prices
    portfolio_df['DailyChange'] = daily_changes
    portfolio_df['DailyChangeRate'] = daily_change_rates
    portfolio_df['PeriodChangeRate'] = period_change_rates
    
    portfolio_df['CurrentValue'] = portfolio_df['CurrentPrice'] * portfolio_df['Quantity']
    portfolio_df['InvestedAmount'] = portfolio_df['AvgPrice'] * portfolio_df['Quantity']
    portfolio_df['ProfitLoss'] = portfolio_df['CurrentValue'] - portfolio_df['InvestedAmount']
    portfolio_df['ReturnRate'] = (portfolio_df['ProfitLoss'] / portfolio_df['InvestedAmount']) * 100
    portfolio_df['ReturnRate'] = portfolio_df['ReturnRate'].fillna(0) # Handle division by zero
    
    return portfolio_df

def load_history():
    try:
        worksheet = get_worksheet("History")
        data = worksheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["Date", "Account", "TotalValue", "TotalInvested", "TotalProfit"])
            
        df = pd.DataFrame(data)
        if 'Account' not in df.columns:
            df['Account'] = 'All'

        for col in ["TotalValue", "TotalInvested", "TotalProfit"]:
            if col in df.columns:
                df[col] = df[col].apply(clean_numeric)

        return df
    except Exception as e:
        print(f"Error loading history from sheets: {e}")
        return pd.DataFrame(columns=["Date", "Account", "TotalValue", "TotalInvested", "TotalProfit"])



def save_history(portfolio_df):
    today = datetime.now().strftime("%Y-%m-%d")
    history_df = load_history()
    
    # 1. Remove existing entries for TODAY to avoid duplicates
    history_df = history_df[history_df['Date'] != today]
    
    new_rows = []
    
    # 2. Calculate totals per Account
    if not portfolio_df.empty:
        grouped = portfolio_df.groupby('Account')[['CurrentValue', 'InvestedAmount', 'ProfitLoss']].sum().reset_index()
        for _, row in grouped.iterrows():
            new_rows.append({
                "Date": today,
                "Account": row['Account'],
                "TotalValue": row['CurrentValue'],
                "TotalInvested": row['InvestedAmount'],
                "TotalProfit": row['ProfitLoss']
            })
            
    # 3. Combine and save to sheets
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        history_df = pd.concat([history_df, new_df], ignore_index=True)
        
    try:
        worksheet = get_worksheet("History")
        worksheet.clear()
        
        clean_df = history_df.fillna("")
        data_to_write = [clean_df.columns.values.tolist()] + clean_df.values.tolist()
        worksheet.update(values=data_to_write, range_name="A1")
    except Exception as e:
        st.error(f"Error saving history to Google Sheets: {e}")

def fetch_history_wrapper(args):
    """Helper to fetch full history"""
    ticker, start_date = args
    try:
        df = fdr.DataReader(ticker, start=start_date)
        return ticker, df
    except:
        return ticker, pd.DataFrame()

def get_portfolio_value_history(portfolio_df, lookback_days=20):
    """
    Calculates the daily value of the CURRENT portfolio over the last N days.
    Returns a DataFrame with columns: ['Date', 'Account', 'Value']
    """
    if portfolio_df.empty:
        return pd.DataFrame()

    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    unique_tickers = portfolio_df['Ticker'].unique()
    
    # 1. Fetch History for all tickers in parallel
    ticker_history = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        args = [(t, start_date) for t in unique_tickers]
        results = list(executor.map(fetch_history_wrapper, args))
        
    for ticker, df in results:
        if not df.empty:
            ticker_history[ticker] = df['Close']
            
    # 2. Build Daily Values
    # We want a DataFrame: Date | Account | Value
    # Iterate through portfolio items, align their history, and multiply by quantity.
    
    all_series = []
    
    for _, row in portfolio_df.iterrows():
        ticker = row['Ticker']
        qty = row['Quantity']
        account = row['Account']
        
        if ticker in ticker_history:
            # Get series, multiply by qty
            val_series = ticker_history[ticker] * qty
            
            # Convert to DF and Handle Index
            val_df = val_series.to_frame(name='Value')
            val_df.index.name = 'Date' # Ensure index is named Date
            val_df = val_df.reset_index()
            val_df['Account'] = account
            
            all_series.append(val_df)
            
    if not all_series:
        return pd.DataFrame()
        
    # Combine all
    combined_df = pd.concat(all_series)
    
    # Group by Date and Account to sum values
    # (Because one account might have multiple stocks)
    grouped = combined_df.groupby(['Date', 'Account'])['Value'].sum().reset_index()
    
    return grouped
    
def get_monthly_summary():
    history_df = load_history()
    if history_df.empty:
        return pd.DataFrame()
    
    history_df['Date'] = pd.to_datetime(history_df['Date'])
    history_df['Month'] = history_df['Date'].dt.to_period('M')
    
    # 1. Group by Date to get roughly the daily global total
    daily_totals = history_df.groupby(['Date', 'Month'])[['TotalValue', 'TotalInvested', 'TotalProfit']].sum().reset_index()
    
    # 2. Now select the last entry for each month
    monthly_summary = daily_totals.groupby('Month').last().reset_index()
    monthly_summary['Month'] = monthly_summary['Month'].astype(str)
    
    return monthly_summary

def get_stock_price_history(ticker, period='1y'):
    """
    Fetches price history for a single stock for '1m' (30 days) or '1y' (365 days).
    """
    days = 30 if period == '1m' else 365
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        df = fdr.DataReader(ticker, start=start_date)
        if df.empty:
            return pd.DataFrame()
        df = df.reset_index()
        return df
    except Exception as e:
        print(f"Error fetching stock price history for {ticker}: {e}")
        return pd.DataFrame()
