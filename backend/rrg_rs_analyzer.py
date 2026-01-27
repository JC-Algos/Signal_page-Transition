#!/usr/bin/env python3
"""
RRG and Relative Strength Analyzer
Integrates RRG chart and RS ranking into stock analysis
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

# Configure Chinese font for matplotlib
import matplotlib.font_manager as fm
import os

# Find CJK font
CJK_FONT = None
font_paths = [
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',
]
for fp in font_paths:
    if os.path.exists(fp):
        CJK_FONT = fm.FontProperties(fname=fp)
        break

# Fallback: try to find any Noto CJK font
if CJK_FONT is None:
    for font in fm.findSystemFonts():
        if 'NotoSansCJK' in font or 'NotoCJK' in font:
            CJK_FONT = fm.FontProperties(fname=font)
            break

matplotlib.rcParams['axes.unicode_minus'] = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import baskets from RS.py
US_SYMBOLS = [
    '^GSPC', '^NDX', 'AAPL', 'ABBV', 'ABNB', 'ADBE', 'ADI', 'ADSK', 'AMD', 'AMGN',
    'AMZN', 'ANET', 'APA', 'APH', 'APP', 'ARM', 'ASML', 'AVGO', 'BAC', 'BKR',
    'BMNR', 'CB', 'CCL', 'CDNS', 'CEG', 'CME', 'COIN', 'CRM', 'CRWD', 'DDOG',
    'DLTR', 'DXCM', 'EOSE', 'EQIX', 'EXPE', 'FCX', 'FTNT', 'FUTU', 'GDX', 'GEV', 'GE', 'GFS',
    'GILD', 'GOOG', 'GS', 'HD', 'HSY', 'IBM', 'ICE', 'IDXX', 'INTC', 'INTU',
    'ISRG', 'J', 'JNJ', 'JPM', 'KLAC', 'KO', 'LLY', 'LMT', 'LOW', 'LRCX',
    'LULU', 'MA', 'MDB', 'META', 'MMM', 'MRK', 'MRVL', 'MS', 'MSFT', 'MSTR',
    'MU', 'NBIS', 'NEE', 'NET', 'NFLX', 'NOW', 'NRG', 'NVDA', 'NVO', 'OKLO',
    'OKTA', 'ON', 'ORCL', 'OXY', 'PANW', 'PDD', 'PEP', 'PFE', 'PGR', 'PLTR',
    'PYPL', 'QBTS', 'QCOM', 'QQQ', 'RKLB', 'SBUX', 'SHOP', 'SMCI', 'SMH', 'SMR',
    'SNOW', 'SNPS', 'TEAM', 'TER', 'TGT', 'TMO', 'TMUS', 'TSLA', 'TSM', 'TTD',
    'TTWO', 'TWLO', 'ULTA', 'UNH', 'UPS', 'V', 'VST', 'VZ', 'WDAY', 'XLB',
    'XLE', 'XLF', 'XLI', 'XLK', 'XLP', 'XLRE', 'XLU', 'XLV', 'XLY', 'XOM',
    'YUM', 'ZS'
]

HK_SYMBOLS = [
    '^HSI', '0001.HK', '0003.HK', '0005.HK', '0006.HK', '0011.HK', '0012.HK', '0016.HK', '0017.HK', '0019.HK',
    '0020.HK', '0027.HK', '0066.HK', '0175.HK', '0241.HK', '0267.HK', '0268.HK', '0285.HK', '0288.HK', '0291.HK',
    '0293.HK', '0300.HK', '0358.HK', '0386.HK', '0388.HK', '0390.HK', '0522.HK', '0669.HK', '0688.HK', '0700.HK', '0762.HK',
    '0763.HK', '0772.HK', '0799.HK', '0823.HK', '0836.HK', '0853.HK', '0857.HK', '0868.HK', '0883.HK', '0909.HK',
    '0914.HK', '0916.HK', '0939.HK', '0941.HK', '0960.HK', '0968.HK', '0981.HK', '0991.HK', '0992.HK', '1024.HK',
    '1038.HK', '1044.HK', '1072.HK', '1093.HK', '1109.HK', '1113.HK', '1133.HK', '1177.HK', '1211.HK', '1299.HK',
    '1316.HK', '1347.HK', '1378.HK', '1398.HK', '1772.HK', '1776.HK', '1787.HK', '1800.HK', '1801.HK', '1810.HK',
    '1818.HK', '1833.HK', '1860.HK', '1876.HK', '1898.HK', '1928.HK', '1929.HK', '1951.HK', '1997.HK', '2007.HK',
    '2013.HK', '2015.HK', '2018.HK', '2208.HK', '2233.HK', '2238.HK', '2252.HK', '2269.HK', '2313.HK', '2318.HK',
    '2319.HK', '2331.HK', '2333.HK', '2382.HK', '2388.HK', '2400.HK', '2498.HK', '2511.HK', '2518.HK', '2522.HK',
    '2533.HK', '2600.HK', '2601.HK', '2628.HK', '2643.HK', '2727.HK', '3690.HK', '3750.HK', '3888.HK', '3968.HK',
    '3988.HK', '6060.HK', '6078.HK', '6098.HK', '6618.HK', '6655.HK', '6681.HK', '6682.HK', '6690.HK', '6699.HK',
    '6862.HK', '6869.HK', '9618.HK', '9626.HK', '9660.HK', '9698.HK', '9863.HK', '9868.HK', '9880.HK', '9888.HK',
    '9923.HK', '9961.HK', '9973.HK', '9988.HK', '9999.HK'
]


def calculate_ma(data, period):
    """Calculate moving average"""
    return data.rolling(window=period).mean()


def calculate_rrg_values(asset_data, benchmark_data):
    """
    Calculate RS-Ratio and RS-Momentum for RRG
    """
    sbr = asset_data / benchmark_data
    rs1 = calculate_ma(sbr, 10)
    rs2 = calculate_ma(sbr, 26)
    rs_ratio = 100 * ((rs1 - rs2) / rs2 + 1)
    rm1 = calculate_ma(rs_ratio, 1)
    rm2 = calculate_ma(rs_ratio, 4)
    rs_momentum = 100 * ((rm1 - rm2) / rm2 + 1)
    return rs_ratio, rs_momentum


def get_rrg_quadrant(rs_ratio: float, rs_momentum: float) -> str:
    """Determine RRG quadrant"""
    if rs_ratio >= 100 and rs_momentum >= 100:
        return "Leading"
    elif rs_ratio < 100 and rs_momentum >= 100:
        return "Improving"
    elif rs_ratio < 100 and rs_momentum < 100:
        return "Lagging"
    else:  # rs_ratio >= 100 and rs_momentum < 100
        return "Weakening"


def get_rrg_quadrant_zh(quadrant: str) -> str:
    """Get Chinese translation for quadrant"""
    mapping = {
        "Leading": "領先",
        "Improving": "改善中",
        "Lagging": "落後",
        "Weakening": "轉弱"
    }
    return f"{quadrant} ({mapping.get(quadrant, quadrant)})"


def generate_rrg_chart(ticker: str, market: str = 'HK', 
                       output_path: str = None, tail_length: int = 8) -> Dict:
    """
    Generate RRG chart for a single ticker against benchmark
    
    Args:
        ticker: Stock ticker
        market: 'HK' or 'US'
        output_path: Path to save chart
        tail_length: Number of weeks for trail
    
    Returns:
        Dict with RRG data and chart path
    """
    try:
        # Set benchmark based on market
        if market.upper() == 'HK':
            benchmark = '^HSI'
            if not ticker.endswith('.HK'):
                ticker = f"{ticker.zfill(4)}.HK"
        else:
            benchmark = '^GSPC'
        
        # Fetch data (weekly, 100 weeks)
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=100)
        
        tickers_to_fetch = [ticker, benchmark]
        data = yf.download(tickers_to_fetch, start=start_date, end=end_date, progress=False)['Close']
        
        if isinstance(data, pd.Series):
            data = data.to_frame(name=ticker)
        
        # Resample to weekly
        data = data.resample('W-FRI').last().ffill(limit=5)
        
        if benchmark not in data.columns or ticker not in data.columns:
            return {'success': False, 'error': f'Data not available for {ticker} or {benchmark}'}
        
        benchmark_data = data[benchmark]
        asset_data = data[ticker]
        
        # Calculate RRG values
        rs_ratio, rs_momentum = calculate_rrg_values(asset_data, benchmark_data)
        
        # Get trail data
        trail_data = []
        for i in range(-tail_length, 1):
            if i < -len(rs_ratio):
                continue
            if pd.notna(rs_ratio.iloc[i]) and pd.notna(rs_momentum.iloc[i]):
                trail_data.append({
                    'date': data.index[i].strftime('%Y-%m-%d'),
                    'rs_ratio': round(float(rs_ratio.iloc[i]), 2),
                    'rs_momentum': round(float(rs_momentum.iloc[i]), 2)
                })
        
        current_rs_ratio = round(float(rs_ratio.iloc[-1]), 2)
        current_rs_momentum = round(float(rs_momentum.iloc[-1]), 2)
        quadrant = get_rrg_quadrant(current_rs_ratio, current_rs_momentum)
        
        # Generate chart
        if output_path:
            fig, ax = plt.subplots(figsize=(10, 10))
            
            # Plot trail data
            ratios = [t['rs_ratio'] for t in trail_data]
            momentums = [t['rs_momentum'] for t in trail_data]
            
            # Calculate axis limits - ensure 100 is center and all quadrants visible
            # Extend range to include data but ensure quadrants are fully colored
            data_x_min, data_x_max = min(ratios), max(ratios)
            data_y_min, data_y_max = min(momentums), max(momentums)
            
            # Calculate how far data extends from 100
            x_extent = max(abs(data_x_min - 100), abs(data_x_max - 100), 10)  # min 10 units
            y_extent = max(abs(data_y_min - 100), abs(data_y_max - 100), 10)  # min 10 units
            
            # Use same extent for both axes to keep square quadrants, add margin
            extent = max(x_extent, y_extent) + 2
            
            x_min, x_max = 100 - extent, 100 + extent
            y_min, y_max = 100 - extent, 100 + extent
            
            # Color all four quadrants fully within the visible range
            ax.fill_between([x_min, 100], 100, y_max, alpha=0.2, color='lightblue', label='Improving')
            ax.fill_between([100, x_max], 100, y_max, alpha=0.2, color='lightgreen', label='Leading')
            ax.fill_between([x_min, 100], y_min, 100, alpha=0.2, color='lightcoral', label='Lagging')
            ax.fill_between([100, x_max], y_min, 100, alpha=0.2, color='lightyellow', label='Weakening')
            
            # Draw center axes at 100
            ax.axhline(y=100, color='black', linestyle='-', linewidth=1.5, zorder=3)
            ax.axvline(x=100, color='black', linestyle='-', linewidth=1.5, zorder=3)
            
            # Trail line with gradient
            for i in range(len(ratios) - 1):
                alpha = 0.3 + (i / len(ratios)) * 0.7
                ax.plot(ratios[i:i+2], momentums[i:i+2], 'o-', 
                       color='darkblue', alpha=alpha, linewidth=2, markersize=4)
            
            # Current position (larger marker)
            ax.scatter(ratios[-1], momentums[-1], s=200, c='darkblue', 
                      marker='o', edgecolors='white', linewidths=2, zorder=5)
            ax.annotate(ticker.replace('.HK', ''), (ratios[-1], momentums[-1]),
                       xytext=(5, 5), textcoords='offset points', fontsize=12, fontweight='bold')
            
            # Labels
            ax.set_xlabel('RS-Ratio', fontsize=12)
            ax.set_ylabel('RS-Momentum', fontsize=12)
            
            # Benchmark name
            benchmark_name = 'HSI' if benchmark == '^HSI' else 'S&P 500'
            if CJK_FONT:
                benchmark_name = '恆生指數' if benchmark == '^HSI' else '標普500指數'
                ax.set_title(f'{ticker.replace(".HK", "")} vs {benchmark_name}\nQuadrant: {quadrant}', fontsize=14, fontproperties=CJK_FONT)
            else:
                ax.set_title(f'{ticker.replace(".HK", "")} vs {benchmark_name}\nQuadrant: {quadrant}', fontsize=14)
            
            # Set axis limits centered on 100
            ax.set_xlim(x_min, x_max)
            ax.set_ylim(y_min, y_max)
            
            # Grid
            ax.grid(True, alpha=0.3)
            
            # Quadrant labels - position in the middle of each quadrant (Chinese, 2x larger)
            label_offset = extent * 0.5
            font_props = {'fontsize': 22, 'alpha': 0.7, 'fontweight': 'bold', 'ha': 'center', 'va': 'center'}
            if CJK_FONT:
                ax.text(100 + label_offset, 100 + label_offset, '領先', color='green', fontproperties=CJK_FONT, **font_props)
                ax.text(100 - label_offset, 100 + label_offset, '改善中', color='blue', fontproperties=CJK_FONT, **font_props)
                ax.text(100 - label_offset, 100 - label_offset, '落後', color='red', fontproperties=CJK_FONT, **font_props)
                ax.text(100 + label_offset, 100 - label_offset, '轉弱', color='orange', fontproperties=CJK_FONT, **font_props)
            else:
                # Fallback to English labels
                ax.text(100 + label_offset, 100 + label_offset, 'Leading', color='green', **font_props)
                ax.text(100 - label_offset, 100 + label_offset, 'Improving', color='blue', **font_props)
                ax.text(100 - label_offset, 100 - label_offset, 'Lagging', color='red', **font_props)
                ax.text(100 + label_offset, 100 - label_offset, 'Weakening', color='orange', **font_props)
            
            plt.tight_layout()
            plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
            plt.close()
        
        return {
            'success': True,
            'ticker': ticker,
            'benchmark': benchmark,
            'rs_ratio': current_rs_ratio,
            'rs_momentum': current_rs_momentum,
            'quadrant': quadrant,
            'trail': trail_data,
            'chart_path': output_path
        }
        
    except Exception as e:
        logger.error(f"Error generating RRG chart: {e}")
        return {'success': False, 'error': str(e)}


def calculate_relative_strength(close_data: pd.DataFrame, window: int, date) -> Dict:
    """Calculate relative strength scores"""
    rs_scores = {}
    data_slice = close_data.loc[:date]
    
    for symbol in data_slice.columns:
        try:
            symbol_data = data_slice[symbol]
            pct_change = symbol_data.pct_change(periods=window)
            
            if pd.isna(pct_change.iloc[-1]):
                rs_scores[symbol] = 0
                continue
            
            other_data = data_slice.drop(columns=[symbol])
            other_pct_change = other_data.pct_change(periods=window)
            
            current_val = pct_change.iloc[-1]
            others_val = other_pct_change.iloc[-1]
            
            outperformance = (current_val > others_val).sum()
            underperformance = (current_val < others_val).sum()
            
            rs_scores[symbol] = int(outperformance - underperformance)
            
        except Exception as e:
            rs_scores[symbol] = 0
    
    return rs_scores


def get_rs_ranking(ticker: str, market: str = 'HK', window: int = 10) -> Dict:
    """
    Get RS ranking for a ticker
    
    Args:
        ticker: Stock ticker
        market: 'HK' or 'US'
        window: Lookback window for RS calculation
    
    Returns:
        Dict with ranking info for current and historical
    """
    try:
        # Select basket
        if market.upper() == 'HK':
            basket = HK_SYMBOLS.copy()
            if not ticker.endswith('.HK'):
                ticker = f"{ticker.zfill(4)}.HK"
        else:
            basket = US_SYMBOLS.copy()
        
        # Add ticker if not in basket
        ticker_in_basket = ticker in basket or ticker.upper() in [s.upper() for s in basket]
        if not ticker_in_basket:
            basket.append(ticker)
            logger.info(f"Added {ticker} to basket (not originally in list)")
        
        # Fetch data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        data = yf.download(basket, start=start_date, end=end_date, progress=False)
        
        if data.empty:
            return {'success': False, 'error': 'No data available'}
        
        close_data = data['Close'] if 'Close' in data.columns else data
        
        # Remove columns with all NaN
        close_data = close_data.dropna(axis=1, how='all')
        
        if ticker not in close_data.columns:
            return {'success': False, 'error': f'{ticker} data not available'}
        
        # Calculate RS for multiple dates
        current_date = close_data.index[-1]
        dates_back = [0, 1, 2, 5, 10]  # Current, 1d, 2d, 5d, 10d ago
        
        rankings = {}
        for days_back in dates_back:
            date_idx = max(0, len(close_data) - 1 - days_back)
            date = close_data.index[date_idx]
            
            rs_scores = calculate_relative_strength(close_data, window, date)
            
            # Sort and get ranking
            sorted_scores = sorted(rs_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Find ticker's position
            ticker_rank = None
            ticker_score = None
            for rank, (sym, score) in enumerate(sorted_scores, 1):
                if sym.upper() == ticker.upper():
                    ticker_rank = rank
                    ticker_score = score
                    break
            
            label = 'current' if days_back == 0 else f'{days_back}d_ago'
            rankings[label] = {
                'date': date.strftime('%Y-%m-%d'),
                'rank': ticker_rank,
                'score': ticker_score,
                'total_stocks': len(sorted_scores)
            }
        
        # Calculate rank changes
        current_rank = rankings['current']['rank']
        rank_changes = {}
        for period in ['1d_ago', '2d_ago', '5d_ago', '10d_ago']:
            if period in rankings and rankings[period]['rank']:
                change = rankings[period]['rank'] - current_rank  # Positive = improved
                rank_changes[period] = change
        
        return {
            'success': True,
            'ticker': ticker,
            'market': market,
            'in_original_basket': ticker_in_basket,
            'rankings': rankings,
            'rank_changes': rank_changes,
            'window': window
        }
        
    except Exception as e:
        logger.error(f"Error calculating RS ranking: {e}")
        return {'success': False, 'error': str(e)}


def format_rrg_report_zh(rrg_data: Dict) -> str:
    """Format RRG data as Chinese report"""
    if not rrg_data.get('success'):
        return f"⚠️ 資產輪動分析失敗: {rrg_data.get('error', '未知錯誤')}"
    
    quadrant_zh = get_rrg_quadrant_zh(rrg_data['quadrant'])
    benchmark_zh = '恆生指數' if rrg_data['benchmark'] == '^HSI' else '標普500指數'
    
    return f"""📈 **資產輪動**
