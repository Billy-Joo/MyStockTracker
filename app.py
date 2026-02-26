import sys
import os

# Add local library path to sys.path
local_lib = os.path.join(os.path.dirname(__file__), "lib")
if os.path.exists(local_lib) and local_lib not in sys.path:
    sys.path.insert(0, local_lib)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import data_manager as dm

st.set_page_config(page_title="My Stock Tracker", layout="wide")

st.title("📈 My Stock Investment Tracker")

# --- Sidebar: Portfolio Management ---
# --- Sidebar: Portfolio Management ---
st.sidebar.header("Portfolio Management")

# Initialize session state for portfolio if not exists
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = dm.load_portfolio()

# Add Stock (No Form)
st.sidebar.subheader("Add New Stock")
account = st.sidebar.text_input("Account Name", "MyAccount")
stock_name = st.sidebar.text_input("Stock Name")
ticker = st.sidebar.text_input("Ticker Symbol (e.g., 005930)")
quantity = st.sidebar.number_input("Quantity", min_value=1, value=10)
avg_price = st.sidebar.number_input("Avg Buy Price", min_value=1.0, value=10000.0)

if st.sidebar.button("Add Stock"):
    if stock_name and ticker:
        new_stock = pd.DataFrame([{
            "Account": account,
            "Name": stock_name,
            "Ticker": ticker,
            "Quantity": quantity,
            "AvgPrice": avg_price
        }])
        # Append using concat
        st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_stock], ignore_index=True)
        dm.save_portfolio(st.session_state.portfolio)
        st.success(f"Added {stock_name}!")
    else:
        st.error("Please fill in all fields.")

# Remove Stock
with st.sidebar.expander("Remove Stock"):
    if not st.session_state.portfolio.empty:
        stock_to_remove = st.selectbox("Select Stock to Remove", st.session_state.portfolio['Name'].unique())
        if st.button("Remove"):
            st.session_state.portfolio = st.session_state.portfolio[st.session_state.portfolio['Name'] != stock_to_remove]
            dm.save_portfolio(st.session_state.portfolio)
            st.success(f"Removed {stock_to_remove}!")
            st.rerun()
# --- Main Content ---


# Load Data
portfolio = st.session_state.portfolio

if portfolio.empty:
    st.info("No stocks in portfolio. Add some from the sidebar!")
