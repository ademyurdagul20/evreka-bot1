from binance.client import Client
import pandas as pd
import ta
import requests
import time

# Binance API bilgileri (public key yeterli, yoksa '' bırakabilirsin)
API_KEY = ''
API_SECRET = ''
client = Client(API_KEY, API_SECRET)

# Telegram bilgileri
TELEGRAM_TOKEN = '7744047969:AAESz5iG39SJzMK78-aH4nhDuXsmKGymIwk'
TELEGRAM_CHAT_ID = '1509101795'

last_signal = None

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message
    }
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram mesajı gönderilemedi: {e}")

def get_klines(symbol, interval, limit=500):
    klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'volume',
                                       'close_time', 'quote_asset_volume', 'number_of_trades',
                                       'taker_buy_base', 'taker_buy_quote', 'ignore'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df.set_index('time', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    return df

def calculate_indicators(df):
    close = df['close']

    # Bollinger Bands
    bb_indicator = ta.volatility.BollingerBands(close, window=30, window_dev=2)
    df['bb_upper'] = bb_indicator.bollinger_hband()
    df['bb_lower'] = bb_indicator.bollinger_lband()

    # Stochastic RSI #1
    stochrsi1 = ta.momentum.StochRSIIndicator(close, window=8, smooth1=3, smooth2=3)
    df['stochrsi1_k'] = stochrsi1.stochrsi_k()
    df['stochrsi1_d'] = stochrsi1.stochrsi_d()

    # RSI
    rsi = ta.momentum.RSIIndicator(close, window=13)
    df['rsi'] = rsi.rsi()

    # Stochastic RSI #2
    stochrsi2 = ta.momentum.StochRSIIndicator(close, window=14, smooth1=3, smooth2=3)
    df['stochrsi2_k'] = stochrsi2.stochrsi_k()
    df['stochrsi2_d'] = stochrsi2.stochrsi_d()

    # TRIX
    trix = ta.trend.TRIXIndicator(close, window=18)
    df['trix'] = trix.trix()

    # MACD
    macd = ta.trend.MACD(close)
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    # CCI
    cci = ta.trend.CCIIndicator(df['high'], df['low'], close, window=25)
    df['cci'] = cci.cci()

    # Williams %R
    wr = ta.momentum.WilliamsRIndicator(df['high'], df['low'], close, lbp=10)
    df['williams_r'] = wr.williams_r()

    return df

def check_long_conditions(df):
    last = df.iloc[-1]
    previous = df.iloc[-2]

    # Fiyat son kapanış lower bandın altında olmalı
    if last['close'] > last['bb_lower']:
        return None

    # stochrsi1_k değeri 5'ten düşük olmalı (0 tam tutmaz, biraz esnetelim)
    if last['stochrsi1_k'] > 5:
        return None

    # RSI 30'dan düşük olmalı
    if last['rsi'] >= 30:
        return None

    # stochrsi2_k 10'un altına kesmeli (cross down)
    if not (last['stochrsi2_k'] < 10 and previous['stochrsi2_k'] >= 10):
        return None

    # TRIX negatif olmalı
    if not (df['trix'] < 0).any():
        return None

    # MACD ve signal negatif olmalı
    if not ((df['macd'] < 0) & (df['macd_signal'] < 0)).any():
        return None

    # Williams %R -90 altından yukarı kesmeli (cross up)
    if not (df['williams_r'] < -90).any() or not (previous['williams_r'] < -90 and last['williams_r'] > -90):
        return None

    # CCI -90 altından yukarı kesmeli (cross up)
    if not (df['cci'] < -90).any() or not (previous['cci'] < -90 and last['cci'] > -90):
        return None

    return "LONG"

def check_short_conditions(df):
    last = df.iloc[-1]
    previous = df.iloc[-2]

    # Fiyat son kapanış upper bandın üstünde olmalı
    if last['close'] < last['bb_upper']:
        return None

    # stochrsi1_k değeri 95'ten yüksek olmalı (100 tam tutmaz, biraz esnetelim)
    if last['stochrsi1_k'] < 95:
        return None

    # RSI 65'ten yüksek olmalı
    if last['rsi'] <= 65:
        return None

    # stochrsi2_k 90'ın üstüne kesmeli (cross up)
    if not (last['stochrsi2_k'] > 90 and previous['stochrsi2_k'] <= 90):
        return None

    # TRIX pozitif olmalı
    if not (df['trix'] > 0).any():
        return None

    # MACD ve signal pozitif olmalı
    if not ((df['macd'] > 0) & (df['macd_signal'] > 0)).any():
        return None

    # Williams %R -20 üstünden aşağı kesmeli (cross down)
    if not (df['williams_r'] > -20).any() or not (previous['williams_r'] > -20 and last['williams_r'] < -20):
        return None

    # CCI +90 üstünden aşağı kesmeli (cross down)
    if not (df['cci'] > 90).any() or not (previous['cci'] > 90 and last['cci'] < 90):
        return None

    return "SHORT"

def run():
    global last_signal
    symbol = "CRVUSDT"
    interval = Client.KLINE_INTERVAL_15MINUTE

    print("Sinyal bekleniyor...")

    while True:
        df = get_klines(symbol, interval)
        df = calculate_indicators(df)

        long_signal = check_long_conditions(df)
        short_signal = check_short_conditions(df)

        if long_signal == "LONG" and last_signal != "LONG":
            send_telegram_message("📈 LONG sinyali geldi: CRVUSDT")
            last_signal = "LONG"
            print("LONG sinyali gönderildi.")
        elif short_signal == "SHORT" and last_signal != "SHORT":
            send_telegram_message("📉 SHORT sinyali geldi: CRVUSDT")
            last_signal = "SHORT"
            print("SHORT sinyali gönderildi.")
        else:
            print("Sinyal yok, bekleniyor...")

        time.sleep(30)

if __name__ == "__main__":
    run()