• 相對強度比率: {rrg_data['rs_ratio']}
• 相對強度動能: {rrg_data['rs_momentum']}
• 象限: {quadrant_zh}
• 基準: {benchmark_zh}"""


def format_rs_report_zh(rs_data: Dict) -> str:
    """Format RS ranking data as Chinese report"""
    if not rs_data.get('success'):
        return f"⚠️ RS 排名分析失敗: {rs_data.get('error', '未知錯誤')}"
    
    rankings = rs_data['rankings']
    changes = rs_data.get('rank_changes', {})
    
    # Build ranking history table
    current = rankings['current']
    
    lines = [
        f"📊 **相對強度 (RS) 排名**",
        f"• 現時排名: #{current['rank']}/{current['total_stocks']} (分數: {current['score']})"
    ]
    
    # Historical rankings
    history = []
    for period in ['1d_ago', '2d_ago', '5d_ago', '10d_ago']:
        if period in rankings and rankings[period]['rank']:
            r = rankings[period]
            change = changes.get(period, 0)
            change_str = f"↑{change}" if change > 0 else (f"↓{abs(change)}" if change < 0 else "→")
            history.append(f"  • {period.replace('_ago', '日前')}: #{r['rank']} ({change_str})")
    
    if history:
        lines.append("• 排名變化:")
        lines.extend(history)
    
    return '\n'.join(lines)


# CLI test
if __name__ == '__main__':
    import sys
    
    ticker = sys.argv[1] if len(sys.argv) > 1 else '0700'
    market = sys.argv[2] if len(sys.argv) > 2 else 'HK'
    
    print(f"\n=== RRG Analysis for {ticker} ({market}) ===")
    rrg_result = generate_rrg_chart(ticker, market, output_path=f'/tmp/rrg_{ticker}.png')
    print(format_rrg_report_zh(rrg_result))
    
    print(f"\n=== RS Ranking for {ticker} ({market}) ===")
    rs_result = get_rs_ranking(ticker, market)
    print(format_rs_report_zh(rs_result))
