#!/usr/bin/env python3
"""
Combined Short Selling Report for Telegram
Generates a nicely formatted report with:
1. Top 20 SFC Aggregate Short Positions (weekly data)
2. Top 20 HKEX Daily Short Selling Turnover
"""

import sys
import json
from datetime import datetime, timezone

# Import from local modules
from sfc_short_positions import fetch_short_positions, get_top_shorted_stocks, get_top_by_short_ratio
from hkex_short_selling import fetch_short_selling_data, add_float_data
from stock_names import get_chinese_name


def format_number(n: int) -> str:
    """Format large numbers with B/M suffix"""
    if n >= 1e9:
        return f"{n/1e9:.2f}B"
    elif n >= 1e6:
        return f"{n/1e6:.1f}M"
    elif n >= 1e3:
        return f"{n/1e3:.1f}K"
    return str(n)


def generate_telegram_report(top_n: int = 20, include_daily: bool = True, include_aggregate: bool = True) -> str:
    """Generate a beautifully formatted Telegram report"""
    
    lines = []
    now_hkt = datetime.now(timezone.utc)
    date_str = now_hkt.strftime('%Y-%m-%d')
    
    lines.append(f"📊 **港股沽空報告** ({date_str})")
    lines.append("")
    
    # Section 1: SFC Aggregate Positions (Weekly)
    if include_aggregate:
        try:
            print("Fetching SFC aggregate short positions...", file=sys.stderr)
            sfc_df = fetch_short_positions()
            
            # Get report date from data
            report_date = sfc_df['fetch_date'].iloc[0] if 'fetch_date' in sfc_df.columns else date_str
            
            lines.append(f"🏦 **累計沽空倉位 Top {top_n}** (SFC {report_date})")
            lines.append("```")
            lines.append(f"{'#':>2} {'代碼':<5} {'名稱':<12} {'沽空額':>8} {'%流通':>6}")
            lines.append("─" * 40)
            
            top_stocks = get_top_shorted_stocks(sfc_df, top_n, include_float=True)
            
            for i, stock in enumerate(top_stocks, 1):
                code = stock['stock_code']
                name = stock['stock_name'][:10]
                value = format_number(stock['short_value_hkd'])
                pct = f"{stock.get('short_pct_of_float', 0):.1f}%" if stock.get('short_pct_of_float') else "—"
                lines.append(f"{i:2}. {code:<5} {name:<12} {value:>8} {pct:>6}")
            
            lines.append("```")
            lines.append("")
            
        except Exception as e:
            print(f"Error fetching SFC data: {e}", file=sys.stderr)
            lines.append("⚠️ SFC 數據暫時無法取得")
            lines.append("")
    
    # Section 2: HKEX Daily Short Selling
    if include_daily:
        try:
            print("Fetching HKEX daily short selling...", file=sys.stderr)
            hkex_df = fetch_short_selling_data()
            
            if not hkex_df.empty:
                trading_date = hkex_df['trading_date'].iloc[0] if 'trading_date' in hkex_df.columns else date_str
                
                lines.append(f"📉 **今日沽空成交 Top {top_n}** (HKEX {trading_date})")
                lines.append("```")
                lines.append(f"{'#':>2} {'代碼':<5} {'名稱':<12} {'沽空額':>8} {'%流通':>6}")
                lines.append("─" * 40)
                
                # Get top by value and add float data
                top_df = hkex_df.nlargest(top_n, 'short_turnover_hkd')
                top_df = add_float_data(top_df)
                
                for i, (_, row) in enumerate(top_df.iterrows(), 1):
                    code = row['stock_code']
                    name = row['stock_name'][:10]
                    value = format_number(row['short_turnover_hkd'])
                    pct = f"{row.get('daily_turnover_pct_of_float', 0):.2f}%" if row.get('daily_turnover_pct_of_float') else "—"
                    lines.append(f"{i:2}. {code:<5} {name:<12} {value:>8} {pct:>6}")
                
                lines.append("```")
                lines.append("")
            else:
                lines.append("⚠️ HKEX 今日數據暫未發布")
                lines.append("")
                
        except Exception as e:
            print(f"Error fetching HKEX data: {e}", file=sys.stderr)
            lines.append("⚠️ HKEX 數據暫時無法取得")
            lines.append("")
    
    # Footer
    lines.append("─────────────────────")
    lines.append("💡 沽空額 = 沽空金額 | %流通 = 佔流通股比例")
    lines.append("📌 SFC = 累計申報倉位 | HKEX = 當日成交")
    
    return "\n".join(lines)