else:
    # Settings (Advanced)
    with st.sidebar.expander("Settings"):
        lookback_days = st.slider("Price Fetch Window (Days)", min_value=5, max_value=365, value=20, help="Increase this if you want to see older data or ensure holidays are covered.")

    # Update Prices Button
    if st.button("🔄 Update Prices & Save History"):
        with st.spinner("Fetching latest prices..."):
            updated_portfolio = dm.update_portfolio_prices(portfolio, lookback_days=lookback_days)
            st.session_state.portfolio = updated_portfolio
            
            # Save History (Now passes the dataframe for granular saving)
            dm.save_history(updated_portfolio)
            st.success("Prices updated and detailed history saved!")

    # Display Metrics
    # Ensure columns exist even if update hasn't run
    if 'CurrentValue' not in st.session_state.portfolio.columns:
         st.session_state.portfolio = dm.update_portfolio_prices(st.session_state.portfolio, lookback_days=lookback_days)

    # --- Account Filtering ---
    accounts = sorted(portfolio['Account'].unique())
    selected_accounts = st.multiselect("Filter by Account", accounts, default=accounts)
    
    if selected_accounts:
        df = portfolio[portfolio['Account'].isin(selected_accounts)].copy()
    else:
        df = portfolio.copy()

    # Ensure necessary columns exist (handling legacy data or partial updates)
    required_cols = ['CurrentValue', 'InvestedAmount', 'ProfitLoss', 'DailyChange', 'DailyChangeRate', 'PeriodChangeRate']
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0

    # Calculate Totals
    total_value = df['CurrentValue'].sum()
    total_invested = df['InvestedAmount'].sum()
    total_profit = df['ProfitLoss'].sum()
    total_return = (total_profit / total_invested * 100) if total_invested != 0 else 0
    
    # Calculate Daily Totals (Sum of daily price changes * quantity)
    today_change_val = (df['DailyChange'] * df['Quantity']).sum()
    # Avoid division by zero
    start_val = total_value - today_change_val
    today_change_pct = (today_change_val / start_val * 100) if start_val != 0 else 0

    # Metrics Row
    st.subheader("📊 Portfolio Overview")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Asset Value", f"{total_value:,.0f} KRW", delta=f"{today_change_val:,.0f} Today")
    m2.metric("Total Invested", f"{total_invested:,.0f} KRW")
    m3.metric("Total Profit/Loss", f"{total_profit:,.0f} KRW", delta=f"{total_return:.2f}%")
    m4.metric("Daily Change", f"{today_change_val:,.0f} KRW", delta=f"{today_change_pct:.2f}%")

    # --- Portfolio Table ---
    st.subheader("📋 My Holdings")
    
    edit_mode = st.toggle("Enable Editing")

    if edit_mode:
        st.info("Edit **Quantity** and **Avg Buy Price** directly in the table below.")
        # Column configuration for formatting
        column_config = {
            "Account": st.column_config.TextColumn("Account"),
            "Name": st.column_config.TextColumn("Stock Name", disabled=True),
            "Ticker": st.column_config.TextColumn("Ticker", disabled=True),
            "Quantity": st.column_config.NumberColumn("Quantity", min_value=0, format="%d"),
            "AvgPrice": st.column_config.NumberColumn("Avg Buy Price", min_value=0, format="%d"),
            "CurrentPrice": st.column_config.NumberColumn("Current Price", format="%d", disabled=True),
            "DailyChange": st.column_config.NumberColumn("Daily Chg", format="%d", disabled=True),
            "DailyChangeRate": st.column_config.NumberColumn("Daily %", format="%.2f%%", disabled=True),
            "PeriodChangeRate": st.column_config.NumberColumn(f"Win % ({lookback_days}d)", format="%.2f%%", disabled=True),
            "CurrentValue": st.column_config.NumberColumn("Value", format="%d", disabled=True),
            "InvestedAmount": st.column_config.NumberColumn("Invested", format="%d", disabled=True),
            "ProfitLoss": st.column_config.NumberColumn("P/L", format="%d", disabled=True),
            "ReturnRate": st.column_config.NumberColumn("Return %", format="%.2f%%", disabled=True),
        }
        
        edited_df = st.data_editor(
            df,
            column_order=["Account", "Name", "Ticker", "Quantity", "AvgPrice", "CurrentPrice", "DailyChange", "DailyChangeRate", "PeriodChangeRate", "CurrentValue", "InvestedAmount", "ProfitLoss", "ReturnRate"],
            column_config=column_config,
            num_rows="dynamic",
            use_container_width=True,
            key="portfolio_editor",
            hide_index=True
        )

        if not edited_df.equals(df[edited_df.columns]):
            curr_portfolio = st.session_state.portfolio.set_index('Ticker')
            updates = edited_df.set_index('Ticker')
            curr_portfolio.update(updates)
            st.session_state.portfolio = curr_portfolio.reset_index()
            st.session_state.portfolio = dm.update_portfolio_prices(st.session_state.portfolio, lookback_days=lookback_days)
            dm.save_portfolio(st.session_state.portfolio)
            st.toast("Portfolio updated!", icon="💾")
            # Force rerun to allow switch back to View mode with updated data if desired? 
            # Not strictly necessary as data_editor updates state.
            
    else:
        # --- View Mode (Styled) ---
        # Helper for color
        def get_color(val):
            if pd.isna(val): return ''
            if val > 0: return 'color: red'
            elif val < 0: return 'color: blue'
            return ''
            
        # Helper for formatting with arrow
        def format_with_arrow(val, is_percent=False):
            if pd.isna(val): return "-"
            arrow = "▲" if val > 0 else "▼" if val < 0 else "" # No arrow for 0
            
            if is_percent:
                return f"{arrow} {abs(val):,.2f}%"
            else:
                return f"{arrow} {abs(val):,.0f}"

        # Apply styling
        # Note: st.dataframe allows display of Styler objects
        styled_df = df.style.format({
            "Quantity": "{:,.0f}",
            "AvgPrice": "{:,.0f}",
            "CurrentPrice": "{:,.0f}",
            "CurrentValue": "{:,.0f}",
            "InvestedAmount": "{:,.0f}",
            "DailyChange": lambda x: format_with_arrow(x),
            "DailyChangeRate": lambda x: format_with_arrow(x, is_percent=True),
            "PeriodChangeRate": lambda x: format_with_arrow(x, is_percent=True),
            "ProfitLoss": lambda x: format_with_arrow(x),
            "ReturnRate": lambda x: format_with_arrow(x, is_percent=True)
        }).map(get_color, subset=["DailyChange", "DailyChangeRate", "PeriodChangeRate", "ProfitLoss", "ReturnRate"])
        
        st.dataframe(
            styled_df,
            column_order=["Account", "Name", "Ticker", "Quantity", "AvgPrice", "CurrentPrice", "DailyChange", "DailyChangeRate", "PeriodChangeRate", "CurrentValue", "InvestedAmount", "ProfitLoss", "ReturnRate"],
            use_container_width=True,
            hide_index=True
        )


    # Charts
    st.subheader("Analysis")
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.write("### Portfolio Allocation")
        fig_pie = px.pie(df, values='CurrentValue', names='Name', title='Asset Allocation')
        st.plotly_chart(fig_pie, use_container_width=True)

    with chart_col2:
        st.write("### Investment vs Current Value")
        # Group by Name for bar chart
        grouped_df = df.groupby('Name')[['InvestedAmount', 'CurrentValue']].sum().reset_index()
        # melt for easy plotting
        melted_df = grouped_df.melt(id_vars='Name', value_vars=['InvestedAmount', 'CurrentValue'], var_name='Type', value_name='Value')
        fig_bar = px.bar(melted_df, x='Name', y='Value', color='Type', barmode='group', title='Cost vs Value per Stock')
        st.plotly_chart(fig_bar, use_container_width=True)

    # Historical Data Analysis
    st.subheader(f"📉 Portfolio Value Trend (Last {lookback_days} Days)")
    
    # 1. Calculated History (Simulation based on current holdings)
    with st.spinner("Calculating historical performance..."):
        # We pass the FILTERED df here, so the history is calculated only for selected accounts
        proforma_history = dm.get_portfolio_value_history(df, lookback_days)
        
    if not proforma_history.empty:
        # Sum up for Total Line
        total_history = proforma_history.groupby('Date')['Value'].sum().reset_index()
        
        # Plot
        # We can overlay Account breakdown if selected
        
        tab1, tab2 = st.tabs(["Total Trend", "By Account"])
        
        with tab1:
            fig_total = px.line(total_history, x='Date', y='Value', title=f"Total Value Trend ({', '.join(selected_accounts) if selected_accounts else 'All'})")
            st.plotly_chart(fig_total, use_container_width=True)
            
        with tab2:
            fig_account = px.line(proforma_history, x='Date', y='Value', color='Account', title="Value Trend by Account")
            st.plotly_chart(fig_account, use_container_width=True)
            
    else:
        st.warning("Could not calculate history. Ensure stock tickers are correct.")


    # Logged History (Saved Data)
    with st.expander("View Saved Log History"):
        st.write("This shows the snapshot data you explicitly saved by clicking 'Update Prices'.")
        history_df = dm.load_history()
        
        if not history_df.empty:
            if selected_accounts:
                 filtered_history = history_df[history_df['Account'].isin(selected_accounts)]
            else:
                 filtered_history = history_df
            
            chart_data = filtered_history.groupby('Date')[['TotalValue', 'TotalInvested']].sum().reset_index()
            
            if chart_data.empty:
                st.warning("No saved history for this selection.")
            else:
                st.line_chart(chart_data, x='Date', y=['TotalValue', 'TotalInvested'])
                
            st.dataframe(dm.get_monthly_summary())
        else:
            st.info("No saved history yet.")

    # Ticker Search Helper
    with st.expander("Find Ticker Symbol"):
        st.info("Search for Korean stocks to find their ticker symbol.")
        search_query = st.text_input("Search Stock Name")
        if search_query:
            try:
                krx_stocks = fdr.StockListing('KRX')
                results = krx_stocks[krx_stocks['Name'].str.contains(search_query, case=False)]
                if not results.empty:
                    st.dataframe(results[['Code', 'Name', 'Market']].head(10))
                else:
                    st.warning("No stocks found.")
            except Exception as e:
                st.error(f"Error searching stocks: {e}")

# End of file

