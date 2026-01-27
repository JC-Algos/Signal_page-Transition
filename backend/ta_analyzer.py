#!/usr/bin/env python3
"""
市場技術分析模組 - Market Technical Analysis Module
Analyzes HK and US stocks with comprehensive TA indicators
"""

import os
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

# Import RRG and RS analyzer
try:
    from rrg_rs_analyzer import generate_rrg_chart, get_rs_ranking, format_rrg_report_zh, format_rs_report_zh, get_rrg_quadrant_zh
    RRG_RS_AVAILABLE = True
except ImportError:
    RRG_RS_AVAILABLE = False

class NumpyEncoder(json.JSONEncoder):
    """Custom encoder to handle numpy types"""
    def default(self, obj):
        if isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        return super().default(obj)

class MarketAnalyzer:
    """Technical analysis for HK and US markets"""
    
    # Market suffixes
    MARKET_SUFFIX = {
        'HK': '.HK',
        'US': ''  # US stocks don't need suffix
    }
    
    def __init__(self):
        self.indicators = {}
        
    def get_symbol(self, ticker: str, market: str = 'US') -> str:
        """Convert ticker to Yahoo Finance format"""
        suffix = self.MARKET_SUFFIX.get(market.upper(), '')
        if market.upper() == 'HK' and not ticker.endswith('.HK'):
            # HK stocks need 4-digit format
            ticker = ticker.zfill(4) + suffix
        return ticker
    
    def fetch_data(self, ticker: str, market: str = 'US', period: str = '1y', interval: str = '1d') -> pd.DataFrame:
        """Fetch OHLCV data from Yahoo Finance"""
        symbol = self.get_symbol(ticker, market)
        try:
            data = yf.download(symbol, period=period, interval=interval, progress=False)
            if data.empty:
                raise ValueError(f"No data found for {symbol}")
            # Flatten multi-index columns if present
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            return data
        except Exception as e:
            raise ValueError(f"Failed to fetch {symbol}: {str(e)}")
    
    def calculate_emas(self, df: pd.DataFrame) -> Dict:
        """Calculate EMA 10, 20, 60, 200"""
        emas = {}
        for period in [10, 20, 60, 200]:
            col_name = f'EMA_{period}'
            df[col_name] = ta.ema(df['Close'], length=period)
            emas[period] = df[col_name].iloc[-1] if not df[col_name].isna().iloc[-1] else None
        
        # Determine trend
        close = df['Close'].iloc[-1]
        ema_10 = emas.get(10)
        ema_20 = emas.get(20)
        ema_60 = emas.get(60)
        ema_200 = emas.get(200)
        
        trend = self._analyze_trend(close, ema_10, ema_20, ema_60, ema_200)
        
        # Build EMA sequence string
        ema_values = [(10, ema_10), (20, ema_20), (60, ema_60), (200, ema_200)]
        sorted_emas = sorted(ema_values, key=lambda x: x[1] if x[1] else 0, reverse=True)
        sequence = ' > '.join([f"EMA{e[0]}" for e in sorted_emas if e[1] is not None])
        
        return {
            'values': {k: round(float(v), 2) if v is not None else None for k, v in emas.items()},
            'trend': trend,
            'trend_zh': self._trend_to_chinese(trend),
            'sequence': sequence
        }
    
    def _analyze_trend(self, close, ema_10, ema_20, ema_60, ema_200) -> str:
        """Analyze trend based on EMA alignment"""
        if None in [ema_10, ema_20, ema_60, ema_200]:
            return 'insufficient_data'
        
        # Check EMA sequence
        bullish_sequence = ema_10 > ema_20 > ema_60 > ema_200  # 多頭排列
        bearish_sequence = ema_10 < ema_20 < ema_60 < ema_200  # 空頭排列
        long_term_bullish = ema_60 > ema_200  # 長期多頭
        long_term_bearish = ema_60 < ema_200  # 長期空頭
        short_term_bullish = ema_10 > ema_20  # 短期多頭
        short_term_bearish = ema_10 < ema_20  # 短期空頭
        
        # Full bullish alignment: 多頭排列
        if bullish_sequence and close > ema_10:
            return 'bullish_alignment'
        # Full bearish alignment: 空頭排列
        elif bearish_sequence and close < ema_10:
            return 'bearish_alignment'
        # Long-term uptrend with short-term consolidation
        elif long_term_bullish and short_term_bearish:
            if close > ema_60:
                return 'uptrend_consolidation'
            else:
                return 'uptrend_correction'
        # Long-term downtrend with short-term bounce
        elif long_term_bearish and short_term_bullish:
            if close < ema_60:
                return 'downtrend_bounce'
            else:
                return 'downtrend_recovery'
        # Uptrend with all EMAs bullish
        elif long_term_bullish and short_term_bullish:
            if close > ema_10:
                return 'strong_uptrend'
            else:
                return 'uptrend_pullback'
        # Downtrend with all EMAs bearish
        elif long_term_bearish and short_term_bearish:
            if close < ema_10:
                return 'strong_downtrend'
            else:
                return 'downtrend_relief'
        # Transition phase
        else:
            return 'transition'
    
    def _trend_to_chinese(self, trend: str) -> str:
        """Convert trend to Chinese"""
        mapping = {
            'bullish_alignment': '🟢 多頭排列 (10>20>60>200)',
            'bearish_alignment': '🔴 空頭排列 (10<20<60<200)',
            'strong_uptrend': '📈 強勢上升 (均線多頭)',
            'uptrend_pullback': '📈↘️ 上升趨勢回調',
            'uptrend_consolidation': '📈⏸️ 上升趨勢整理 (短期回調，長期多頭)',
            'uptrend_correction': '📈⚠️ 上升趨勢修正 (跌破60日線)',
            'strong_downtrend': '📉 強勢下跌 (均線空頭)',
            'downtrend_bounce': '📉↗️ 下跌趨勢反彈 (短期回升，長期空頭)',
            'downtrend_recovery': '📉🔄 下跌趨勢反轉嘗試',
            'downtrend_relief': '📉⏸️ 下跌趨勢喘息',
            'transition': '🔄 趨勢轉換期',
            'insufficient_data': '⚠️ 數據不足'
        }
        return mapping.get(trend, trend)
    
    def calculate_dmi_adx(self, df: pd.DataFrame) -> Dict:
        """Calculate DMI (DI+, DI-) and ADX for trend strength"""
        adx_data = ta.adx(df['High'], df['Low'], df['Close'], length=14)
        
        if adx_data is None or adx_data.empty:
            return {'error': 'Failed to calculate ADX/DMI'}
        
        # Get latest values
        adx = adx_data['ADX_14'].iloc[-1]
        di_plus = adx_data['DMP_14'].iloc[-1]
        di_minus = adx_data['DMN_14'].iloc[-1]
        
        # Previous values for trend change detection
        adx_prev = adx_data['ADX_14'].iloc[-2] if len(adx_data) > 1 else adx
        di_plus_prev = adx_data['DMP_14'].iloc[-2] if len(adx_data) > 1 else di_plus
        di_minus_prev = adx_data['DMN_14'].iloc[-2] if len(adx_data) > 1 else di_minus
        
        # Analyze trendiness
        trendiness = self._analyze_trendiness(adx, di_plus, di_minus, adx_prev, di_plus_prev, di_minus_prev)
        
        return {
            'ADX': round(float(adx), 2),
            'DI_plus': round(float(di_plus), 2),
            'DI_minus': round(float(di_minus), 2),
            'trendiness': trendiness,
            'trendiness_zh': self._trendiness_to_chinese(trendiness)
        }
    
    def _analyze_trendiness(self, adx, di_plus, di_minus, adx_prev, di_plus_prev, di_minus_prev) -> str:
        """Analyze trend strength and potential changes"""
        # ADX levels
        if adx > 40:
            strength = 'very_strong'
        elif adx > 25:
            strength = 'strong'
        elif adx > 20:
            strength = 'moderate'
        else:
            strength = 'weak'
        
        # Direction
        if di_plus > di_minus:
            direction = 'bullish'
        else:
            direction = 'bearish'
        
        # Trend change signals
        crossover = False
        if di_plus > di_minus and di_plus_prev <= di_minus_prev:
            crossover = 'bullish_crossover'
        elif di_minus > di_plus and di_minus_prev <= di_plus_prev:
            crossover = 'bearish_crossover'
        
        # ADX turning
        adx_rising = bool(adx > adx_prev)
        
        return {
            'strength': strength,
            'direction': direction,
            'crossover': crossover,
            'adx_rising': adx_rising
        }
    
    def _trendiness_to_chinese(self, trendiness: Dict) -> str:
        """Convert trendiness analysis to Chinese"""
        strength_map = {
            'very_strong': '非常強勢',
            'strong': '強勢',
            'moderate': '中等',
            'weak': '弱勢/無趨勢'
        }
        direction_map = {
            'bullish': '多方主導',
            'bearish': '空方主導'
        }
        
        result = f"趨勢強度: {strength_map.get(trendiness['strength'], trendiness['strength'])}\n"
        result += f"方向: {direction_map.get(trendiness['direction'], trendiness['direction'])}\n"
        
        if trendiness['crossover']:
            if trendiness['crossover'] == 'bullish_crossover':
                result += "⚠️ DI+ 向上穿越 DI- (看漲信號)\n"
            else:
                result += "⚠️ DI- 向上穿越 DI+ (看跌信號)\n"
        
        if trendiness['adx_rising']:
            result += "ADX 上升中 (趨勢加強)"
        else:
            result += "ADX 下降中 (趨勢減弱)"
        
        return result
    
    def calculate_fibonacci(self, df: pd.DataFrame, lookback: int = 60) -> Dict:
        """Calculate Fibonacci retracement levels"""
        recent = df.tail(lookback)
        high = recent['High'].max()
        low = recent['Low'].min()
        diff = high - low
        
        # Standard Fibonacci levels
        levels = {
            '0.0% (高點)': high,
            '23.6%': high - diff * 0.236,
            '38.2%': high - diff * 0.382,
            '50.0%': high - diff * 0.5,
            '61.8%': high - diff * 0.618,
            '78.6%': high - diff * 0.786,
            '100.0% (低點)': low
        }
        
        # Current price position
        close = df['Close'].iloc[-1]
        position = self._find_fib_position(close, levels)
        
        return {
            'high': round(high, 2),
            'low': round(low, 2),
            'levels': {k: round(v, 2) for k, v in levels.items()},
            'current_price': round(close, 2),
            'position': position,
            'position_zh': self._fib_position_to_chinese(position, close, levels)
        }
    
    def _find_fib_position(self, price, levels) -> str:
        """Find where current price sits relative to Fib levels"""
        sorted_levels = sorted(levels.values(), reverse=True)
        for i, level in enumerate(sorted_levels[:-1]):
            if price >= sorted_levels[i+1]:
                return f"between_{i}_{i+1}"
        return "below_all"
    
    def _fib_position_to_chinese(self, position: str, price: float, levels: Dict) -> str:
        """Convert Fib position to Chinese analysis"""
        level_names = list(levels.keys())
        level_values = list(levels.values())
        
        # Find nearest support and resistance
        supports = [v for v in level_values if v < price]
        resistances = [v for v in level_values if v > price]
        
        nearest_support = max(supports) if supports else None
        nearest_resistance = min(resistances) if resistances else None
        
        result = ""
        if nearest_resistance:
            # Find level name
            for name, val in levels.items():
                if val == nearest_resistance:
                    result += f"📍 上方阻力: {name} @ {round(nearest_resistance, 2)}\n"
                    break
        
        if nearest_support:
            for name, val in levels.items():
                if val == nearest_support:
                    result += f"📍 下方支撐: {name} @ {round(nearest_support, 2)}"
                    break
        
        return result if result else "價格在斐波那契範圍外"
    
    def analyze_volume(self, df: pd.DataFrame) -> Dict:
        """Analyze volume patterns"""
        # Volume moving averages
        df['Vol_MA_20'] = df['Volume'].rolling(20).mean()
        
        current_vol = df['Volume'].iloc[-1]
        avg_vol = df['Vol_MA_20'].iloc[-1]
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1
        
        # Volume trend (last 5 days)
        recent_vol = df['Volume'].tail(5).mean()
        prev_vol = df['Volume'].tail(10).head(5).mean()
        vol_trend = 'increasing' if recent_vol > prev_vol * 1.1 else ('decreasing' if recent_vol < prev_vol * 0.9 else 'stable')
        
        # Price-volume relationship
        price_change = (df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100
        
        if vol_ratio > 1.5 and price_change > 0:
            pv_signal = 'bullish_volume_breakout'
        elif vol_ratio > 1.5 and price_change < 0:
            pv_signal = 'bearish_volume_breakdown'
        elif vol_ratio < 0.7:
            pv_signal = 'low_volume_consolidation'
        else:
            pv_signal = 'normal'
        
        return {
            'current': int(current_vol),
            'avg_20': int(avg_vol) if not np.isnan(avg_vol) else None,
            'ratio': round(vol_ratio, 2),
            'trend': vol_trend,
            'signal': pv_signal,
            'analysis_zh': self._volume_to_chinese(vol_ratio, vol_trend, pv_signal, price_change)
        }
    
    def _volume_to_chinese(self, ratio, trend, signal, price_change) -> str:
        """Convert volume analysis to Chinese"""
        result = ""
        
        # Volume vs average
        if ratio > 2:
            result += "🔥 成交量異常放大 (>2x 平均)\n"
        elif ratio > 1.5:
            result += "📈 成交量明顯放大\n"
        elif ratio > 1:
            result += "成交量略高於平均\n"
        elif ratio > 0.7:
            result += "成交量正常\n"
        else:
            result += "📉 成交量萎縮\n"
        
        # Trend
        trend_map = {
            'increasing': '近期成交量趨勢: 放大',
            'decreasing': '近期成交量趨勢: 萎縮',
            'stable': '近期成交量趨勢: 穩定'
        }
        result += trend_map.get(trend, '') + "\n"
        
        # Signal interpretation
        signal_map = {
            'bullish_volume_breakout': '⚠️ 價漲量增 - 可能突破',
            'bearish_volume_breakdown': '⚠️ 價跌量增 - 可能破位',
            'low_volume_consolidation': '低量整理中',
            'normal': '量價配合正常'
        }
        result += signal_map.get(signal, '')
        
        return result
    
    def analyze_candlestick(self, df: pd.DataFrame) -> Dict:
        """Analyze candlestick patterns"""
        patterns = []
        
        # Get last few candles
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else None
        
        o, h, l, c = last['Open'], last['High'], last['Low'], last['Close']
        body = abs(c - o)
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l
        total_range = h - l
        
        # Doji
        if body < total_range * 0.1 and total_range > 0:
            patterns.append(('doji', '十字星', 'neutral', '市場猶豫不決，可能變盤'))
        
        # Hammer (at potential bottom)
        if lower_wick > body * 2 and upper_wick < body * 0.5 and body > 0:
            patterns.append(('hammer', '錘子線', 'bullish', '可能見底信號'))
        
        # Shooting star (at potential top)
        if upper_wick > body * 2 and lower_wick < body * 0.5 and body > 0:
            patterns.append(('shooting_star', '射擊之星', 'bearish', '可能見頂信號'))
        
        # Marubozu (strong candle)
        if body > total_range * 0.8 and total_range > 0:
            if c > o:
                patterns.append(('bullish_marubozu', '光頭光腳陽線', 'bullish', '強勢買盤'))
            else:
                patterns.append(('bearish_marubozu', '光頭光腳陰線', 'bearish', '強勢賣盤'))
        
        # Engulfing patterns - check last 3 days for better detection
        # Allow small gap tolerance (1% of price)
        gap_tolerance = c * 0.01
        
        if len(df) >= 3:
            # Look back up to 3 days for engulfing patterns
            for lookback in range(1, min(4, len(df))):
                check_candle = df.iloc[-1 - lookback]
                check_body = abs(check_candle['Close'] - check_candle['Open'])
                
                # Bullish engulfing: find a red candle that current green candle engulfs
                is_check_red = check_candle['Close'] < check_candle['Open']
                is_current_green = c > o
                opens_near_or_below = o <= check_candle['Close'] + gap_tolerance
                closes_above = c >= check_candle['Open']
                body_larger = body > check_body * 1.5  # Current body at least 1.5x larger
                
                if is_check_red and is_current_green and opens_near_or_below and closes_above and body_larger:
                    if lookback == 1:
                        patterns.append(('bullish_engulfing', '看漲吞噬', 'bullish', '強勢反轉信號'))
                    else:
                        patterns.append(('bullish_engulfing', f'看漲吞噬 ({lookback}日前)', 'bullish', f'吞噬{lookback}日前陰線，強勢反轉'))
                    break  # Found one, stop looking
                
                # Bearish engulfing: find a green candle that current red candle engulfs
                is_check_green = check_candle['Close'] > check_candle['Open']
                is_current_red = c < o
                opens_near_or_above = o >= check_candle['Close'] - gap_tolerance
                closes_below = c <= check_candle['Open']
                
                if is_check_green and is_current_red and opens_near_or_above and closes_below and body_larger:
                    if lookback == 1:
                        patterns.append(('bearish_engulfing', '看跌吞噬', 'bearish', '弱勢反轉信號'))
                    else:
                        patterns.append(('bearish_engulfing', f'看跌吞噬 ({lookback}日前)', 'bearish', f'吞噬{lookback}日前陽線，弱勢反轉'))
                    break
        
        # Basic candle description
        if c > o:
            candle_type = '陽線'
            change_pct = (c - o) / o * 100
        else:
            candle_type = '陰線'
            change_pct = (o - c) / o * 100
        
        return {
            'type': candle_type,
            'body_pct': round(body / total_range * 100, 1) if total_range > 0 else 0,
            'patterns': patterns,
            'analysis_zh': self._candle_to_chinese(candle_type, patterns, change_pct)
        }
    
    def _candle_to_chinese(self, candle_type, patterns, change_pct) -> str:
        """Convert candlestick analysis to Chinese"""
        result = f"📊 最新K線: {candle_type}\n"
        
        if patterns:
            result += "\n🕯️ 發現K線形態:\n"
            for p in patterns:
                name, zh_name, bias, desc = p
                emoji = '🟢' if bias == 'bullish' else ('🔴' if bias == 'bearish' else '⚪')
                result += f"  {emoji} {zh_name}: {desc}\n"
        else:
            result += "未發現明顯K線形態"
        
        return result
    
    def calculate_volume_profile(self, df: pd.DataFrame, num_bins: int = 50, value_area_pct: float = 0.70) -> Dict:
        """
        Calculate Volume Profile with VAL, VAH, and PoC
        
        Args:
            df: DataFrame with OHLCV data
            num_bins: Number of price bins for the profile
            value_area_pct: Percentage for value area (default 70%)
        
        Returns:
            Dict with PoC, VAH, VAL and profile data
        """
        if len(df) < 20:
            return {'error': 'Insufficient data for volume profile'}
        
        # Use typical price (HLC/3) for volume distribution
        df = df.copy()
        df['typical_price'] = (df['High'] + df['Low'] + df['Close']) / 3
        
        # Create price bins
        price_min = df['Low'].min()
        price_max = df['High'].max()
        bin_size = (price_max - price_min) / num_bins
        
        # Initialize volume profile
        profile = {}
        for i in range(num_bins):
            bin_low = price_min + (i * bin_size)
            bin_high = bin_low + bin_size
            bin_mid = (bin_low + bin_high) / 2
            profile[bin_mid] = 0
        
        # Distribute volume across price bins
        for idx, row in df.iterrows():
            low, high, vol = row['Low'], row['High'], row['Volume']
            if vol == 0 or np.isnan(vol):
                continue
            
            # Find bins that this candle spans
            for bin_mid in profile.keys():
                bin_low = bin_mid - (bin_size / 2)
                bin_high = bin_mid + (bin_size / 2)
                
                # Check if candle overlaps with bin
                if high >= bin_low and low <= bin_high:
                    # Calculate overlap percentage
                    overlap_low = max(low, bin_low)
                    overlap_high = min(high, bin_high)
                    candle_range = high - low if high > low else 1
                    overlap_pct = (overlap_high - overlap_low) / candle_range
                    profile[bin_mid] += vol * overlap_pct
        
        # Find Point of Control (PoC) - highest volume price level
        poc_price = max(profile, key=profile.get)
        poc_volume = profile[poc_price]
        
        # Calculate Value Area (VAH and VAL)
        total_volume = sum(profile.values())
        target_volume = total_volume * value_area_pct
        
        # Sort bins by distance from PoC
        sorted_bins = sorted(profile.items(), key=lambda x: abs(x[0] - poc_price))
        
        accumulated_volume = 0
        value_area_prices = []
        
        for price, vol in sorted_bins:
            accumulated_volume += vol
            value_area_prices.append(price)
            if accumulated_volume >= target_volume:
                break
        
        vah = max(value_area_prices)  # Value Area High
        val = min(value_area_prices)  # Value Area Low
        
        # Current price position relative to value area
        current_price = df['Close'].iloc[-1]
        
        if current_price > vah:
            position = 'above_va'
            position_zh = '在價值區上方 (可能超買)'
        elif current_price < val:
            position = 'below_va'
            position_zh = '在價值區下方 (可能超賣)'
        elif abs(current_price - poc_price) < bin_size * 2:
            position = 'at_poc'
            position_zh = '接近控制點 (PoC)'
        else:
            position = 'in_va'
            position_zh = '在價值區內'
        
        return {
            'poc': round(float(poc_price), 2),
            'vah': round(float(vah), 2),
            'val': round(float(val), 2),
            'current_price': round(float(current_price), 2),
            'position': position,
            'position_zh': position_zh,
            'analysis_zh': self._volume_profile_to_chinese(poc_price, vah, val, current_price, position)
        }
    
    def _volume_profile_to_chinese(self, poc, vah, val, current_price, position) -> str:
        """Convert volume profile to Chinese analysis"""
        result = f"""📊 **成交量分佈 (Volume Profile)**
• PoC (控制點): {round(poc, 2)}
• VAH (價值區高): {round(vah, 2)}
• VAL (價值區低): {round(val, 2)}
• 價值區範圍: {round(val, 2)} - {round(vah, 2)}

"""
        if position == 'above_va':
            result += "📍 現價在價值區上方\n"
            result += f"⚠️ 距VAH: {round(current_price - vah, 2)} (可能回落至價值區)\n"
            result += f"關注支撐: VAH @ {round(vah, 2)}"
        elif position == 'below_va':
            result += "📍 現價在價值區下方\n"
            result += f"⚠️ 距VAL: {round(val - current_price, 2)} (可能反彈至價值區)\n"
            result += f"關注阻力: VAL @ {round(val, 2)}"
        elif position == 'at_poc':
            result += "📍 現價接近控制點 (PoC)\n"
            result += "這是成交量最集中的價位，通常有較強支撐/阻力"
        else:
            result += "📍 現價在價值區內\n"
            result += f"上方阻力: VAH @ {round(vah, 2)}\n"
            result += f"下方支撐: VAL @ {round(val, 2)}"
        
        return result
    
    def full_analysis(self, ticker: str, market: str = 'US') -> Dict:
        """Run complete technical analysis"""
        try:
            # Fetch data (use 2 years for better volume profile)
            df = self.fetch_data(ticker, market, period='2y')
            
            # Get stock info
            symbol = self.get_symbol(ticker, market)
            stock = yf.Ticker(symbol)
            info = stock.info
            name = info.get('shortName', info.get('longName', ticker))
            
            # Run all analyses
            emas = self.calculate_emas(df.copy())
            dmi_adx = self.calculate_dmi_adx(df.copy())
            fibonacci = self.calculate_fibonacci(df.copy())
            volume = self.analyze_volume(df.copy())
            candlestick = self.analyze_candlestick(df.copy())
            volume_profile = self.calculate_volume_profile(df.copy())
            
            # Current price info
            current_price = df['Close'].iloc[-1]
            prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100
            
            # RRG and RS Analysis (if available)
            rrg_data = None
            rs_data = None
            if RRG_RS_AVAILABLE:
                try:
                    # Generate RRG chart - use CHART_DIR env var if set
                    chart_dir = os.environ.get('CHART_DIR', '/root/clawd/research/charts')
                    os.makedirs(chart_dir, exist_ok=True)
                    rrg_output_path = f'{chart_dir}/rrg_{ticker}_{market}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                    rrg_data = generate_rrg_chart(ticker, market, output_path=rrg_output_path)
                except Exception as e:
                    rrg_data = {'success': False, 'error': str(e)}
                
                try:
                    # Get RS ranking
                    rs_data = get_rs_ranking(ticker, market)
                except Exception as e:
                    rs_data = {'success': False, 'error': str(e)}
            
            return {
                'success': True,
                'ticker': ticker,
                'market': market,
                'name': name,
                'price': {
                    'current': round(current_price, 2),
                    'change': round(change, 2),
                    'change_pct': round(change_pct, 2)
                },
                'ema': emas,
                'dmi_adx': dmi_adx,
                'fibonacci': fibonacci,
                'volume': volume,
                'candlestick': candlestick,
                'volume_profile': volume_profile,
                'rrg': rrg_data,
                'rs_ranking': rs_data,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'ticker': ticker,
                'market': market
            }
    
    def generate_report_zh(self, analysis: Dict) -> str:
        """Generate Chinese analysis report"""
        if not analysis.get('success'):
            return f"❌ 分析失敗: {analysis.get('error', '未知錯誤')}"
        
        report = f"""📊 **{analysis['name']}** ({analysis['ticker']}.{analysis['market']})
━━━━━━━━━━━━━━━━━━━━━━

💰 **價格資訊**
現價: {analysis['price']['current']}
漲跌: {analysis['price']['change']} ({analysis['price']['change_pct']:+.2f}%)

─ ─ ─ ─ ─ ─ ─ ─ ─ ─

📈 **趨勢分析 (EMA)**
{analysis['ema']['trend_zh']}
排列順序: {analysis['ema'].get('sequence', 'N/A')}
• EMA10: {analysis['ema']['values'].get(10, 0):.2f}
• EMA20: {analysis['ema']['values'].get(20, 0):.2f}
• EMA60: {analysis['ema']['values'].get(60, 0):.2f}
• EMA200: {analysis['ema']['values'].get(200, 0):.2f}

─ ─ ─ ─ ─ ─ ─ ─ ─ ─

📏 **趨勢強度 (DMI/ADX)**
ADX: {analysis['dmi_adx'].get('ADX', 'N/A')}
DI+: {analysis['dmi_adx'].get('DI_plus', 'N/A')} | DI-: {analysis['dmi_adx'].get('DI_minus', 'N/A')}
{analysis['dmi_adx'].get('trendiness_zh', '')}

─ ─ ─ ─ ─ ─ ─ ─ ─ ─

📐 **斐波那契關鍵位**
{analysis['fibonacci'].get('position_zh', '')}
• 高點: {analysis['fibonacci']['high']}
• 低點: {analysis['fibonacci']['low']}

─ ─ ─ ─ ─ ─ ─ ─ ─ ─

📊 **成交量分析**
{analysis['volume'].get('analysis_zh', '')}

─ ─ ─ ─ ─ ─ ─ ─ ─ ─

📈 **成交量分佈 (Volume Profile)**
{analysis.get('volume_profile', {}).get('analysis_zh', 'N/A')}

─ ─ ─ ─ ─ ─ ─ ─ ─ ─

🕯️ **K線形態**
{analysis['candlestick'].get('analysis_zh', '')}
"""
        
        # Add RRG section if available
        if analysis.get('rrg') and analysis['rrg'].get('success'):
            rrg = analysis['rrg']
            quadrant_zh = get_rrg_quadrant_zh(rrg['quadrant']) if RRG_RS_AVAILABLE else rrg['quadrant']
            benchmark_zh = '恆生指數' if rrg['benchmark'] == '^HSI' else '標普500指數'
            # RS-Ratio context: >100 = outperforming, <100 = underperforming
            ratio_context = "贏市場" if rrg['rs_ratio'] >= 100 else "輸市場"
            # RS-Momentum context: >100 = strengthening, <100 = weakening
            momentum_context = "正在增強" if rrg['rs_momentum'] >= 100 else "正在減弱"
            report += f"""
─ ─ ─ ─ ─ ─ ─ ─ ─ ─

📈 **資產輪動**
• 相對強度比率: {rrg['rs_ratio']} (相對表現{ratio_context} :100)
• 相對強度動能: {rrg['rs_momentum']} (相對表現{momentum_context})
• 象限: {quadrant_zh}
• 基準: {benchmark_zh}
"""
        
        # Add RS Ranking section if available
        if analysis.get('rs_ranking') and analysis['rs_ranking'].get('success'):
            rs = analysis['rs_ranking']
            rankings = rs.get('rankings', {})
            changes = rs.get('rank_changes', {})
            current = rankings.get('current', {})
            
            report += f"""
─ ─ ─ ─ ─ ─ ─ ─ ─ ─

📊 **相對強度排名 (Relative Strength Rank)**
• 現時排名: #{current.get('rank', 'N/A')}/{current.get('total_stocks', 'N/A')} (分數: {current.get('score', 'N/A')})
"""
            # Add historical changes
            for period in ['1d_ago', '2d_ago', '5d_ago', '10d_ago']:
                if period in rankings and rankings[period].get('rank'):
                    r = rankings[period]
                    change = changes.get(period, 0)
                    change_str = f"↑{change}" if change > 0 else (f"↓{abs(change)}" if change < 0 else "→")
                    report += f"• {period.replace('_ago', '日前')}: #{r['rank']} ({change_str})\n"
            
            # Removed: footnote about ticker not in original basket
        
        report += f"""
━━━━━━━━━━━━━━━━━━━━━━
⏰ 分析時間: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC
📌 數據週期: 2年日線
"""
        return report.strip()


# Flask API for n8n integration
def create_app():
    from flask import Flask, request, jsonify
    
    app = Flask(__name__)
    app.json.encoder = NumpyEncoder
    analyzer = MarketAnalyzer()
    
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok', 'service': 'market-analyzer'})
    
    @app.route('/analyze', methods=['POST'])
    def analyze():
        """
        Analyze a stock
        Body: {"ticker": "AAPL", "market": "US"} or {"ticker": "0700", "market": "HK"}
        """
        data = request.json or {}
        ticker = data.get('ticker')
        market = data.get('market', 'US')
        
        if not ticker:
            return jsonify({'error': 'ticker is required'}), 400
        
        result = analyzer.full_analysis(ticker, market)
        return jsonify(result)
    
    @app.route('/analyze/report', methods=['POST'])
    def analyze_report():
        """Get analysis as formatted Chinese report"""
        data = request.json or {}
        ticker = data.get('ticker')
        market = data.get('market', 'US')
        
        if not ticker:
            return jsonify({'error': 'ticker is required'}), 400
        
        analysis = analyzer.full_analysis(ticker, market)
        report = analyzer.generate_report_zh(analysis)
        
        return jsonify({
            'success': analysis.get('success', False),
            'report': report,
            'raw': analysis
        })
    
    @app.route('/analyze/batch', methods=['POST'])
    def analyze_batch():
        """Analyze multiple stocks"""
        data = request.json or {}
        stocks = data.get('stocks', [])  # [{"ticker": "AAPL", "market": "US"}, ...]
        
        results = []
        for stock in stocks:
            ticker = stock.get('ticker')
            market = stock.get('market', 'US')
            if ticker:
                analysis = analyzer.full_analysis(ticker, market)
                report = analyzer.generate_report_zh(analysis)
                results.append({
                    'ticker': ticker,
                    'market': market,
                    'report': report,
                    'success': analysis.get('success', False)
                })
        
        return jsonify({'results': results, 'count': len(results)})
    
    @app.route('/analyze/telegram', methods=['POST'])
    def analyze_telegram():
        """Analyze and send directly to Telegram"""
        import subprocess
        
        data = request.json or {}
        ticker = data.get('ticker')
        market = data.get('market', 'US')
        chat_id = data.get('chat_id', '1016466977')  # Default to Jason's chat
        
        if not ticker:
            return jsonify({'error': 'ticker is required'}), 400
        
        analysis = analyzer.full_analysis(ticker, market)
        report = analyzer.generate_report_zh(analysis)
        
        # Send via clawdbot CLI
        try:
            result = subprocess.run(
                ['/usr/bin/clawdbot', 'message', 'send', 
                 '--channel', 'telegram', 
                 '--target', str(chat_id), 
                 '--message', report],
                capture_output=True,
                text=True,
                timeout=30
            )
            sent = result.returncode == 0
        except Exception as e:
            sent = False
        
        return jsonify({
            'success': analysis.get('success', False),
            'sent': sent,
            'ticker': ticker,
            'market': market
        })
    
    @app.route('/analyze/complete', methods=['POST'])
    def analyze_complete():
        """
        Complete analysis with TA report + Technical chart + RRG chart
        Returns all paths for consistent output
        """
        import subprocess
        
        data = request.json or {}
        ticker = data.get('ticker')
        market = data.get('market', 'US')
        
        if not ticker:
            return jsonify({'error': 'ticker is required'}), 400
        
        result = {
            'success': False,
            'ticker': ticker,
            'market': market,
            'report': '',
            'technical_chart': None,
            'rrg_chart': None
        }
        
        # 1. Run TA analysis and get formatted report
        analysis = analyzer.full_analysis(ticker, market)
        result['report'] = analyzer.generate_report_zh(analysis)
        result['success'] = analysis.get('success', False)
        result['raw'] = analysis
        
        # 2. Get RRG chart path from analysis (already generated in full_analysis)
        if analysis.get('rrg', {}).get('chart_path'):
            result['rrg_chart'] = analysis['rrg']['chart_path']
        
        # 3. Generate technical chart using venv python
        try:
            venv_python = '/root/clawd/projects/market-analyzer/venv/bin/python3'
            chart_result = subprocess.run(
                [venv_python, '/root/clawd/projects/market-analyzer/generate_chart.py',
                 ticker, '--market', market, '--period', '13mo'],
                capture_output=True,
                text=True,
                timeout=90,
                cwd='/root/clawd/projects/market-analyzer'
            )
            # Extract chart path from output
            import re
            for line in chart_result.stdout.split('\n'):
                match = re.search(r'(/root/clawd/research/charts/[^\s]+\.png)', line)
                if match:
                    result['technical_chart'] = match.group(1)
                    break
            if not result['technical_chart'] and chart_result.stderr:
                result['technical_chart_error'] = chart_result.stderr[:200]
        except Exception as e:
            result['technical_chart_error'] = str(e)
        
        return jsonify(result)
    
    @app.route('/analyze/full', methods=['POST'])
    def analyze_full():
        """
        Full analysis with TA + Perplexity news
        Requires PERPLEXITY_API_KEY environment variable
        """
        import subprocess
        import os
        
        data = request.json or {}
        ticker = data.get('ticker')
        market = data.get('market', 'US')
        chat_id = data.get('chat_id', '1016466977')
        include_news = data.get('include_news', True)
        
        if not ticker:
            return jsonify({'error': 'ticker is required'}), 400
        
        # Run TA analysis
        analysis = analyzer.full_analysis(ticker, market)
        ta_report = analyzer.generate_report_zh(analysis)
        
        # Try to get Perplexity news if API key is available
        news_report = ""
        if include_news and os.environ.get('PERPLEXITY_API_KEY'):
            try:
                from perplexity_client import PerplexityClient
                pplx = PerplexityClient()
                news = pplx.search_news(ticker, market)
                if news.get('success'):
                    news_report = f"""

📰 **新聞面分析 (Perplexity AI)**
━━━━━━━━━━━━━━━━━━━━━━

{news.get('content', 'N/A')}
"""
                    if news.get('citations'):
                        news_report += "\n📎 資料來源:\n"
                        for cite in news.get('citations', [])[:5]:
                            news_report += f"• {cite}\n"
            except Exception as e:
                news_report = f"\n⚠️ 新聞獲取失敗: {str(e)}\n"
        elif include_news:
            news_report = "\n⚠️ 新聞功能需要設置 PERPLEXITY_API_KEY\n"
        
        # Combine reports
        full_report = ta_report + news_report
        
        # Send to Telegram
        try:
            result = subprocess.run(
                ['/usr/bin/clawdbot', 'message', 'send', 
                 '--channel', 'telegram', 
                 '--target', str(chat_id), 
                 '--message', full_report],
                capture_output=True,
                text=True,
                timeout=60
            )
            sent = result.returncode == 0
        except Exception as e:
            sent = False
        
        return jsonify({
            'success': analysis.get('success', False),
            'sent': sent,
            'ticker': ticker,
            'market': market,
            'has_news': bool(news_report and 'Perplexity' in news_report)
        })
    
    return app


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'serve':
        # Run as API server
        app = create_app()
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 5003
        print(f"Starting Market Analyzer API on port {port}...")
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # CLI test
        analyzer = MarketAnalyzer()
        
        # Test with a US stock
        print("Testing AAPL (US)...")
        result = analyzer.full_analysis('AAPL', 'US')
        print(analyzer.generate_report_zh(result))
        
        print("\n" + "="*50 + "\n")
        
        # Test with a HK stock (Tencent)
        print("Testing 0700 (HK)...")
        result = analyzer.full_analysis('0700', 'HK')
        print(analyzer.generate_report_zh(result))
