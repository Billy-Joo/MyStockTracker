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
    required_cols = ['Quantity', 'AvgPrice', 'CurrentValue', 'InvestedAmount', 'ProfitLoss', 'DailyChange', 'DailyChangeRate', 'PeriodChangeRate']
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = df[col].apply(dm.clean_numeric)

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

    # --- Portfolio Table Header & Controls ---
    h_col1, h_col2, h_col3 = st.columns([3, 1.5, 2])
    with h_col1:
        st.subheader("📋 My Holdings")
    with h_col2:
        edit_mode = st.toggle("Enable Editing")
    with h_col3:
        show_stock_detail = st.toggle("🔍 개별 종목 상세/차트 보기", value=False, help="선택한 종목의 삭제 기능 및 1개월/1년 주가 차트를 표시합니다.")

    event = None
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
        
        event = st.dataframe(
            styled_df,
            column_order=["Account", "Name", "Ticker", "Quantity", "AvgPrice", "CurrentPrice", "DailyChange", "DailyChangeRate", "PeriodChangeRate", "CurrentValue", "InvestedAmount", "ProfitLoss", "ReturnRate"],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="portfolio_grid_select"
        )

    # --- Selected Stock Detail & Actions (Only rendered if show_stock_detail is ON) ---
    if show_stock_detail and not df.empty:
        st.markdown("---")
        st.subheader("🎯 개별 종목 상세 관리 및 주가 분석")
        st.caption("💡 위의 **보유 종목 표(그리드)에서 원하는 종목 행을 직접 클릭**하시거나, 아래 드롭다운에서 선택하면 삭제 및 1개월/1년 주가 변화를 바로 확인하실 수 있습니다.")
        
        stock_options = [f"{row['Name']} ({row['Ticker']}) | 계좌: {row['Account']}" for _, row in df.iterrows()]
        
        # Check if user clicked a row in the grid table
        if event and hasattr(event, "selection") and event.selection and "rows" in event.selection and len(event.selection["rows"]) > 0:
            grid_row_idx = event.selection["rows"][0]
            if 0 <= grid_row_idx < len(df):
                clicked_stock_str = stock_options[grid_row_idx]
                if st.session_state.get("prev_grid_selection") != grid_row_idx or st.session_state.get("selected_stock_item") != clicked_stock_str:
                    st.session_state["prev_grid_selection"] = grid_row_idx
                    st.session_state["selected_stock_item"] = clicked_stock_str

        # Fallback if session state is missing or out of sync
        if "selected_stock_item" not in st.session_state or st.session_state["selected_stock_item"] not in stock_options:
            st.session_state["selected_stock_item"] = stock_options[0]
        
        selected_stock_str = st.selectbox(
            "선택된 종목 (위 표에서 클릭한 종목이 자동 반영됩니다):", 
            stock_options, 
            key="selected_stock_item"
        )
        
        if selected_stock_str and selected_stock_str in stock_options:
            sel_idx = stock_options.index(selected_stock_str)
            selected_row = df.iloc[sel_idx]
            sel_name = selected_row['Name']
            sel_ticker = str(selected_row['Ticker']).zfill(6)
            sel_account = selected_row['Account']
            
            detail_col1, detail_col2 = st.columns([1, 2])
            
            with detail_col1:
                st.markdown(f"### 📌 {sel_name}")
                st.write(f"- **티커(종목코드)**: `{sel_ticker}`")
                st.write(f"- **증권 계좌**: `{sel_account}`")
                st.write(f"- **보유 수량**: `{selected_row['Quantity']:,.0f} 주`")
                st.write(f"- **평균 매수가**: `{selected_row['AvgPrice']:,.0f} 원`")
                st.write(f"- **현재가**: `{selected_row['CurrentPrice']:,.0f} 원`")
                st.write(f"- **평가 금액**: `{selected_row['CurrentValue']:,.0f} 원`")
                
                # Delete Stock Functionality
                st.markdown("#### 🗑️ 종목 삭제")
                st.write("선택한 종목을 포트폴리오에서 삭제합니다.")
                if st.button(f"'{sel_name}' ({sel_account}) 삭제하기", type="primary", key="btn_delete_selected"):
                    new_portfolio = st.session_state.portfolio[
                        ~((st.session_state.portfolio['Name'] == sel_name) & 
                          (st.session_state.portfolio['Ticker'] == sel_ticker) & 
                          (st.session_state.portfolio['Account'] == sel_account))
                    ]
                    st.session_state.portfolio = new_portfolio
                    dm.save_portfolio(st.session_state.portfolio)
                    st.success(f"'{sel_name}' ({sel_account}) 종목이 삭제되었습니다!")
                    st.rerun()
                    
            with detail_col2:
                st.markdown("#### 📈 주가 변화 추이 (1개월 / 1년)")
                period_tab1, period_tab2 = st.tabs(["1개월 변화", "1년 변화"])
                
                for period_key, current_tab in [("1m", period_tab1), ("1y", period_tab2)]:
                    with current_tab:
                        with st.spinner("주가 차트 불러오는 중..."):
                            stock_hist_df = dm.get_stock_price_history(sel_ticker, period=period_key)
                            
                        if not stock_hist_df.empty and 'Close' in stock_hist_df.columns:
                            fig_stock = px.line(
                                stock_hist_df, 
                                x='Date', 
                                y='Close', 
                                title=f"{sel_name} ({sel_ticker}) {'1개월' if period_key=='1m' else '1년'} 주가 흐름",
                                labels={'Close': '종가 (원)', 'Date': '날짜'}
                            )
                            fig_stock.update_traces(line_color='#e74c3c' if period_key=='1m' else '#2980b9', line_width=2)
                            fig_stock.update_layout(hovermode="x unified", height=320)
                            st.plotly_chart(fig_stock, use_container_width=True)
                            
                            start_price = stock_hist_df.iloc[0]['Close']
                            end_price = stock_hist_df.iloc[-1]['Close']
                            max_price = stock_hist_df['Close'].max()
                            min_price = stock_hist_df['Close'].min()
                            period_change = end_price - start_price
                            period_pct = (period_change / start_price * 100) if start_price != 0 else 0
                            
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("시작가", f"{start_price:,.0f}원")
                            c2.metric("최신가", f"{end_price:,.0f}원", delta=f"{period_pct:+.2f}%")
                            c3.metric("최고가", f"{max_price:,.0f}원")
                            c4.metric("최저가", f"{min_price:,.0f}원")
                        else:
                            st.info("주가 변동 데이터를 불러올 수 없습니다.")



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
