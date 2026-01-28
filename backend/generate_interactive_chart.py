#!/usr/bin/env python3
"""
Generate INTERACTIVE candlestick chart with Plotly
Uses CDN for plotly.js (~50KB instead of 4.7MB)
"""

import os
import sys
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def calculate_volume_profile(data: pd.DataFrame, num_bins: int = 30) -> tuple:
    """
    Calculate Volume Profile data
    
    Returns:
        price_levels: array of price levels
        volumes: volume at each price level
        poc: Point of Control (highest volume price)
        vah: Value Area High
        val: Value Area Low
    """
    price_min = data['Low'].min()
    price_max = data['High'].max()
    bin_size = (price_max - price_min) / num_bins
    
    price_levels = []
    volumes = []
    
    for i in range(num_bins):
        bin_low = price_min + (i * bin_size)
        bin_high = bin_low + bin_size
        bin_mid = (bin_low + bin_high) / 2
        price_levels.append(bin_mid)
        
        vol = 0
        for idx, row in data.iterrows():
            if row['High'] >= bin_low and row['Low'] <= bin_high:
                candle_range = row['High'] - row['Low'] if row['High'] > row['Low'] else 1
                overlap_low = max(row['Low'], bin_low)
                overlap_high = min(row['High'], bin_high)
                overlap_pct = (overlap_high - overlap_low) / candle_range
                vol += row['Volume'] * overlap_pct
        volumes.append(vol)
    
    max_vol_idx = np.argmax(volumes)
    poc = price_levels[max_vol_idx]
    
    total_vol = sum(volumes)
    target_vol = total_vol * 0.70
    
    accumulated = volumes[max_vol_idx]
    lower_idx = max_vol_idx
    upper_idx = max_vol_idx
    
    while accumulated < target_vol:
        lower_vol = volumes[lower_idx - 1] if lower_idx > 0 else 0
        upper_vol = volumes[upper_idx + 1] if upper_idx < len(volumes) - 1 else 0
        
        if lower_vol >= upper_vol and lower_idx > 0:
            lower_idx -= 1
            accumulated += lower_vol
        elif upper_idx < len(volumes) - 1:
            upper_idx += 1
            accumulated += upper_vol
        else:
            break
    
    val = price_levels[lower_idx]
    vah = price_levels[upper_idx]
    
    return np.array(price_levels), np.array(volumes), poc, vah, val


