#!/usr/bin/env python3
"""
Technical Analysis API for JC-Algos Website
Combines TA report, Technical Chart, and RRG Chart
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import numpy as np

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ta_analyzer import MarketAnalyzer, NumpyEncoder
from rrg_rs_analyzer import generate_rrg_chart, get_rs_ranking, get_rrg_quadrant_zh
from generate_chart import generate_chart

app = Flask(__name__)
app.json.encoder = NumpyEncoder
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize analyzer
analyzer = MarketAnalyzer()

# Chart output directory (in Docker, uses /app/charts via CHART_DIR env var)
CHART_DIR = os.environ.get('CHART_DIR', '/root/clawd/research/charts')
# Fallback: Use /app/charts if running in Docker and env var not set
if not os.environ.get('CHART_DIR') and os.path.exists('/app'):
    CHART_DIR = '/app/charts'
os.makedirs(CHART_DIR, exist_ok=True)
print(f"📁 Using chart directory: {CHART_DIR}")


@app.route('/api/ta/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'technical-analysis-api',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/ta/analyze', methods=['GET', 'POST'])
def analyze():
    """
    Full technical analysis endpoint
    
    GET: /api/ta/analyze?ticker=0700&market=HK
    POST: {"ticker": "0700", "market": "HK"}
    
    Returns:
        - TA report (formatted text)
        - Technical chart URL
        - RRG chart URL
        - Raw analysis data
    """
    if request.method == 'POST':
        data = request.json or {}
    else:
        data = request.args.to_dict()
    
    ticker = data.get('ticker', '').upper().strip()
    market = data.get('market', 'HK').upper().strip()
    
    if not ticker:
        return jsonify({'success': False, 'error': 'ticker is required'}), 400
    
    # Validate market
    if market not in ['HK', 'US']:
        return jsonify({'success': False, 'error': 'market must be HK or US'}), 400
    
    result = {
        'success': False,
        'ticker': ticker,
        'market': market,
        'report': '',
        'charts': {
            'technical': None,
            'rrg': None
        },
        'data': None,
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        # 1. Run full TA analysis
        analysis = analyzer.full_analysis(ticker, market)
        if not analysis.get('success'):
            return jsonify({
                'success': False,
                'error': analysis.get('error', 'Analysis failed'),
                'ticker': ticker,
                'market': market
            }), 400
        
        # 2. Generate formatted report
        result['report'] = analyzer.generate_report_zh(analysis)
        result['data'] = {
            'name': analysis.get('name'),
            'price': analysis.get('price'),
            'ema': analysis.get('ema'),
            'dmi_adx': analysis.get('dmi_adx'),
            'fibonacci': analysis.get('fibonacci'),
            'volume': analysis.get('volume'),
            'volume_profile': analysis.get('volume_profile'),
            'candlestick': analysis.get('candlestick')
        }
        
        # 3. Generate technical chart
        try:
            # Ensure output directory exists
            os.makedirs(CHART_DIR, exist_ok=True)
            chart_path = generate_chart(ticker, market, period='13mo', output_dir=CHART_DIR)
            if chart_path and os.path.exists(chart_path):
                # Return relative path for API access
                chart_filename = os.path.basename(chart_path)
                result['charts']['technical'] = f'/api/ta/chart/{chart_filename}'
        except Exception as e:
            result['charts']['technical_error'] = str(e)
        
        # 4. Generate RRG chart
        try:
            # Ensure output directory exists
            os.makedirs(CHART_DIR, exist_ok=True)
            rrg_filename = f'rrg_{ticker}_{market}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            rrg_path = os.path.join(CHART_DIR, rrg_filename)
            # Make sure rrg_path is absolute and directory exists
            rrg_path = os.path.abspath(rrg_path)
            os.makedirs(os.path.dirname(rrg_path), exist_ok=True)
            rrg_data = generate_rrg_chart(ticker, market, output_path=rrg_path)
            
            if rrg_data.get('success') and os.path.exists(rrg_path):
                result['charts']['rrg'] = f'/api/ta/chart/{rrg_filename}'
                result['data']['rrg'] = {
                    'rs_ratio': rrg_data.get('rs_ratio'),
                    'rs_momentum': rrg_data.get('rs_momentum'),
                    'quadrant': rrg_data.get('quadrant'),
                    'quadrant_zh': get_rrg_quadrant_zh(rrg_data.get('quadrant', ''))
                }
        except Exception as e:
            result['charts']['rrg_error'] = str(e)
        
        # 5. Get RS ranking
        try:
            rs_data = get_rs_ranking(ticker, market)
            if rs_data.get('success'):
                result['data']['rs_ranking'] = {
                    'current_rank': rs_data['rankings']['current']['rank'],
                    'total_stocks': rs_data['rankings']['current']['total_stocks'],
                    'score': rs_data['rankings']['current']['score'],
                    'rank_changes': rs_data.get('rank_changes', {})
                }
        except Exception as e:
            result['data']['rs_ranking_error'] = str(e)
        
        result['success'] = True
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'ticker': ticker,
            'market': market
        }), 500


@app.route('/api/ta/chart/<filename>')
def serve_chart(filename):
    """Serve chart images"""
    chart_path = os.path.join(CHART_DIR, filename)
    if os.path.exists(chart_path):
        return send_file(chart_path, mimetype='image/png')
    return jsonify({'error': 'Chart not found'}), 404


@app.route('/api/ta/quick', methods=['GET'])
def quick_analysis():
    """
    Quick analysis - returns just the key metrics without charts
    Faster for list views
    """
    ticker = request.args.get('ticker', '').upper().strip()
    market = request.args.get('market', 'HK').upper().strip()
    
    if not ticker:
        return jsonify({'success': False, 'error': 'ticker is required'}), 400
    
    try:
        analysis = analyzer.full_analysis(ticker, market)
        if not analysis.get('success'):
            return jsonify({
                'success': False,
                'error': analysis.get('error', 'Analysis failed')
            }), 400
        
        return jsonify({
            'success': True,
            'ticker': ticker,
            'market': market,
            'name': analysis.get('name'),
            'price': analysis.get('price'),
            'trend': analysis.get('ema', {}).get('trend_zh'),
            'adx': analysis.get('dmi_adx', {}).get('ADX'),
            'volume_ratio': analysis.get('volume', {}).get('ratio'),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ta/batch', methods=['POST'])
def batch_analysis():
    """
    Batch analysis for multiple tickers
    POST: {"tickers": ["0700", "9988"], "market": "HK"}
    """
    data = request.json or {}
    tickers = data.get('tickers', [])
    market = data.get('market', 'HK').upper()
    
    if not tickers:
        return jsonify({'success': False, 'error': 'tickers array is required'}), 400
    
    results = []
    for ticker in tickers[:10]:  # Limit to 10 tickers
        try:
            analysis = analyzer.full_analysis(ticker, market)
            results.append({
                'ticker': ticker,
                'success': analysis.get('success', False),
                'name': analysis.get('name'),
                'price': analysis.get('price'),
                'trend': analysis.get('ema', {}).get('trend_zh') if analysis.get('success') else None,
                'error': analysis.get('error') if not analysis.get('success') else None
            })
        except Exception as e:
            results.append({
                'ticker': ticker,
                'success': False,
                'error': str(e)
            })
    
    return jsonify({
        'success': True,
        'count': len(results),
        'results': results
    })


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Technical Analysis API')
    parser.add_argument('--port', '-p', type=int, default=5004, help='Port to run on')
    parser.add_argument('--host', '-H', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--debug', '-d', action='store_true', help='Debug mode')
    
    args = parser.parse_args()
    
    print(f"🚀 Starting Technical Analysis API on {args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)
