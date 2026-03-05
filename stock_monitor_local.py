#!/usr/bin/env python3
"""
股票监控脚本 (主备模式)
- 优先使用 Yahoo Finance
- 如果被限流，自动切换到 Twelvedata
- 每次请求延迟 5 秒，避免触发限流

需要安装: pip install yfinance requests
"""

import requests
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 尝试导入 yfinance
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("警告: yfinance 未安装，请运行: pip install yfinance")

# 配置文件路径
CONFIG_DIR = Path(__file__).parent
STOCKS_FILE = CONFIG_DIR / "stocks.json"
LOG_FILE = CONFIG_DIR / "stock_monitor.log"

# Twelvedata API 配置
TWELVEDATA_API_KEY = "785bfc4b878c4bc9a5cc517262c26f25"
TWELVEDATA_BASE = "https://api.twelvedata.com"

# 请求延迟 (秒)
REQUEST_DELAY = 5

# 默认股票列表
DEFAULT_STOCKS = [
    {"symbol": "ICLN", "name": "iShares Global Clean Energy ETF"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation 英伟达"},
    {"symbol": "TSM", "name": "Taiwan Semiconductor 台积电"},
    {"symbol": "GOOGL", "name": "Alphabet Inc. Google"},
]

# 飞书 Webhook URL
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK_URL", "")

def load_stocks():
    if STOCKS_FILE.exists():
        with open(STOCKS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return DEFAULT_STOCKS

def save_stocks(stocks):
    with open(STOCKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)

def delay():
    time.sleep(REQUEST_DELAY)

def is_rate_limit_error(e):
    err_msg = str(e).lower()
    return "rate limit" in err_msg or "too many request" in err_msg

# ========== Yahoo Finance ==========
def get_yahoo_price(symbol):
    if not YFINANCE_AVAILABLE:
        return None, "yfinance未安装"
    
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        current = info.get('currentPrice') or info.get('regularMarketPrice')
        previous = info.get('previousClose') or info.get('regularMarketPreviousClose')
        
        if current and previous:
            change = current - previous
            change_pct = (change / previous * 100)
            
            return {
                "source": "yahoo",
                "current": current,
                "previous": previous,
                "change": change,
                "change_pct": change_pct,
                "volume": info.get('volume'),
                "currency": info.get('currency', 'USD')
            }, None
    except Exception as e:
        if is_rate_limit_error(e):
            return None, "rate_limit"
        return None, str(e)
    
    return None, "无数据"

def get_yahoo_company_info(symbol):
    if not YFINANCE_AVAILABLE:
        return {}
    
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        return {
            "sector": info.get('sector', ''),
            "industry": info.get('industry', ''),
            "market_cap": info.get('marketCap'),
            "pe_ratio": info.get('trailingPE'),
        }
    except Exception as e:
        if is_rate_limit_error(e):
            return {"error": "rate_limit"}
        return {}

def get_yahoo_news(symbol):
    if not YFINANCE_AVAILABLE:
        return []
    
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        
        result = []
        if news:
            for item in news[:3]:
                result.append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "publisher": item.get("publisher", "")
                })
        return result
    except Exception as e:
        return []