def generate_interactive_chart(symbol: str, market: str = 'HK', 
                                output_dir: str = '/root/clawd/research/charts',
                                use_cdn: bool = True) -> str:
    """
    Generate an interactive Plotly candlestick chart with EMAs and Volume Profile
    
    Args:
        symbol: Stock symbol (e.g., "0700", "AAPL")
        market: Market (HK, US)
        output_dir: Directory to save the chart
        use_cdn: If True, use CDN for plotly.js (~50KB). If False, embed full library (~4.7MB)
        
    Returns:
        Path to the generated HTML file
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Format symbol for Yahoo Finance
    if market.upper() == 'HK':
        clean_symbol = symbol.replace('.HK', '')
        yf_symbol = f"{clean_symbol.zfill(4)}.HK"
    else:
        yf_symbol = symbol
    
    print(f"📊 Generating interactive chart for {yf_symbol}...")
    
    # Fetch 2 years of data for EMA200 calculation
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=730)
        full_data = yf.download(yf_symbol, start=start_date, end=end_date, interval='1d', progress=False)
        
        if full_data.empty:
            print(f"❌ No data found for {yf_symbol}")
            return None
        
        # Flatten multi-index columns if present
        if isinstance(full_data.columns, pd.MultiIndex):
            full_data.columns = full_data.columns.get_level_values(0)
            
    except Exception as e:
        print(f"❌ Failed to fetch data: {e}")
        return None
    
    # Calculate EMAs on full data
    full_data['EMA10'] = full_data['Close'].ewm(span=10, adjust=False).mean()
    full_data['EMA20'] = full_data['Close'].ewm(span=20, adjust=False).mean()
    full_data['EMA60'] = full_data['Close'].ewm(span=60, adjust=False).mean()
    full_data['EMA200'] = full_data['Close'].ewm(span=200, adjust=False).mean()
    
    # Use last 6 months for display
    display_days = 126
    data = full_data.tail(display_days).copy()
    data = data.reset_index()
    data['Date'] = pd.to_datetime(data['Date'])
    
    print(f"📊 Displaying {len(data)} days, EMAs from {len(full_data)} days")
    
    # Get stock info
    try:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info
        name = info.get('shortName', info.get('longName', yf_symbol))
    except:
        name = yf_symbol
    
    # Current price info
    current_price = data['Close'].iloc[-1]
    prev_close = data['Close'].iloc[-2] if len(data) > 1 else current_price
    change = current_price - prev_close
    change_pct = (change / prev_close) * 100
    
    # Calculate Volume Profile
    current_year = datetime.now().year
    ytd_start = f"{current_year}-01-01"
    ytd_data = data[data['Date'] >= ytd_start]
    if len(ytd_data) < 10:
        ytd_data = data.tail(126)
    
    price_levels, volumes, poc, vah, val = calculate_volume_profile(ytd_data)
    
    # Create subplots: price chart + volume
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.8, 0.2],
        subplot_titles=(None, None)
    )
    
    # Candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=data['Date'],
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name='Price',
            increasing_line_color='#26A69A',
            decreasing_line_color='#EF5350',
            increasing_fillcolor='#26A69A',
            decreasing_fillcolor='#EF5350',
        ),
        row=1, col=1
    )
    
    # EMAs - blue tones with increasing width
    ema_configs = [
        ('EMA10', '#87CEEB', 1),    # Light sky blue
        ('EMA20', '#4169E1', 1.5),  # Royal blue
        ('EMA60', '#0066CC', 2),    # Medium blue
        ('EMA200', '#00008B', 3),   # Deep navy
    ]
    
    for ema_name, color, width in ema_configs:
        fig.add_trace(
            go.Scatter(
                x=data['Date'],
                y=data[ema_name],
                mode='lines',
                name=ema_name,
                line=dict(color=color, width=width),
                hovertemplate=f'{ema_name}: %{{y:.2f}}<extra></extra>'
            ),
            row=1, col=1
        )
    
    # Volume Profile lines
    # PoC - Point of Control
    fig.add_hline(
        y=poc, line_dash="solid", line_color="#FF6600", line_width=2,
        annotation_text=f"PoC {poc:.2f}", annotation_position="right",
        annotation_font_color="#FF6600", annotation_font_size=10,
        row=1, col=1
    )
    
    # VAH - Value Area High
    fig.add_hline(
        y=vah, line_dash="dash", line_color="#0066FF", line_width=1.5,
        annotation_text=f"VAH {vah:.2f}", annotation_position="right",
        annotation_font_color="#0066FF", annotation_font_size=9,
        row=1, col=1
    )
    
    # VAL - Value Area Low
    fig.add_hline(
        y=val, line_dash="dash", line_color="#0066FF", line_width=1.5,
        annotation_text=f"VAL {val:.2f}", annotation_position="right",
        annotation_font_color="#0066FF", annotation_font_size=9,
        row=1, col=1
    )
    
    # Volume bars
    colors = ['#26A69A' if data['Close'].iloc[i] >= data['Open'].iloc[i] else '#EF5350' 
              for i in range(len(data))]
    
    fig.add_trace(
        go.Bar(
            x=data['Date'],
            y=data['Volume'],
            name='Volume',
            marker_color=colors,
            opacity=0.7,
            showlegend=False
        ),
        row=2, col=1
    )
    
    # Layout
    title_text = f"{name} ({yf_symbol}) - 6M Interactive Chart"
    subtitle = f"Price: {current_price:.2f} ({change:+.2f}, {change_pct:+.2f}%)"
    
    fig.update_layout(
        title=dict(
            text=f"{title_text}<br><sup>{subtitle}</sup>",
            x=0.5,
            xanchor='center',
            font=dict(size=14)
        ),
        xaxis_rangeslider_visible=False,
        xaxis2_rangeslider_visible=False,
        template='plotly_white',
        height=480,  # Optimized height - no scrolling needed
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.8)",
            font=dict(size=10)
        ),
        hovermode='x unified',
        margin=dict(l=50, r=100, t=60, b=30),
    )
    
    # Y-axis labels
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Vol", row=2, col=1)
    
    # Hide non-trading days (weekends + find gaps in data for holidays)
    # Get all dates and find missing trading days
    all_dates = pd.date_range(start=data['Date'].min(), end=data['Date'].max(), freq='D')
    trading_dates = set(data['Date'].dt.date)
    missing_dates = [d for d in all_dates if d.date() not in trading_dates]
    
    # Convert to date values for rangebreaks
    date_breaks = [dict(values=[d]) for d in missing_dates]
    
    fig.update_xaxes(
        rangebreaks=[
            dict(bounds=["sat", "mon"]),  # Hide weekends
        ] + date_breaks  # Hide holidays/missing dates
    )
    
    # Output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"{output_dir}/{symbol}_{market}_interactive_{timestamp}.html"
    
    # Save with CDN option for smaller file size
    include_plotlyjs = 'cdn' if use_cdn else True
    fig.write_html(output_file, include_plotlyjs=include_plotlyjs)
    
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file)
        size_kb = file_size / 1024
        cdn_status = "CDN" if use_cdn else "embedded"
        print(f"✅ Interactive chart saved: {output_file}")
        print(f"📦 File size: {size_kb:.1f}KB ({cdn_status} plotly.js)")
        return output_file
    
    return None


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Interactive Stock Chart')
    parser.add_argument('symbol', help='Stock symbol (e.g., 0700, AAPL)')
    parser.add_argument('--market', '-m', default='HK', help='Market: HK or US')
    parser.add_argument('--no-cdn', action='store_true', help='Embed full plotly.js (larger file)')
    
    args = parser.parse_args()
    
    chart_path = generate_interactive_chart(
        args.symbol, 
        args.market,
        use_cdn=not args.no_cdn
    )
    
    if chart_path:
        print(f"\n📈 Interactive Chart: {chart_path}")
