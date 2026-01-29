# JC Algos 沽空報告

香港股票沽空數據分析工具

## 功能

1. **個股沽空查詢** - 輸入股票代碼查詢今日沽空及累計沽空倉位
2. **互動圖表** - 顯示過去10週累計倉位及過去10日每日沽空
3. **沽空排行榜** - Top 20 按流通股百分比排名

## 數據來源

- **SFC 證監會** - 累計申報沽空倉位 (每週更新)
- **HKEX 港交所** - 每日沽空成交數據

## 安裝

```bash
pip install -r requirements.txt
playwright install chromium
```

## 運行

```bash
python short_selling_web.py
```

訪問 http://localhost:5004

## API 端點

- `GET /api/short/lookup?ticker=700` - 查詢個股沽空數據
- `GET /api/short/top20` - 獲取 Top 20 排行榜

## 授權

© 2026 JC Algos