# ========== Twelvedata ==========
def get_twelvedata_price(symbol):
    try:
        url = f"{TWELVEDATA_BASE}/time_series"
        params = {
            "symbol": symbol,
            "interval": "1day",
            "outputsize": 5,
            "apikey": TWELVEDATA_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        if data.get("status") == "ok" and "values" in data:
            values = data["values"]
            if len(values) >= 2:
                current = float(values[0]["close"])
                previous = float(values[1]["close"])
                volume = int(values[0]["volume"])
                
                change = current - previous
                change_pct = (change / previous * 100) if previous else 0
                
                return {
                    "source": "twelvedata",
                    "current": current,
                    "previous": previous,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": volume,
                    "date": values[0]["datetime"]
                }, None
    except Exception as e:
        return None, str(e)
    
    return None, "无数据"

def get_twelvedata_company_info(symbol):
    try:
        url = f"{TWELVEDATA_BASE}/symbol_search"
        params = {"symbol": symbol, "apikey": TWELVEDATA_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if data.get("results"):
            return {"name": data["results"][0].get("description", "")}
    except:
        pass
    return {}

# ========== 主备模式 ==========
def get_stock_data(symbol, use_twelvedata=False):
    if not use_twelvedata:
        delay()
        price, err = get_yahoo_price(symbol)
        
        if err == "rate_limit":
            log(f"Yahoo 限流，切换到 Twelvedata...")
            use_twelvedata = True
        elif price:
            delay()
            company_info = get_yahoo_company_info(symbol)
            if company_info.get("error") == "rate_limit":
                log(f"Yahoo 公司信息限流，切换到 Twelvedata...")
                use_twelvedata = True
                company_info = get_twelvedata_company_info(symbol)
            
            delay()
            news = get_yahoo_news(symbol)
            
            return {
                "price": price,
                "company_info": company_info,
                "news": news
            }, use_twelvedata
    
    # 备用 Twelvedata
    delay()
    price, err = get_twelvedata_price(symbol)
    
    if price:
        company_info = get_twelvedata_company_info(symbol)
        return {
            "price": price,
            "company_info": company_info,
            "news": []
        }, use_twelvedata
    
    return {
        "price": None,
        "company_info": {},
        "news": []
    }, use_twelvedata

# ========== 日志和消息 ==========
def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_msg)
    print(log_msg.strip())

def format_price(price):
    if price is None:
        return "N/A"
    return f"{price:.2f}"

def format_volume(volume):
    if not volume:
        return "N/A"
    if volume >= 1_000_000_000:
        return f"{volume/1_000_000_000:.2f}B"
    elif volume >= 1_000_000:
        return f"{volume/1_000_000:.2f}M"
    elif volume >= 1_000:
        return f"{volume/1_000:.2f}K"
    return str(volume)

def build_message(stock_data_list, use_twelvedata=False):
    date = datetime.now().strftime("%Y-%m-%d")
    source = "Twelvedata" if use_twelvedata else "Yahoo"
    
    lines = [f"📊 每日股票监控 - {date}\n"]
    lines.append(f"数据源: {source}\n")
    lines.append("=" * 40 + "\n")
    
    gainers = []
    losers = []
    
    for stock in stock_data_list:
        price_data = stock["data"]["price"]
        if price_data:
            change_pct = price_data.get('change_pct', 0)
            if change_pct > 0:
                gainers.append((stock["symbol"], change_pct))
            elif change_pct < 0:
                losers.append((stock["symbol"], change_pct))
    
    if gainers:
        lines.append("📈 上涨: " + ", ".join([f"{s}(+{p:.2f}%)" for s, p in gainers]))
    if losers:
        lines.append("📉 下跌: " + ", ".join([f"{s}({p:.2f}%)" for s, p in losers]))
    lines.append("-" * 40 + "\n")
    
    for stock in stock_data_list:
        symbol = stock["symbol"]
        name = stock["name"]
        price_data = stock["data"]["price"]
        
        if price_data:
            current = price_data.get('current')
            change = price_data.get('change')
            change_pct = price_data.get('change_pct')
            volume = price_data.get('volume')
            
            emoji = "📈" if change_pct >= 0 else "📉"
            lines.append(f"{emoji} {symbol}")
            lines.append(f"   {name}")
            lines.append(f"   现价: ${current:.2f}")
            lines.append(f"   涨跌: {change:+.2f} ({change_pct:+.2f}%)")
            if volume:
                lines.append(f"   成交量: {format_volume(volume)}")
        else:
            lines.append(f"❌ {symbol} - {name}")
            lines.append("   数据获取失败")
        
        lines.append("")
    
    lines.append("=" * 40)
    lines.append("\n💡 回复「添加股票 XXX」或「删除股票 XXX」管理监控")
    
    return "\n".join(lines)

def send_feishu_message(content, webhook_url=None):
    if not webhook_url:
        webhook_url = FEISHU_WEBHOOK
    
    if not webhook_url:
        log("未配置飞书 Webhook URL")
        print("\n" + "=" * 60)
        print("消息内容 (未发送):")
        print("=" * 60)
        print(content)
        print("=" * 60)
        return False
    
    message = {"msg_type": "text", "content": {"text": content}}
    
    try:
        response = requests.post(webhook_url, json=message, timeout=30)
        result = response.json()
        
        if result.get("code") == 0:
            log("飞书消息发送成功")
            return True
        else:
            log(f"飞书消息发送失败: {result}")
            return False
    except Exception as e:
        log(f"发送飞书消息异常: {e}")
        return False

def add_stock(symbol, name=None):
    stocks = load_stocks()
    
    for stock in stocks:
        if stock["symbol"].upper() == symbol.upper():
            log(f"股票 {symbol} 已存在")
            return False
    
    if not name and YFINANCE_AVAILABLE:
        try:
            delay()
            ticker = yf.Ticker(symbol)
            info = ticker.info
            name = info.get('shortName') or info.get('longName') or symbol
        except:
            name = symbol
    
    stocks.append({"symbol": symbol.upper(), "name": name or symbol})
    save_stocks(stocks)
    log(f"已添加股票: {symbol} - {name}")
    return True

def remove_stock(symbol):
    stocks = load_stocks()
    original_len = len(stocks)
    stocks = [s for s in stocks if s["symbol"].upper() != symbol.upper()]
    
    if len(stocks) < original_len:
        save_stocks(stocks)
        log(f"已删除股票: {symbol}")
        return True
    else:
        log(f"股票 {symbol} 不存在")
        return False

def list_stocks():
    stocks = load_stocks()
    print("\n当前监控的股票:")
    for i, stock in enumerate(stocks, 1):
        print(f"  {i}. {stock['symbol']} - {stock['name']}")
    print()

def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        
        if cmd == "add" and len(sys.argv) > 2:
            symbol = sys.argv[2]
            name = sys.argv[3] if len(sys.argv) > 3 else None
            add_stock(symbol, name)
            return
        
        elif cmd == "remove" and len(sys.argv) > 2:
            remove_stock(sys.argv[2])
            return
        
        elif cmd == "list":
            list_stocks()
            return
        
        elif cmd == "help":
            print("""
股票监控脚本用法:
  python3 stock_monitor.py           - 运行监控
  python3 stock_monitor.py list      - 列出所有股票
  python3 stock_monitor.py add NVDA  - 添加股票
  python3 stock_monitor.py add NVDA "NVIDIA Corp" - 添加股票(带名称)
  python3 stock_monitor.py remove NVDA - 删除股票
            """)
            return
    
    log("=" * 50)
    log("开始股票监控任务")
    log(f"请求延迟: {REQUEST_DELAY}秒/次")
    
    stocks = load_stocks()
    log(f"监控股票列表: {[s['symbol'] for s in stocks]}")
    
    stock_data_list = []
    use_twelvedata = False
    
    for stock in stocks:
        symbol = stock["symbol"]
        name = stock["name"]
        
        log(f"正在获取 {symbol} 数据...")
        
        data, use_twelvedata = get_stock_data(symbol, use_twelvedata)
        
        stock_data_list.append({
            "symbol": symbol,
            "name": name,
            "data": data
        })
        
        price = data["price"]
        source = price.get("source") if price else "N/A"
        log(f"{symbol} 完成 - 价格: {format_price(price.get('current') if price else None)} (来源: {source})")
    
    message = build_message(stock_data_list, use_twelvedata)
    print("\n" + "=" * 50)
    print(message)
    print("=" * 50 + "\n")
    
    send_feishu_message(message)
    
    log("股票监控任务完成")

if __name__ == "__main__":
    main()
