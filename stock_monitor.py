#!/usr/bin/env python3
"""
股票监控脚本 (Twelvedata 版)
每天收市后获取股票价格变化，推送到飞书
"""

import requests
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 配置文件路径
CONFIG_DIR = Path(__file__).parent
STOCKS_FILE = CONFIG_DIR / "stocks.json"
LOG_FILE = CONFIG_DIR / "stock_monitor.log"

# API 配置
API_KEY = "785bfc4b878c4bc9a5cc517262c26f25"
API_BASE = "https://api.twelvedata.com"

# 默认股票列表
DEFAULT_STOCKS = [
    {"symbol": "ICLN", "name": "iShares Global Clean Energy ETF"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation 英伟达"},
    {"symbol": "TSM", "name": "Taiwan Semiconductor 台积电"},
    {"symbol": "GOOGL", "name": "Alphabet Inc. Google"},
]

# 飞书 Webhook URL (需要手动设置)
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK_URL", "")

def load_stocks():
    """加载股票列表"""
    if STOCKS_FILE.exists():
        with open(STOCKS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return DEFAULT_STOCKS

def save_stocks(stocks):
    """保存股票列表"""
    with open(STOCKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)

def get_stock_price(symbol):
    """获取股票价格和涨跌幅"""
    try:
        # 获取历史数据
        url = f"{API_BASE}/time_series"
        params = {
            "symbol": symbol,
            "interval": "1day",
            "outputsize": 5,
            "apikey": API_KEY
        }
        
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        if data.get("status") == "ok" and "values" in data:
            values = data["values"]
            if len(values) >= 2:
                current = float(values[0]["close"])
                previous = float(values[1]["close"])
                volume = int(values[0]["volume"])
                high = float(values[0]["high"])
                low = float(values[0]["low"])
                
                change = current - previous
                change_pct = (change / previous * 100) if previous else 0
                
                return {
                    "current": current,
                    "previous": previous,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": volume,
                    "high": high,
                    "low": low,
                    "currency": "USD",
                    "date": values[0]["datetime"]
                }
    except Exception as e:
        log(f"获取 {symbol} 失败: {e}")
    
    return None

def get_stock_company(symbol):
    """获取公司信息 (通过描述端点)"""
    try:
        url = f"{API_BASE}/symbol_search"
        params = {
            "symbol": symbol,
            "apikey": API_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get("results") and len(data["results"]) > 0:
            result = data["results"][0]
            return {
                "name": result.get("description", ""),
                "exchange": result.get("exchange", ""),
                "type": result.get("type", "")
            }
    except Exception as e:
        log(f"获取 {symbol} 公司信息失败: {e}")
    
    return {}

def log(message):
    """写日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_msg)
    print(log_msg.strip())

def format_price(price):
    """格式化价格"""
    if price is None:
        return "N/A"
    return f"{price:.2f}"

def format_change(change, change_pct):
    """格式化涨跌幅"""
    if change is None:
        return "N/A"
    emoji = "📈" if change >= 0 else "📉"
    sign = "+" if change >= 0 else ""
    return f"{emoji} {sign}{format_price(change)} ({sign}{change_pct:.2f}%)"

def format_volume(volume):
    """格式化成交量"""
    if not volume:
        return "N/A"
    if volume >= 1_000_000_000:
        return f"{volume/1_000_000_000:.2f}B"
    elif volume >= 1_000_000:
        return f"{volume/1_000_000:.2f}M"
    elif volume >= 1_000:
        return f"{volume/1_000:.2f}K"
    return str(volume)

def build_message(stock_data_list):
    """构建飞书消息"""
    date = datetime.now().strftime("%Y-%m-%d")
    
    lines = [f"📊 每日股票监控 - {date}\n"]
    
    for stock in stock_data_list:
        symbol = stock["symbol"]
        name = stock["name"]
        price_data = stock["price"]
        
        if price_data:
            change_pct = price_data.get("change_pct", 0)
            emoji = "📈" if change_pct >= 0 else "📉"
            current = price_data.get("current", 0)
            lines.append(f"{emoji} {symbol} | ${current:.2f} | {change_pct:+.2f}%")
        else:
            lines.append(f"❌ {symbol} 数据获取失败")
    
    # 添加统计
    gainers = sum(1 for s in stock_data_list if s.get("price", {}).get("change_pct", 0) > 0)
    losers = sum(1 for s in stock_data_list if s.get("price", {}).get("change_pct", 0) < 0)
    lines.append(f"\n📈 {gainers} | 📉 {losers}")
    
    return "\n".join(lines)

def send_feishu_message(content, webhook_url=None):
    """发送飞书消息"""
    if not webhook_url:
        webhook_url = FEISHU_WEBHOOK
    
    if not webhook_url:
        log("未配置飞书 Webhook URL，请设置环境变量 FEISHU_WEBHOOK_URL")
        # 打印消息而不是发送
        print("\n" + "=" * 60)
        print("消息内容 (未发送 - 缺少 Webhook URL):")
        print("=" * 60)
        print(content)
        print("=" * 60)
        return False
    
    # 构建飞书 Text 消息
    message = {
        "msg_type": "text",
        "content": {
            "text": content
        }
    }
    
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
    """添加股票"""
    stocks = load_stocks()
    
    # 检查是否已存在
    for stock in stocks:
        if stock["symbol"].upper() == symbol.upper():
            log(f"股票 {symbol} 已存在")
            return False
    
    # 尝试获取公司信息
    if not name:
        company = get_stock_company(symbol)
        name = company.get("name", symbol)
    
    stocks.append({"symbol": symbol.upper(), "name": name or symbol})
    save_stocks(stocks)
    log(f"已添加股票: {symbol} - {name}")
    return True

def remove_stock(symbol):
    """删除股票"""
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
    """列出所有股票"""
    stocks = load_stocks()
    print("\n当前监控的股票:")
    for i, stock in enumerate(stocks, 1):
        print(f"  {i}. {stock['symbol']} - {stock['name']}")
    print()

def main():
    """主函数"""
    # 检查命令行参数
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

设置飞书 Webhook:
  export FEISHU_WEBHOOK_URL="你的飞书机器人Webhook地址"
            """)
            return
    
    # 运行监控
    log("=" * 50)
    log("开始股票监控任务")
    
    stocks = load_stocks()
    log(f"监控股票列表: {[s['symbol'] for s in stocks]}")
    
    stock_data_list = []
    
    for stock in stocks:
        symbol = stock["symbol"]
        name = stock["name"]
        
        log(f"正在获取 {symbol} 数据...")
        
        # 获取价格
        price_data = get_stock_price(symbol)
        
        stock_data_list.append({
            "symbol": symbol,
            "name": name,
            "price": price_data
        })
        
        log(f"{symbol} 完成 - 价格: {price_data.get('current') if price_data else 'N/A'}")
    
    # 构建消息
    message = build_message(stock_data_list)
    print("\n" + "=" * 50)
    print(message)
    print("=" * 50 + "\n")
    
    # 发送飞书
    send_feishu_message(message)
    
    log("股票监控任务完成")

if __name__ == "__main__":
    main()