def generate_telegram_report_v2(top_n: int = 20) -> str:
    """Alternative format with emoji bullets - cleaner for mobile"""
    
    lines = []
    now_hkt = datetime.now(timezone.utc)
    date_str = now_hkt.strftime('%Y-%m-%d')
    
    lines.append(f"📊 **港股沽空報告**")
    lines.append(f"📅 {date_str}")
    lines.append("")
    
    # Section 1: SFC Aggregate Positions - Ranked by % of Float
    try:
        print("Fetching SFC aggregate short positions...", file=sys.stderr)
        sfc_df = fetch_short_positions()
        report_date = sfc_df['fetch_date'].iloc[0] if 'fetch_date' in sfc_df.columns else date_str
        
        lines.append(f"🏦 **累計沽空倉位** (SFC截至{report_date})")
        lines.append("📐 按%流通股排名")
        lines.append("")
        
        # Get top 50 by value first (faster), then sort by % of float
        top_by_value = get_top_shorted_stocks(sfc_df, 50, include_float=True)
        # Filter to those with valid float data and sort by %
        top_stocks = sorted(
            [s for s in top_by_value if s.get('short_pct_of_float', 0) > 0],
            key=lambda x: x.get('short_pct_of_float', 0),
            reverse=True
        )[:top_n]
        
        for i, stock in enumerate(top_stocks, 1):
            code = stock['stock_code']
            # Get Chinese name
            name = get_chinese_name(code)
            if len(name) > 6:
                name = name[:6]
            value_b = stock['short_value_hkd'] / 1e9
            pct = stock.get('short_pct_of_float', 0)
            
            # Use different markers for top 5
            if i <= 3:
                marker = ["🥇", "🥈", "🥉"][i-1]
            elif i <= 5:
                marker = "🔥"
            else:
                marker = "•"
            
            pct_str = f"{pct:.1f}%" if pct else "—"
            lines.append(f"{marker} **{code}** {name} — {pct_str} (${value_b:.1f}B)")
        
        lines.append("")
        
    except Exception as e:
        print(f"Error fetching SFC data: {e}", file=sys.stderr)
        lines.append("⚠️ SFC 數據暫時無法取得")
        lines.append("")
    
    # Section 2: HKEX Daily - Ranked by % of Float
    try:
        print("Fetching HKEX daily short selling...", file=sys.stderr)
        hkex_df = fetch_short_selling_data()
        
        if not hkex_df.empty:
            trading_date = hkex_df['trading_date'].iloc[0] if 'trading_date' in hkex_df.columns else "今日"
            
            lines.append(f"📉 **今日沽空成交** (HKEX {trading_date})")
            lines.append("📐 按%流通股排名")
            lines.append("")
            
            # First filter to top 50 by value to limit API calls, then add float data
            top_by_value = hkex_df.nlargest(50, 'short_turnover_hkd')
            top_df = add_float_data(top_by_value)
            
            # Sort by % of float (exclude NaN/zero)
            import math
            valid_rows = []
            for _, row in top_df.iterrows():
                pct = row.get('daily_turnover_pct_of_float', 0)
                if pct and not math.isnan(pct) and pct > 0:
                    valid_rows.append(row)
            
            # Sort by % descending and take top N
            valid_rows.sort(key=lambda x: x.get('daily_turnover_pct_of_float', 0), reverse=True)
            top_sorted = valid_rows[:top_n]
            
            for i, row in enumerate(top_sorted, 1):
                code = row['stock_code']
                # Get Chinese name
                name = get_chinese_name(code)
                if len(name) > 6:
                    name = name[:6]
                value_m = row['short_turnover_hkd'] / 1e6
                pct = row.get('daily_turnover_pct_of_float', 0)
                
                if i <= 3:
                    marker = ["🥇", "🥈", "🥉"][i-1]
                elif i <= 5:
                    marker = "🔥"
                else:
                    marker = "•"
                
                pct_str = f"{pct:.2f}%"
                lines.append(f"{marker} **{code}** {name} — {pct_str} (${value_m:.0f}M)")
            
            lines.append("")
        else:
            lines.append("⚠️ HKEX 今日數據暫未發布")
            lines.append("")
            
    except Exception as e:
        print(f"Error fetching HKEX data: {e}", file=sys.stderr)
        lines.append("⚠️ HKEX 數據暫時無法取得")
        lines.append("")
    
    # Footer
    lines.append("───")
    lines.append("💡 按%流通股排名 | 括號內為沽空金額")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Short Selling Report')
    parser.add_argument('--top', '-t', type=int, default=20, help='Top N stocks (default: 20)')
    parser.add_argument('--format', '-f', choices=['v1', 'v2'], default='v2', help='Output format')
    parser.add_argument('--daily-only', action='store_true', help='Only show daily data')
    parser.add_argument('--aggregate-only', action='store_true', help='Only show aggregate data')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    args = parser.parse_args()
    
    if args.format == 'v1':
        report = generate_telegram_report(
            top_n=args.top,
            include_daily=not args.aggregate_only,
            include_aggregate=not args.daily_only
        )
    else:
        report = generate_telegram_report_v2(top_n=args.top)
    
    if args.json:
        print(json.dumps({"report": report}, ensure_ascii=False))
    else:
        print(report)
