from flask import Flask, render_template_string, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import json
import uuid
import random
import urllib.parse
import sqlite3
import os
import urllib.request
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'winnerpari_secure_key_2026')

# --- SECURE API KEY CONFIGURATION ---
FLUTTERWAVE_PUBLIC_KEY = os.environ.get('FLUTTERWAVE_PUBLIC_KEY', 'FLWPUBK-a705d605724e2735dd4e459ac95ac43-X')
FLUTTERWAVE_SECRET_KEY = os.environ.get('FLUTTERWAVE_SECRET_KEY', '')

# --- YOUR REAL FOOTBALL API CREDENTIALS ---
FOOTBALL_API_KEY = os.environ.get('FOOTBALL_API_KEY', '75a591933fa60e7ca2e657158d2413c7')
FOOTBALL_API_ENDPOINT = os.environ.get('FOOTBALL_API_ENDPOINT', 'https://v3.football.api-sports.io/fixtures?live=all')

# --- DEDICATED CURRENCY FLUTTERWAVE LINKS ---
CURRENCY_FLUTTERWAVE_LINKS = {
    'NGN': 'https://flutterwave.com/pay/4y5pskcahodx',
    'EUR': 'https://flutterwave.com/pay/npujm2kdqlrm',
    'INR': 'https://flutterwave.com/pay/xmgzwju04r0n',
    'TRY': 'https://flutterwave.com/pay/xivo8wfm1ynp',
    'USD': 'https://flutterwave.com/pay/k9qbxyamd4m3',
    'GBP': 'https://flutterwave.com/pay/s6cj9gcosu3o',
    'GHS': 'https://flutterwave.com/pay/kkyyzv97r0uh'
}

def get_flutterwave_link_for_currency(currency):
    if currency in CURRENCY_FLUTTERWAVE_LINKS:
        return CURRENCY_FLUTTERWAVE_LINKS[currency]

    african_currencies = ['KES', 'ZAR', 'UGX', 'TZS', 'XOF', 'XAF', 'RWF']
    european_currencies = ['CHF', 'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF', 'RON', 'BGN']

    if currency in african_currencies:
        return CURRENCY_FLUTTERWAVE_LINKS['NGN']
    elif currency in european_currencies:
        return CURRENCY_FLUTTERWAVE_LINKS['EUR']
    else:
        return CURRENCY_FLUTTERWAVE_LINKS['USD']

# --- TWO DATABASE CONFIGURATION ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_BINDS'] = {
    'users_db': 'sqlite:///' + os.path.join(BASE_DIR, 'winnerpari.db'),
    'matches_db': 'sqlite:///' + os.path.join(BASE_DIR, 'matches_data.db')
}
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'winnerpari.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

SUPPORT_WHATSAPP_NUMBER = "+40725276530"

# --- CRYPTO WALLET CONFIGURATIONS ---
CRYPTO_WALLETS = [
    {
        "id": "btc",
        "name": "Bitcoin (BTC)",
        "network": "Bitcoin Network",
        "address": "bc1q93pce4yqx3alyxf4dkmqqg3eg97rzswhrj0j9c"
    },
    {
        "id": "erc20",
        "name": "ERC20 (ETH, USDT, USDC)",
        "network": "Ethereum Network (ERC20)",
        "address": "0x1a0e0aa77917a2df4fd9af9caf8ba555166e9275"
    },
    {
        "id": "bep20",
        "name": "BEP20 (BNB, USDT, USDC)",
        "network": "Binance Smart Chain (BEP20)",
        "address": "0x1a0e0aa77917a2df4fd9af9caf8ba555166e9275"
    },
    {
        "id": "sol",
        "name": "Solana (SOL, USDT, USDC)",
        "network": "Solana Network",
        "address": "4MtfYqdKG7WKmZist4mviRHauqsQxTPjvnGNBt3UjEWw"
    },
    {
        "id": "trc20",
        "name": "TRC20 (TRX, USDT)",
        "network": "Tron Network (TRC20)",
        "address": "TKiwrSNMiTMgskbjDUBk1RTmvptQLDCPzT"
    }
]

# --- DATABASE MODELS ---
class User(db.Model):
    __bind_key__ = 'users_db'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    balance = db.Column(db.Float, default=0.00)
    bonus_balance = db.Column(db.Float, default=0.00)
    currency = db.Column(db.String(10), default='USD')
    is_admin = db.Column(db.Boolean, default=False)
    welcomed = db.Column(db.Boolean, default=False)
    referred_by = db.Column(db.String(80), nullable=True)
    is_blocked = db.Column(db.Boolean, default=False)
    block_reason = db.Column(db.Text, nullable=True)

class Setting(db.Model):
    __bind_key__ = 'users_db'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)

class Bet(db.Model):
    __bind_key__ = 'users_db'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='bets')
    ticket_items_json = db.Column(db.Text, nullable=False)
    total_odds = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    potential_win = db.Column(db.Float, nullable=False)
    ticket_type = db.Column(db.String(20), default='Single')
    booking_code = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(20), default='Pending')
    celebrated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BookingSlip(db.Model):
    __bind_key__ = 'users_db'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    slip_data = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DepositRequest(db.Model):
    __bind_key__ = 'users_db'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='deposits')
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='Pending')
    support_message = db.Column(db.Text, default='')
    support_has_updated = db.Column(db.Boolean, default=True)
    user_acknowledged = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WithdrawalRequest(db.Model):
    __bind_key__ = 'users_db'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='withdrawals')
    amount = db.Column(db.Float, nullable=False)
    payout_method = db.Column(db.String(100), nullable=False)
    account_details = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    support_message = db.Column(db.Text, default='Your withdrawal request is received and under review by management.')
    support_has_updated = db.Column(db.Boolean, default=False)
    user_acknowledged = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Match(db.Model):
    __bind_key__ = 'matches_db'
    id = db.Column(db.Integer, primary_key=True)
    sport = db.Column(db.String(30), default='Football')
    league = db.Column(db.String(80), default='Global League')
    team_home = db.Column(db.String(100), nullable=False)
    team_away = db.Column(db.String(100), nullable=False)
    odds_home = db.Column(db.Float, nullable=False)
    odds_draw = db.Column(db.Float, nullable=False)
    odds_away = db.Column(db.Float, nullable=False)
    over_under_json = db.Column(db.Text, default='{}')
    odds_btts_yes = db.Column(db.Float, default=1.75)
    odds_btts_no = db.Column(db.Float, default=2.00)
    correct_scores_json = db.Column(db.Text, default='{}')
    match_date = db.Column(db.String(20), default='2026-10-18')
    match_time = db.Column(db.String(20), default='20:00')
    status = db.Column(db.String(20), default='Upcoming')
    score_home = db.Column(db.Integer, default=0)
    score_away = db.Column(db.Integer, default=0)
    target_score_home = db.Column(db.Integer, default=1)
    target_score_away = db.Column(db.Integer, default=0)
    match_minute = db.Column(db.String(10), default='')
    is_auto = db.Column(db.Boolean, default=True)
    winner = db.Column(db.String(20), nullable=True)

# --- HELPER FUNCTIONS ---
CURRENCY_RATES_TO_USD = {
    'USD': 1.0, 'EUR': 0.90, 'GBP': 0.78, 'NGN': 1330.0,
    'CAD': 1.35, 'AUD': 1.50, 'JPY': 150.0, 'INR': 83.0,
    'KES': 130.0, 'GHS': 15.0, 'ZAR': 18.5, 'CHF': 0.90, 'CNY': 7.20,
    'TRY': 32.5, 'UZS': 12600.0
}

def detect_currency_by_ip(remote_ip):
    try:
        if not remote_ip or remote_ip in ['127.0.0.1', 'localhost', '::1']:
            return 'NGN'
        return 'NGN'
    except Exception:
        return 'NGN'

def get_now_local():
    return datetime.utcnow() + timedelta(hours=1)

def get_min_deposit(currency):
    if currency == 'NGN': return 5000.0
    if currency == 'GHS': return 100.0
    if currency == 'INR': return 1500.0
    rate_to_gbp = CURRENCY_RATES_TO_USD.get(currency, 1.0) / CURRENCY_RATES_TO_USD.get('GBP', 0.78)
    return round(5.0 * rate_to_gbp, 2)

def get_min_stake(currency):
    if currency == 'NGN': return 5000.0
    if currency == 'GHS': return 50.0
    if currency == 'INR': return 500.0
    rate_to_gbp = CURRENCY_RATES_TO_USD.get(currency, 1.0) / CURRENCY_RATES_TO_USD.get('GBP', 0.78)
    return round(10.0 * rate_to_gbp, 2)

def mask_username(username):
    if not username: return "Player"
    if len(username) <= 2: return username[0] + "***"
    return username[0] + "***" + username[-1]

def check_request_expirations():
    threshold = datetime.utcnow() - timedelta(minutes=30)
    pending_deps = DepositRequest.query.filter_by(status='Pending').all()
    for dep in pending_deps:
        if dep.created_at < threshold:
            dep.status = 'Cancelled'
            dep.support_message = 'Payment cancelled due to 30-minute timeout.'
            dep.user_acknowledged = True
    db.session.commit()

def generate_correct_scores(odds_home=2.0, odds_away=3.0, odds_draw=3.3):
    scores = {}
    home_bias = max(0.7, min(1.4, odds_home / 2.2))
    away_bias = max(0.7, min(1.4, odds_away / 2.2))

    for h in range(6):
        for a in range(6):
            if h == 0 and a == 0:
                base = 5.62
            elif (h == 1 and a == 0):
                base = 9.56 * home_bias
            elif (h == 0 and a == 1):
                base = 10.50 * away_bias
            elif (h == 1 and a == 1):
                base = 12.65
            elif (h == 2 and a == 0):
                base = 13.89 * home_bias
            elif (h == 0 and a == 2):
                base = 14.50 * away_bias
            elif (h == 2 and a == 1):
                base = 12.76 * home_bias
            elif (h == 1 and a == 2):
                base = 13.20 * away_bias
            else:
                base = 14.0 + (h + a) * 3.5 + abs(h - a) * 2.0
                if h > a:
                    base *= home_bias
                elif a > h:
                    base *= away_bias

            score_val = round(max(5.0, base + random.uniform(-0.4, 0.4)), 2)
            scores[f"{h}-{a}"] = score_val
    return json.dumps(scores)

def generate_over_under_lines():
    lines = {}
    lines["0.5"] = {"over": round(random.uniform(1.07, 1.15), 2), "under": round(random.uniform(5.00, 8.50), 2)}
    lines["1.5"] = {"over": round(random.uniform(1.30, 1.45), 2), "under": round(random.uniform(2.40, 3.20), 2)}
    lines["2.5"] = {"over": round(random.uniform(1.70, 2.10), 2), "under": round(random.uniform(1.70, 2.10), 2)}
    lines["3.5"] = {"over": round(random.uniform(2.60, 3.50), 2), "under": round(random.uniform(1.30, 1.48), 2)}
    lines["4.5"] = {"over": round(random.uniform(4.50, 7.00), 2), "under": round(random.uniform(1.10, 1.20), 2)}
    return json.dumps(lines)

def format_match_pretty_date(date_str, time_str):
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return dt.strftime("%A, %b %d - %H:%M")
    except:
        return f"{date_str} {time_str}"

def process_match_settlement(match_obj):
    match_obj.status = 'Finished'
    match_obj.score_home = match_obj.target_score_home
    match_obj.score_away = match_obj.target_score_away
    if match_obj.score_home > match_obj.score_away:
        match_obj.winner = 'Home'
    elif match_obj.score_home < match_obj.score_away:
        match_obj.winner = 'Away'
    else:
        match_obj.winner = 'Draw'

    pending_tickets = Bet.query.filter_by(status='Pending').all()
    for ticket in pending_tickets:
        items = json.loads(ticket.ticket_items_json)
        all_finished = True
        for item in items:
            mo = Match.query.get(item['matchId'])
            if not mo or mo.status != 'Finished':
                all_finished = False

        if all_finished:
            user = User.query.get(ticket.user_id)
            if not user: continue

            overall_win = True
            for item in items:
                mo = Match.query.get(item['matchId'])
                p = item['pick']
                iw = False
                m_tot = mo.score_home + mo.score_away

                if p == 'Home' and mo.winner == 'Home': iw = True
                elif p == 'Draw' and mo.winner == 'Draw': iw = True
                elif p == 'Away' and mo.winner == 'Away': iw = True
                elif p.startswith('Over_'):
                    line = float(p.replace('Over_', ''))
                    if m_tot > line: iw = True
                elif p.startswith('Under_'):
                    line = float(p.replace('Under_', ''))
                    if m_tot < line: iw = True
                elif p == 'BTTS Yes' and mo.score_home > 0 and mo.score_away > 0: iw = True
                elif p == 'BTTS No' and (mo.score_home == 0 or mo.score_away == 0): iw = True
                elif p.startswith('CS_'):
                    if p.replace('CS_', '') == f"{mo.score_home}-{mo.score_away}": iw = True
                if not iw: overall_win = False

            if overall_win:
                ticket.status = 'Won'
                user.balance += ticket.potential_win
            else:
                ticket.status = 'Lost'
    db.session.commit()

# --- REAL FOOTBALL API FETCH ENGINE ---
def fetch_and_store_real_matches():
    headers = {
        "x-apisports-key": FOOTBALL_API_KEY,
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(FOOTBALL_API_ENDPOINT, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            matches_list = data.get('response', []) 
            
            for item in matches_list:
                league = item.get('league', {}).get('name', 'Global League')
                home = item.get('teams', {}).get('home', {}).get('name', 'Home Team')
                away = item.get('teams', {}).get('away', {}).get('name', 'Away Team')
                
                raw_date = item.get('fixture', {}).get('date', '2026-10-18T20:00:00Z')
                match_date_str = raw_date[:10]
                match_time_str = raw_date[11:16]
                
                existing = Match.query.filter_by(team_home=home, team_away=away, match_date=match_date_str).first()
                if not existing:
                    oh = round(random.uniform(1.40, 3.20), 2)
                    od = round(random.uniform(3.00, 3.80), 2)
                    oa = round(random.uniform(2.10, 4.50), 2)
                    
                    m = Match(
                        sport='Football',
                        league=league,
                        team_home=home,
                        team_away=away,
                        odds_home=oh,
                        odds_draw=od,
                        odds_away=oa,
                        target_score_home=random.choice([0, 1, 2, 3]),
                        target_score_away=random.choice([0, 1, 2]),
                        match_date=match_date_str,
                        match_time=match_time_str,
                        status='Upcoming',
                        over_under_json=generate_over_under_lines(),
                        correct_scores_json=generate_correct_scores(oh, oa, od),
                        is_auto=False
                    )
                    db.session.add(m)
            db.session.commit()
    except Exception as e:
        print(f"Real API Match Fetch Error: {e}")

def run_automated_bookmaker_engine():
    check_request_expirations()
    now_dt = get_now_local()
    today_str = now_dt.strftime('%Y-%m-%d')

    fetch_and_store_real_matches()

    upcoming_to_live = Match.query.filter(
        Match.status == 'Upcoming',
        Match.sport == 'Football',
        Match.match_date <= today_str
    ).all()

    for m in upcoming_to_live:
        try:
            m_datetime = datetime.strptime(f"{m.match_date} {m.match_time}", "%Y-%m-%d %H:%M")
            if m_datetime <= now_dt:
                m.status = 'Live'
                m.match_minute = "1'"
        except Exception:
            pass

    live_matches = Match.query.filter(
        Match.status == 'Live',
        Match.sport == 'Football'
    ).all()

    for m in live_matches:
        try:
            m_datetime = datetime.strptime(f"{m.match_date} {m.match_time}", "%Y-%m-%d %H:%M")
            real_elapsed_mins = (now_dt - m_datetime).total_seconds() / 60
            elapsed_mins = int(real_elapsed_mins * 2) + 1

            if elapsed_mins >= 90:
                m.match_minute = "90'"
                process_match_settlement(m)
            else:
                current_min = min(elapsed_mins, 89)
                m.match_minute = f"{current_min}'"

                total_target_goals = (m.target_score_home or 0) + (m.target_score_away or 0)
                if total_target_goals > 0:
                    step_interval = max(10, int(75 / (total_target_goals + 1)))
                    simulated_home = 0
                    simulated_away = 0

                    for i in range(1, total_target_goals + 1):
                        goal_minute = 10 + (i * step_interval)
                        if current_min >= goal_minute:
                            if simulated_home < m.target_score_home and (simulated_away >= m.target_score_away or i % 2 != 0):
                                simulated_home += 1
                            elif simulated_away < m.target_score_away:
                                simulated_away += 1

                    m.score_home = simulated_home
                    m.score_away = simulated_away
                else:
                    m.score_home = 0
                    m.score_away = 0
        except Exception:
            pass

    old_matches = Match.query.filter(Match.match_date < today_str).all()
    for om in old_matches:
        db.session.delete(om)
    db.session.commit()

with app.app_context():
    db.create_all()

    db_path = os.path.join(BASE_DIR, 'winnerpari.db')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for table in ['deposit_request', 'withdrawal_request']:
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [col[1] for col in cursor.fetchall()]
            if 'support_message' not in columns:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN support_message TEXT;")
            if 'support_has_updated' not in columns:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN support_has_updated BOOLEAN DEFAULT 0;")
            if 'user_acknowledged' not in columns:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_acknowledged BOOLEAN DEFAULT 0;")
        cursor.execute("PRAGMA table_info(user);")
        user_cols = [col[1] for col in cursor.fetchall()]
        if 'bonus_balance' not in user_cols:
            cursor.execute("ALTER TABLE user ADD COLUMN bonus_balance FLOAT DEFAULT 0.0;")
        if 'referred_by' not in user_cols:
            cursor.execute("ALTER TABLE user ADD COLUMN referred_by VARCHAR(80);")
        if 'is_blocked' not in user_cols:
            cursor.execute("ALTER TABLE user ADD COLUMN is_blocked BOOLEAN DEFAULT 0;")
        if 'block_reason' not in user_cols:
            cursor.execute("ALTER TABLE user ADD COLUMN block_reason TEXT;")
        conn.commit()
        conn.close()

    admin_user = User.query.filter_by(email='admin@winnerpari.com').first()
    if not admin_user:
        admin_user = User(username='Winnerpari Admin', email='admin@winnerpari.com', password='adminpassword123', balance=100000.0, is_admin=True, welcomed=True)
        db.session.add(admin_user)
        db.session.commit()

    if not Setting.query.filter_by(key='notification_email').first():
        db.session.add(Setting(key='notification_email', value='admin@winnerpari.com'))
        db.session.commit()

# --- WINNERPARI COMPLETE BASE TEMPLATE ---
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Winnerpari - Professional Sportsbook</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
    <style>
        :root {
            --mp-bg: #0f172a;
            --mp-card-bg: #1e293b;
            --mp-border: #334155;
            --mp-accent: #e11d48;
            --mp-success: #00c853;
            --mp-text: #f8fafc;
            --mp-text-muted: #94a3b8;
        }

        body { 
            background-color: var(--mp-bg); 
            color: var(--mp-text); 
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; 
            padding-bottom: 90px; 
            font-size: 0.92rem; 
        }

        .sporty-header { 
            background-color: #0b132b; 
            border-bottom: 2px solid var(--mp-accent);
            padding: 10px 16px; 
            color: #ffffff; 
        }
        .sporty-brand { 
            font-size: 1.25rem; 
            color: #ffffff; 
            text-decoration: none; 
            font-weight: 900; 
            letter-spacing: 0.5px;
        }
        .sporty-brand i { color: var(--mp-accent); }

        .balance-badge { 
            background-color: rgba(0, 200, 83, 0.15); 
            color: #00ff68; 
            border: 1px solid rgba(0, 200, 83, 0.3);
            border-radius: 20px; 
            padding: 4px 12px; 
            font-size: 0.8rem; 
            font-weight: 800; 
        }
        
        .deposit-top-btn { 
            background: var(--mp-accent); 
            color: #ffffff; 
            border-radius: 20px; 
            font-weight: 800; 
            font-size: 0.75rem; 
            padding: 5px 14px; 
            border: none; 
            text-decoration: none; 
            transition: opacity 0.2s;
        }
        .deposit-top-btn:hover { opacity: 0.9; color: #ffffff; }

        .dropdown-menu-dark { 
            background-color: #1e293b !important; 
            border: 1px solid var(--mp-border) !important; 
            z-index: 99999 !important; 
            box-shadow: 0 10px 25px rgba(0,0,0,0.4) !important; 
        }
        .dropdown-menu-dark .dropdown-item { 
            color: var(--mp-text) !important; 
            padding: 8px 14px !important; 
            font-weight: 600 !important; 
            font-size: 0.88rem !important; 
            cursor: pointer; 
        }
        .dropdown-menu-dark .dropdown-item:hover { 
            background-color: #334155 !important; 
            color: var(--mp-accent) !important; 
        }

        .card { 
            background-color: var(--mp-card-bg); 
            border: 1px solid var(--mp-border); 
            color: var(--mp-text); 
            border-radius: 10px; 
            box-shadow: 0 4px 12px rgba(0,0,0,0.2); 
            margin-bottom: 12px; 
        }

        .btn-success { background-color: var(--mp-success); border: none; font-weight: 700; color: #ffffff; }
        .btn-success:hover { background-color: #00b048; color: #ffffff; }

        .table { color: var(--mp-text); border-color: var(--mp-border); font-size: 0.85rem; white-space: nowrap; }
        .table-responsive { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }

        .form-control, .form-select { 
            background-color: #0b132b; 
            border: 1px solid var(--mp-border); 
            color: var(--mp-text); 
            font-weight: 600; 
            font-size: 0.88rem; 
            padding: 8px 12px; 
        }
        .form-control:focus, .form-select:focus { 
            background-color: #0b132b; 
            border-color: var(--mp-accent); 
            color: var(--mp-text); 
            box-shadow: 0 0 0 0.2rem rgba(225, 29, 72, 0.25); 
        }

        .sport-tabs { 
            background: #1e293b; 
            border: 1px solid var(--mp-border);
            border-radius: 8px;
            overflow-x: auto; 
            white-space: nowrap; 
        }
        .sport-tab-btn { 
            background: none; 
            border: none; 
            color: var(--mp-text-muted); 
            font-weight: 700; 
            padding: 12px 18px; 
            font-size: 0.85rem; 
            transition: all 0.2s; 
            text-decoration: none; 
            display: inline-block; 
        }
        .sport-tab-btn.active, .sport-tab-btn:hover { 
            color: #ffffff; 
            background-color: rgba(225, 29, 72, 0.15);
            border-bottom: 3px solid var(--mp-accent); 
        }

        .ticker-banner { 
            background: #0b132b; 
            color: #ffffff; 
            padding: 8px 0; 
            font-size: 0.8rem; 
            border-bottom: 1px solid var(--mp-border); 
            white-space: nowrap; 
            overflow: hidden; 
            font-weight: 600; 
        }
        .ticker-content { display: inline-block; animation: marquee 30s linear infinite; }
        @keyframes marquee { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }

        .match-row { 
            background-color: var(--mp-card-bg); 
            border: 1px solid var(--mp-border); 
            border-radius: 10px; 
            padding: 12px; 
            margin-bottom: 10px; 
            transition: border-color 0.2s;
        }
        .match-row:hover { border-color: #475569; }

        .odds-btn { 
            background-color: #0b132b; 
            border: 1px solid var(--mp-border); 
            color: #38bdf8; 
            font-weight: 800; 
            width: 100%; 
            border-radius: 6px; 
            padding: 8px 0; 
            font-size: 0.82rem; 
            transition: all 0.2s; 
            cursor: pointer; 
        }
        .odds-btn:hover { background-color: #1e293b; border-color: var(--mp-accent); color: #ffffff; }
        .odds-btn.selected { background-color: var(--mp-accent) !important; color: #ffffff !important; border-color: var(--mp-accent) !important; }

        .more-options-toggle { color: #38bdf8; font-size: 0.78rem; text-decoration: none; font-weight: 700; cursor: pointer; }
        .market-sub-header { 
            background: #0b132b; 
            color: var(--mp-text); 
            font-size: 0.78rem; 
            font-weight: 800; 
            padding: 8px 12px; 
            border-radius: 6px; 
            cursor: pointer; 
            margin-top: 6px; 
            margin-bottom: 4px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            border: 1px solid var(--mp-border); 
        }

        .betslip-float-btn { 
            position: fixed; 
            bottom: 20px; 
            right: 20px; 
            z-index: 1050; 
            background: var(--mp-accent); 
            color: #ffffff; 
            border-radius: 30px; 
            padding: 12px 22px; 
            font-weight: 800; 
            font-size: 0.9rem; 
            box-shadow: 0 4px 20px rgba(225, 29, 72, 0.4); 
            cursor: pointer; 
            display: block; 
        }

        .offcanvas { background-color: var(--mp-card-bg) !important; color: var(--mp-text) !important; }
        .offcanvas-header { background-color: #0b132b !important; border-bottom: 1px solid var(--mp-border) !important; }
        
        .goog-te-combo { background-color: #0b132b !important; color: var(--mp-text) !important; border: 1px solid var(--mp-border) !important; border-radius: 4px; padding: 2px 4px; font-size: 0.75rem; font-weight: 600; }
        .goog-logo-link, .goog-te-gadget span { display: none !important; }
        .goog-te-gadget { color: transparent !important; }

        footer { 
            background-color: #0b132b; 
            border-top: 1px solid var(--mp-border); 
            margin-top: 30px; 
            padding: 20px 0; 
            text-align: center; 
            color: var(--mp-text-muted); 
            font-size: 0.82rem; 
        }

        .payment-option-card {
            border: 1.5px solid var(--mp-border);
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.2s ease-in-out;
            background-color: #0b132b;
        }
        .payment-option-card:hover {
            border-color: var(--mp-accent);
            background-color: #1e293b;
        }
        .payment-option-card.selected {
            border-color: var(--mp-accent);
            background-color: #1e293b;
            box-shadow: 0 2px 8px rgba(225, 29, 72, 0.2);
        }

        #winningCelebrationModal .modal-content {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: #ffffff !important;
        }
        .celebration-overlay {
            background: rgba(10, 15, 25, 0.92) !important;
            backdrop-filter: blur(10px);
        }
        .lucky-trophy-badge {
            font-size: 5rem;
            color: #ffd700;
            text-shadow: 0 0 25px rgba(255, 215, 0, 0.9), 0 0 50px rgba(255, 215, 0, 0.5);
            position: relative;
            display: inline-block;
        }
        .lucky-trophy-letter {
            position: absolute;
            top: 42%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 1.6rem;
            font-weight: 900;
            color: #0b1329;
            font-family: 'Segoe UI', sans-serif;
            text-shadow: 0 1px 2px rgba(255,255,255,0.7);
        }
    </style>
</head>
<body>
    <div class="sporty-header d-flex justify-content-between align-items-center sticky-top shadow-sm">
        <div class="d-flex align-items-center gap-2">
            <a class="sporty-brand" href="/"><i class="fa-solid fa-trophy me-1"></i> Winnerpari</a>
            <div id="google_translate_element" class="d-none d-md-inline-block"></div>
        </div>
        <div class="d-flex align-items-center gap-2">
            {% if session.get('user_id') %}
                <span class="balance-badge"><i class="fa-solid fa-wallet me-1"></i> {{ session.get('currency', 'USD') }} {{ "%.2f"|format(session.get('balance', 0.0)) }}</span>
                <a href="/dashboard" class="deposit-top-btn"><i class="fa-solid fa-plus me-1"></i> Deposit</a>
                <div class="dropdown">
                    <button class="btn btn-dark btn-sm rounded-circle px-2 py-1 shadow-sm border border-secondary" type="button" data-bs-toggle="dropdown" aria-expanded="false"><i class="fa-solid fa-ellipsis-vertical text-light"></i></button>
                    <ul class="dropdown-menu dropdown-menu-end dropdown-menu-dark shadow-lg py-2" style="min-width: 200px;">
                        <li><div class="px-3 py-2 text-light border-bottom mb-1" style="background-color: #0b132b;">
                            <small class="d-block text-muted text-uppercase fw-bold" style="font-size: 0.6rem;">Account Profile</small>
                            <span class="fw-bold text-light" style="font-size: 0.88rem;"><i class="fa-solid fa-user me-1 text-danger"></i> {{ session.get('username') }}</span>
                            <div class="small text-primary fw-bold" style="font-size: 0.7rem;">User ID: <strong>#{{ session.get('user_id') }}</strong></div>
                        </div></li>
                        <li><a class="dropdown-item" href="/dashboard"><i class="fa-solid fa-gauge me-2 text-danger"></i> My Dashboard</a></li>
                        <li><a class="dropdown-item" href="/bets_history"><i class="fa-solid fa-ticket me-2 text-danger"></i> Bet History</a></li>
                        <li><a class="dropdown-item" href="/settings"><i class="fa-solid fa-gear me-2 text-danger"></i> Account Settings</a></li>
                        <li><a class="dropdown-item" href="#" data-bs-toggle="modal" data-bs-target="#affiliateModal"><i class="fa-solid fa-gift me-2 text-warning"></i> Affiliate Program</a></li>
                        <li><a class="dropdown-item" href="/dashboard"><i class="fa-solid fa-wallet me-2 text-danger"></i> Deposit Funds</a></li>
                        <li><a class="dropdown-item" href="/dashboard"><i class="fa-solid fa-money-bill-transfer me-2 text-danger"></i> Withdraw Funds</a></li>
                        {% if session.get('is_admin') %}
                            <li><a class="dropdown-item text-primary fw-bold" href="/admin"><i class="fa-solid fa-user-shield me-2"></i> Admin Panel</a></li>
                        {% endif %}
                        <li><hr class="dropdown-divider my-1 border-secondary"></li>
                        <li><a class="dropdown-item text-danger fw-bold" href="/logout"><i class="fa-solid fa-right-from-bracket me-2"></i> Logout</a></li>
                    </ul>
                </div>
            {% else %}
                <a href="/login" class="btn btn-outline-light btn-sm px-2 fw-bold" style="font-size: 0.78rem;">Login</a>
                <a href="/register" class="btn btn-success btn-sm px-2 fw-bold" style="font-size: 0.78rem;">Join</a>
            {% endif %}
        </div>
    </div>

    <!-- BLOCKED ACCOUNT POPUP MODAL -->
    {% if session.get('user_id') and blocked_user_notice %}
    <div class="modal fade show" tabindex="-1" style="display: block; background: rgba(15, 23, 42, 0.95); z-index: 99999;" data-bs-backdrop="static">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content card border-danger shadow-lg text-center p-4">
                <div class="modal-body">
                    <div class="mb-3 text-danger fs-1"><i class="fa-solid fa-ban"></i></div>
                    <h3 class="text-danger fw-bold mb-2">Account Restricted</h3>
                    <p class="text-light mb-4 fw-semibold" style="white-space: pre-wrap; font-size: 0.95rem;">{{ blocked_user_notice }}</p>
                    <a href="https://wa.me/{{ support_whatsapp }}?text={{ urllib_quote('Hello Support Team, my Winnerpari account has been restricted. Please assist me with the instructions.') }}" target="_blank" class="btn btn-success w-100 fw-bold py-2 shadow mb-2">
                        <i class="fab fa-whatsapp me-1"></i> Contact Support on WhatsApp
                    </a>
                    <a href="/logout" class="btn btn-outline-secondary w-100 fw-bold py-2">Logout</a>
                </div>
            </div>
        </div>
    </div>
    {% endif %}

    <div class="bg-dark px-2 py-1 d-md-none text-end border-bottom border-secondary">
        <div id="google_translate_element_mobile" class="d-inline-block"></div>
    </div>

    <div class="ticker-banner">
        <div class="ticker-content">
            <i class="fa-solid fa-bullhorn me-2 text-warning"></i> Recent Winners:
            {% for w in recent_winners %}
                <span class="text-warning mx-2"><i class="fa-solid fa-star me-1"></i> {{ w.masked_name }} won {{ w.user.currency }} {{ "%.2f"|format(w.potential_win) }} on Winnerpari</span> &bull;
            {% endfor %}
            <span class="text-warning mx-2"><i class="fa-solid fa-star me-1"></i> J***s from UK won £1,500</span> &bull;
            <span class="text-warning mx-2"><i class="fa-solid fa-star me-1"></i> S***l from Nigeria won ₦450,000</span>
        </div>
    </div>

    <div class="container py-3" style="max-width: 1000px;">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }} alert-dismissible fade show shadow-sm py-2 small" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close btn-close-white py-2" data-bs-dismiss="alert" aria-label="Close"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </div>

    <!-- Affiliate Program Modal -->
    {% if session.get('user_id') %}
    <div class="modal fade" id="affiliateModal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content card border-warning shadow-lg">
                <div class="modal-header bg-warning text-dark py-2">
                    <h6 class="modal-title fw-bold m-0"><i class="fa-solid fa-gift me-2"></i> Winnerpari Affiliate Program</h6>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body text-light text-center py-3">
                    <div class="mb-2"><i class="fa-solid fa-handshake-angle fs-1 text-warning"></i></div>
                    <h5 class="fw-bold text-success mb-1">Invite Friends & Earn Commission!</h5>
                    <p class="text-muted small mb-3">Earn up to <strong>20% revenue share commission</strong> on every active bet placed by players registering with your link.</p>

                    <div class="p-2 rounded border border-secondary mb-3" style="background-color: #0b132b;">
                        <small class="text-muted d-block text-uppercase fw-bold mb-1" style="font-size: 0.7rem;">Your Personal Affiliate Referral Link</small>
                        <div class="input-group input-group-sm">
                            <input type="text" id="affiliateLinkInput" class="form-control text-primary fw-bold text-center" value="https://{{ request.host }}/register?ref={{ session.get('username') }}" readonly>
                            <button class="btn btn-success fw-bold px-3" type="button" onclick="copyAffiliateLink()"><i class="fa-solid fa-copy me-1"></i> Copy</button>
                        </div>
                    </div>

                    <div class="row g-2 text-center">
                        <div class="col-6">
                            <div class="p-2 rounded border border-secondary" style="background-color: #0b132b;">
                                <small class="text-muted d-block" style="font-size: 0.75rem;">Total Referrals</small>
                                <span class="fw-bold text-light" style="font-size: 0.95rem;" id="refCountVal">{{ ref_count }} Players</span>
                            </div>
                        </div>
                        <div class="col-6">
                            <div class="p-2 rounded border border-secondary" style="background-color: #0b132b;">
                                <small class="text-muted d-block" style="font-size: 0.75rem;">Commission Rate</small>
                                <span class="fw-bold text-success" style="font-size: 0.95rem;">20% Revenue</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
        function copyAffiliateLink() {
            const input = document.getElementById('affiliateLinkInput');
            input.select();
            document.execCommand('copy');
            alert('Affiliate link copied to clipboard!');
        }
    </script>
    {% endif %}

    <div class="betslip-float-btn" id="betslipBadge" data-bs-toggle="offcanvas" data-bs-target="#betslipDrawer">
        <i class="fa-solid fa-ticket me-1"></i> Bet Slip (<span id="slipCount">0</span>)
    </div>

    <div class="offcanvas offcanvas-end text-light border-start border-secondary" tabindex="-1" id="betslipDrawer" style="width: 340px;">
        <div class="offcanvas-header border-bottom py-2">
            <h6 class="offcanvas-title text-danger fw-bold m-0"><i class="fa-solid fa-receipt me-2"></i> Your Bet Slip</h6>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="offcanvas"></button>
        </div>
        <div class="offcanvas-body d-flex flex-column justify-content-between p-3">
            <div>
                <div class="input-group input-group-sm mb-3">
                    <input type="text" id="loadCodeInput" class="form-control text-uppercase fw-bold" placeholder="Enter Booking Code">
                    <button class="btn btn-outline-danger fw-bold px-3" type="button" onclick="loadBookingCode()">Load</button>
                </div>
                <div id="betslipItems" class="mb-3">
                    <p class="text-muted text-center py-4 small">No picks selected. Click on odds to add to your slip!</p>
                </div>
            </div>
            <div class="border-top border-secondary pt-3 p-2 rounded" style="background-color: #0b132b;">
                <div class="d-flex justify-content-between mb-2">
                    <span class="text-muted fw-bold small">Total Odds:</span>
                    <span class="fw-bold text-primary" id="totalOdds">1.00</span>
                </div>
                <div class="mb-3">
                    <div class="d-flex justify-content-between">
                        <label class="form-label text-muted small fw-bold">Stake ({{ session.get('currency', 'USD') }})</label>
                        <small class="text-muted" style="font-size: 0.7rem;">Min Stake: {{ session.get('currency', 'USD') }} {{ "%.2f"|format(min_stake_val) }}</small>
                    </div>
                    <input type="number" step="0.01" min="{{ min_stake_val }}" id="stakeInput" class="form-control text-center fw-bold" placeholder="{{ min_stake_val }}" oninput="calculateReturns()">
                </div>
                <div class="d-flex justify-content-between mb-3 p-2 rounded border border-secondary" style="background-color: #1e293b;">
                    <span class="text-muted fw-bold small">Potential Win:</span>
                    <span class="fw-bold text-success">{{ session.get('currency', 'USD') }} <span id="potentialWin">0.00</span></span>
                </div>
                {% if session.get('user_id') %}
                <form action="/place_accumulator" method="POST" id="accForm">
                    <input type="hidden" name="slip_data" id="slipDataInput">
                    <input type="hidden" name="stake" id="stakeFormInput">
                    <button type="submit" class="btn btn-success w-100 fw-bold shadow py-2" onclick="submitBetslip(event)">PLACE BET NOW</button>
                </form>
                {% else %}
                <a href="/login" class="btn btn-success w-100 fw-bold py-2">LOGIN TO PLACE BET</a>
                {% endif %}
            </div>
        </div>
    </div>

    <!-- Registration Welcome Banner Modal -->
    {% if session.get('user_id') and show_welcome_modal %}
    <div class="modal fade show" id="welcomeBonusModal" tabindex="-1" style="display: block; background: rgba(0,0,0,0.8);" data-bs-backdrop="static">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content card border-success shadow-lg text-center p-3">
                <div class="modal-body">
                    <div class="mb-2"><i class="fa-solid fa-gift text-success fs-1"></i></div>
                    <h4 class="text-success fw-bold mb-1">100% FIRST DEPOSIT BONUS! 🎉</h4>
                    <p class="text-light small mb-2">Make your first deposit today and receive a <strong>100% cash match bonus</strong> directly credited to your account upon approval!</p>
                    <div class="p-2 rounded border border-success my-2" style="background-color: #0b132b;">
                        <small class="text-muted d-block text-uppercase fw-bold" style="font-size: 0.65rem;">Exclusive Offer</small>
                        <span class="fw-bold text-success fs-6">First Deposit & Get 100% Match</span>
                    </div>
                    <button type="button" class="btn btn-success w-100 fw-bold shadow py-2 mb-2" onclick="closeWelcomeModalAndDeposit()">DEPOSIT NOW</button>
                    <button type="button" class="btn btn-outline-secondary btn-sm w-100 fw-bold" onclick="closeWelcomeModal()">Continue to Site</button>
                </div>
            </div>
        </div>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            var duration = 3 * 1000; var end = Date.now() + duration;
            (function frame() {
                confetti({ particleCount: 5, angle: 60, spread: 55, origin: { x: 0 }, colors: ['#e11d48', '#ffd700', '#00c853'] });
                confetti({ particleCount: 5, angle: 120, spread: 55, origin: { x: 1 }, colors: ['#e11d48', '#ffd700', '#00c853'] });
                if (Date.now() < end) { requestAnimationFrame(frame); }
            }());
        });
        function closeWelcomeModal() {
            document.getElementById('welcomeBonusModal').style.display = 'none';
            fetch('/dismiss_welcome', { method: 'POST' });
        }
        function closeWelcomeModalAndDeposit() {
            document.getElementById('welcomeBonusModal').style.display = 'none';
            fetch('/dismiss_welcome', { method: 'POST' });
            window.location.href = '/dashboard?deposit_modal=true';
        }
    </script>
    {% endif %}

    <!-- Winning Celebration Popup Modal -->
    {% if session.get('user_id') and uncelebrated_win %}
    <div class="modal fade show celebration-overlay" id="winningCelebrationModal" tabindex="-1" style="display: block;" data-bs-backdrop="static">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content text-center p-4">
                <div class="modal-body position-relative">
                    <div class="text-white-50 uppercase fw-bold mb-1" style="font-size: 0.75rem; letter-spacing: 1.5px;">You won more than 99% of all players</div>
                    <h2 class="text-white mb-1" style="font-weight: 900; letter-spacing: 1px; font-size: 1.8rem;">YOU WON</h2>
                    <div class="text-warning fw-bold fs-3 mb-2" style="text-shadow: 0 0 15px rgba(255,215,0,0.6);">{{ session.get('currency', 'USD') }} {{ "%.2f"|format(uncelebrated_win.potential_win) }}</div>

                    <div class="my-3 position-relative">
                        <div class="lucky-trophy-badge">
                            <i class="fa-solid fa-trophy"></i>
                            <span class="lucky-trophy-letter">W</span>
                        </div>
                    </div>

                    <div class="p-2 px-3 rounded border border-secondary mb-3 text-center mx-auto" style="background: rgba(255,255,255,0.08) !important; max-width: 280px;">
                        <span class="text-light small font-monospace" style="font-size: 0.78rem;">Verify Code : <strong class="text-success">{{ uncelebrated_win.booking_code or ('WP-' ~ uncelebrated_win.id) }}</strong></span>
                    </div>

                    <div class="d-flex gap-3">
                        <a href="/bets_history" class="btn btn-outline-light w-50 fw-bold py-2 small" style="border-radius: 8px; border-color: rgba(255,255,255,0.4);">Details</a>
                        <button type="button" class="btn btn-success w-50 fw-bold py-2 small shadow" style="background-color: #00c853; border-radius: 8px;" onclick="closeCelebration({{ uncelebrated_win.id }})">Show Off</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            var duration = 3 * 1000; var end = Date.now() + duration;
            (function frame() {
                confetti({ particleCount: 5, angle: 60, spread: 55, origin: { x: 0 }, colors: ['#e11d48', '#ffd700', '#ffffff'] });
                confetti({ particleCount: 5, angle: 120, spread: 55, origin: { x: 1 }, colors: ['#e11d48', '#ffd700', '#ffffff'] });
                if (Date.now() < end) { requestAnimationFrame(frame); }
            }());
        });
        function closeCelebration(ticketId) {
            document.getElementById('winningCelebrationModal').style.display = 'none';
            fetch('/dismiss_celebration/' + ticketId, { method: 'POST' });
        }
    </script>
    {% endif %}

    <!-- Deposit Messaging Popup -->
    {% if session.get('user_id') and unacknowledged_deposit and not session.get('dismissed_deposit_' ~ unacknowledged_deposit.id) %}
    <div class="modal fade show" id="adminMessageModal" tabindex="-1" style="display: block; background: rgba(0,0,0,0.8);" data-bs-backdrop="static">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content card border-danger shadow-lg">
                <div class="modal-header bg-danger text-white py-2">
                    <h6 class="modal-title fw-bold m-0"><i class="fa-solid fa-bell me-2"></i> Payment Confirmation & Waiting Status</h6>
                </div>
                <div class="modal-body text-center py-3">
                    <div class="alert alert-warning text-dark mb-2 py-2 small">
                        <strong>Deposit:</strong> {{ unacknowledged_deposit.user.currency }} {{ "%.2f"|format(unacknowledged_deposit.amount) }} | <strong>Method:</strong> {{ unacknowledged_deposit.payment_method }}
                    </div>

                    {% if not ('Crypto' in unacknowledged_deposit.payment_method or 'Support' in unacknowledged_deposit.payment_method) %}
                    <div class="mb-3">
                        <a href="{{ flutterwave_deposit_link }}" target="_blank" class="btn btn-success w-100 fw-bold py-2 shadow" style="font-size: 0.95rem;">
                            <i class="fa-solid fa-external-link-alt me-1"></i> Click Here to Open Secure Payment Page
                        </a>
                        <small class="text-muted d-block mt-1" style="font-size: 0.72rem;">If the payment page didn't pop up automatically, tap the button above.</small>
                    </div>
                    {% endif %}

                    <p class="text-light mb-3 fw-bold small" style="white-space: pre-wrap;">{{ unacknowledged_deposit.support_message }}</p>

                    <div class="mb-2">
                        {% if 'Crypto' in unacknowledged_deposit.payment_method %}
                        <div class="alert alert-info py-2 small text-start">
                            <strong>Selected Crypto Address:</strong><br>
                            <code id="popupCryptoAddr" class="text-break text-primary fw-bold" style="font-size: 0.78rem;">{{ unacknowledged_deposit.support_message.split('Address: ')[1] if 'Address: ' in unacknowledged_deposit.support_message else '' }}</code>
                        </div>
                        {% elif 'Support' in unacknowledged_deposit.payment_method %}
                        <a href="https://wa.me/{{ support_whatsapp }}?text={{ urllib_quote('Hello Support Team, I need assistance with my deposit request of ' + unacknowledged_deposit.user.currency + ' ' + '%.2f'|format(unacknowledged_deposit.amount) + ' via Other Payment Method.') }}" target="_blank" class="btn btn-success px-3 fw-bold shadow btn-sm mb-2">
                            <i class="fab fa-whatsapp me-1"></i> Message Support on WhatsApp
                        </a>
                        {% endif %}
                    </div>
                    <p class="text-muted" style="font-size: 0.75rem;">Once confirmed, your payment will be reflected in your balance. Click 'Done' if your payment is complete.</p>
                </div>
                <div class="modal-footer justify-content-between py-2" style="background-color: #0b132b;">
                    <button type="button" class="btn btn-outline-secondary btn-sm px-3 fw-bold" onclick="dismissPopup({{ unacknowledged_deposit.id }})">Later</button>
                    <a href="https://wa.me/{{ support_whatsapp }}?text={{ urllib_quote('Hello Support Team, I have a deposit request of ' + unacknowledged_deposit.user.currency + ' ' + '%.2f'|format(unacknowledged_deposit.amount) + ' via ' + unacknowledged_deposit.payment_method + '. Please assist.') }}" target="_blank" class="btn btn-success btn-sm px-2 fw-bold">
                        <i class="fab fa-whatsapp me-1"></i> WhatsApp
                    </a>
                    <form action="/acknowledge_deposit/{{ unacknowledged_deposit.id }}" method="POST" class="d-inline">
                        <button type="submit" class="btn btn-success btn-sm px-2 fw-bold shadow">Done</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            {% if not ('Crypto' in unacknowledged_deposit.payment_method or 'Support' in unacknowledged_deposit.payment_method) %}
            const autoLink = "{{ flutterwave_deposit_link }}";
            if (autoLink) {
                try { window.open(autoLink, '_blank'); } catch(e){}
            }
            {% endif %}
        });

        function dismissPopup(depId) {
            const modalEl = document.getElementById('adminMessageModal');
            if (modalEl) modalEl.style.display = 'none';
            fetch('/dismiss_deposit/' + depId, { method: 'POST' });
        }
    </script>
    {% endif %}

    <!-- Admin Deposit Message Editor Modal -->
    <div class="modal fade" id="adminMessageEditModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content card border-danger shadow-lg">
                <div class="modal-header bg-danger text-white py-2">
                    <h6 class="modal-title fw-bold m-0"><i class="fa-solid fa-pen-to-square me-2"></i> Edit Deposit Instructions</h6>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <form id="modalEditMessageForm" method="POST">
                    <div class="modal-body" style="background-color: #0b132b;">
                        <label class="form-label text-light fw-bold mb-1 small">Custom payment instructions or link:</label>
                        <textarea name="support_message" id="modalEditMessageTextarea" class="form-control text-light" rows="4" required style="font-size: 0.88rem;"></textarea>
                    </div>
                    <div class="modal-footer py-2" style="background-color: #1e293b;">
                        <button type="button" class="btn btn-outline-secondary btn-sm px-3 fw-bold" data-bs-dismiss="modal">Cancel</button>
                        <button type="submit" class="btn btn-success btn-sm px-3 fw-bold shadow">Save & Send</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <footer>
        <div class="container">
            <p class="mb-1 text-light fw-bold">&copy; 2026 Winnerpari. All Rights Reserved. &bull; <small class="text-muted">18+ Play Responsibly</small></p>
            <p class="mb-0">
                <a href="https://wa.me/{{ support_whatsapp }}?text={{ urllib_quote('Hello Support Team, I need assistance with my Winnerpari account.') }}" target="_blank" class="btn btn-success btn-sm px-3 fw-bold shadow-sm">
                    <i class="fab fa-whatsapp me-1"></i> WhatsApp Support Team
                </a>
            </p>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script type="text/javascript">
        function googleTranslateElementInit() {
            new google.translate.TranslateElement({ pageLanguage: 'en', includedLanguages: 'en,tr,uz,es,fr,de,pt,ar,hi,zh-CN', layout: google.translate.TranslateElement.InlineLayout.SIMPLE, autoDisplay: false }, 'google_translate_element');
            if(document.getElementById('google_translate_element_mobile')) {
                new google.translate.TranslateElement({ pageLanguage: 'en', includedLanguages: 'en,tr,uz,es,fr,de,pt,ar,hi,zh-CN', layout: google.translate.TranslateElement.InlineLayout.SIMPLE, autoDisplay: false }, 'google_translate_element_mobile');
            }
        }
    </script>
    <script type="text/javascript" src="//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit"></script>

    <script>
        let selectedPicks = {};
        const minStakeAllowed = {{ min_stake_val }};

        function togglePick(matchId, pick, odds, matchName) {
            const key = `match_${matchId}_${pick}`;
            const btnId = `btn_${matchId}_${pick.replace(/\s+/g, '_').replace(/\./g, '_').replace(/-/g, '_')}`;
            const btn = document.getElementById(btnId);
            if (selectedPicks[key]) {
                delete selectedPicks[key];
                if (btn) btn.classList.remove('selected');
            } else {
                if(pick === 'Home' || pick === 'Draw' || pick === 'Away') {
                    ['Home', 'Draw', 'Away'].forEach(p => {
                        delete selectedPicks[`match_${matchId}_${p}`];
                        const b = document.getElementById(`btn_${matchId}_${p}`);
                        if (b) b.classList.remove('selected');
                    });
                }
                if(pick.startsWith && pick.startsWith('CS_')) {
                    Object.keys(selectedPicks).forEach(k => {
                        if (k.startsWith(`match_${matchId}_CS_`)) {
                            delete selectedPicks[k];
                            const ob = document.getElementById(`btn_${matchId}_${k.split('_').slice(2).join('_')}`);
                            if (ob) ob.classList.remove('selected');
                        }
                    });
                }
                selectedPicks[key] = { matchId: matchId, pick: pick, odds: parseFloat(odds), matchName: matchName };
                if (btn) btn.classList.add('selected');
            }
            renderBetslip();
        }

        function renderBetslip() {
            const container = document.getElementById('betslipItems');
            const keys = Object.keys(selectedPicks);
            document.getElementById('slipCount').innerText = keys.length;
            if (keys.length === 0) {
                container.innerHTML = '<p class="text-muted text-center py-4 small">No picks selected. Click on odds to add to your slip!</p>';
                document.getElementById('totalOdds').innerText = '1.00';
                calculateReturns();
                return;
            }
            let html = ''; let totalOdds = 1.00;
            keys.forEach(k => {
                const item = selectedPicks[k];
                totalOdds *= item.odds;
                let displayPick = item.pick;
                if(displayPick.startsWith('CS_')) displayPick = 'Correct Score: ' + displayPick.replace('CS_', '');
                if(displayPick.startsWith('Over_')) displayPick = 'Over ' + displayPick.replace('Over_', '');
                if(displayPick.startsWith('Under_')) displayPick = 'Under ' + displayPick.replace('Under_', '');
                html += `
                <div class="p-2 mb-2 rounded shadow-sm border border-secondary" style="background-color: #0b132b;">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <small class="fw-bold text-light" style="font-size: 0.8rem;">${item.matchName}</small>
                        <button type="button" class="btn-close btn-close-white btn-sm" onclick="removePick('${k}')" style="font-size: 0.65rem;"></button>
                    </div>
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="badge bg-danger text-white fw-bold" style="font-size: 0.72rem;">Pick: ${displayPick}</span>
                        <span class="fw-bold text-primary small">@ ${item.odds.toFixed(2)}</span>
                    </div>
                </div>`;
            });
            container.innerHTML = html;
            document.getElementById('totalOdds').innerText = totalOdds.toFixed(2);
            calculateReturns();
        }

        function removePick(key) {
            const item = selectedPicks[key];
            if(item) {
                const btn = document.getElementById(`btn_${item.matchId}_${item.pick.replace(/\s+/g, '_').replace(/\./g, '_').replace(/-/g, '_')}`);
                if(btn) btn.classList.remove('selected');
            }
            delete selectedPicks[key];
            renderBetslip();
        }

        function calculateReturns() {
            const stake = parseFloat(document.getElementById('stakeInput').value) || 0;
            const totalOdds = parseFloat(document.getElementById('totalOdds').innerText) || 1.00;
            document.getElementById('potentialWin').innerText = (stake * totalOdds).toFixed(2);
        }

        function submitBetslip(e) {
            const keys = Object.keys(selectedPicks);
            if (keys.length === 0) { e.preventDefault(); alert('Your bet slip is empty!'); return; }
            const stake = parseFloat(document.getElementById('stakeInput').value);
            if (!stake || stake <= 0) { e.preventDefault(); alert('Please enter a valid stake amount!'); return; }
            if (stake < minStakeAllowed) {
                e.preventDefault();
                alert('Minimum stake amount allowed is ' + minStakeAllowed + '!');
                return;
            }
            document.getElementById('slipDataInput').value = JSON.stringify(keys.map(k => selectedPicks[k]));
            document.getElementById('stakeFormInput').value = stake;
        }

        function toggleMoreOptions(matchId) {
            const el = document.getElementById(`extraOptions_${matchId}`);
            el.style.display = (el.style.display === 'none' || el.style.display === '') ? 'block' : 'none';
        }

        function toggleMarketSection(sectionId) {
            const el = document.getElementById(sectionId);
            el.style.display = (el.style.display === 'none' || el.style.display === '') ? 'block' : 'none';
        }

        function loadBookingCode() {
            const code = document.getElementById('loadCodeInput').value.trim();
            if (!code) return;
            window.location.href = `/share/${code}`;
        }

        function openAdminMessageModal(depId, currentMsg) {
            const form = document.getElementById('modalEditMessageForm');
            const textarea = document.getElementById('modalEditMessageTextarea');
            if (form && textarea) {
                form.action = '/admin/process_deposit/' + depId;
                textarea.value = currentMsg;
                var myModal = new bootstrap.Modal(document.getElementById('adminMessageEditModal'));
                myModal.show();
            }
        }

        function selectPaymentMethodOption(value) {
            const radio = document.getElementById('pm_radio_' + value);
            if (radio) radio.checked = true;

            const cards = document.querySelectorAll('.payment-option-card');
            cards.forEach(card => card.classList.remove('selected'));

            const selectedCard = document.getElementById('card_pm_' + value);
            if (selectedCard) selectedCard.classList.add('selected');

            const cryptoContainer = document.getElementById('cryptoWalletsContainer');
            if (cryptoContainer) {
                if (value === 'crypto') {
                    cryptoContainer.style.display = 'block';
                } else {
                    cryptoContainer.style.display = 'none';
                }
            }
        }

        function copyCryptoAddress(address, btnEl) {
            navigator.clipboard.writeText(address).then(() => {
                const originalText = btnEl.innerHTML;
                btnEl.innerHTML = '<i class="fa-solid fa-check me-1"></i> Copied!';
                btnEl.classList.remove('btn-outline-success');
                btnEl.classList.add('btn-success');
                setTimeout(() => {
                    btnEl.innerHTML = originalText;
                    btnEl.classList.remove('btn-success');
                    btnEl.classList.add('btn-outline-success');
                }, 2000);
            }).catch(err => {
                alert('Failed to copy address.');
            });
        }
    </script>
</body>
</html>
"""

HOME_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
<div class="sport-tabs shadow-sm mb-3 rounded">
    <div class="container d-flex">
        <a href="/?tab=today" class="sport-tab-btn {% if current_tab == 'today' %}active{% endif %}"><i class="fa-solid fa-calendar-day me-1"></i> Today & Tomorrow's Matches</a>
        <a href="/?tab=live" class="sport-tab-btn {% if current_tab == 'live' %}active{% endif %}"><i class="fa-solid fa-circle text-danger me-1"></i> Live Matches</a>
        <a href="/?tab=basketball" class="sport-tab-btn {% if current_tab == 'basketball' %}active{% endif %}"><i class="fa-solid fa-basketball me-1"></i> Basketball</a>
        <a href="/?tab=tennis" class="sport-tab-btn {% if current_tab == 'tennis' %}active{% endif %}"><i class="fa-solid fa-baseball-bat-ball me-1"></i> Tennis</a>
    </div>
</div>

<div class="container mt-2">
    <div class="d-flex justify-content-between align-items-center mb-2">
        <h5 class="m-0 text-danger fw-bold" style="font-size: 1rem;">
            {% if current_tab == 'today' %}<i class="fa-solid fa-futbol me-2"></i>Today & Tomorrow's Matches (Live API Feed)
            {% elif current_tab == 'live' %}<i class="fa-solid fa-circle text-danger me-2"></i>Live Ongoing Matches
            {% elif current_tab == 'basketball' %}<i class="fa-solid fa-basketball me-2"></i>Basketball Matches
            {% elif current_tab == 'tennis' %}<i class="fa-solid fa-baseball-bat-ball me-2"></i>Tennis Matches
            {% endif %}
        </h5>
    </div>

    <div id="matchContainer">
        {% if matches %}
            {% for match in matches %}
            <div class="match-row shadow-sm">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-secondary fw-bold" style="font-size: 0.72rem;"><i class="fa-solid fa-trophy me-1 text-warning"></i> {{ match.league }}</small>
                    <div>
                        {% if match.status == 'Live' %}
                            <span class="badge bg-danger" style="font-size: 0.65rem;"><i class="fa-solid fa-circle me-1"></i> LIVE {{ match.match_minute }}</span>
                        {% elif match.status == 'Finished' %}
                            <span class="badge bg-secondary" style="font-size: 0.65rem;"><i class="fa-solid fa-flag-checkered me-1"></i> Finished</span>
                        {% else %}
                            <span class="badge bg-dark border border-secondary text-light" style="font-size: 0.65rem;"><i class="fa-regular fa-calendar me-1"></i> {{ match.pretty_date }}</span>
                        {% endif %}
                    </div>
                </div>

                <div class="row align-items-center g-1">
                    <div class="col-md-5">
                        <div class="d-flex justify-content-between align-items-center fw-bold text-light" style="font-size: 0.85rem;">
                            <span>{{ match.team_home }}</span>
                            {% if match.status == 'Live' %}
                                <span class="badge bg-dark text-warning px-2 py-1" style="font-size: 0.78rem;">{{ match.score_home }} - {{ match.score_away }}</span>
                            {% elif match.status == 'Finished' %}
                                <span class="badge bg-secondary text-white px-2 py-1" style="font-size: 0.78rem;">FT: {{ match.score_home }} - {{ match.score_away }}</span>
                            {% else %}
                                <span class="text-muted small" style="font-size: 0.75rem;">vs</span>
                            {% endif %}
                            <span>{{ match.team_away }}</span>
                        </div>
                    </div>

                    <div class="col-md-7">
                        {% if match.status == 'Finished' %}
                        <div class="text-center py-1 rounded border border-secondary text-muted small fw-bold" style="background-color: #0b132b;">Match has finished</div>
                        {% else %}
                        <div class="row g-1">
                            <div class="col-4">
                                <button type="button" class="odds-btn" id="btn_{{ match.id }}_Home" onclick="togglePick({{ match.id }}, 'Home', {{ match.odds_home }}, '{{ match.team_home }} vs {{ match.team_away }}')">
                                    1 <small class="text-light fw-bold">({{ match.odds_home }})</small>
                                </button>
                            </div>
                            <div class="col-4">
                                <button type="button" class="odds-btn" id="btn_{{ match.id }}_Draw" onclick="togglePick({{ match.id }}, 'Draw', {{ match.odds_draw }}, '{{ match.team_home }} vs {{ match.team_away }}')">
                                    X <small class="text-light fw-bold">({{ match.odds_draw }})</small>
                                </button>
                            </div>
                            <div class="col-4">
                                <button type="button" class="odds-btn" id="btn_{{ match.id }}_Away" onclick="togglePick({{ match.id }}, 'Away', {{ match.odds_away }}, '{{ match.team_home }} vs {{ match.team_away }}')">
                                    2 <small class="text-light fw-bold">({{ match.odds_away }})</small>
                                </button>
                            </div>
                        </div>
                        {% endif %}
                    </div>
                </div>

                {% if match.status != 'Finished' %}
                <div class="d-flex justify-content-between align-items-center mt-2 pt-1 border-top border-secondary">
                    <span class="more-options-toggle" onclick="toggleMoreOptions({{ match.id }})">
                        <i class="fa-solid fa-circle-plus me-1"></i> More Options (Over/Under, BTTS, Correct Score)
                    </span>
                    <small class="text-muted" style="font-size: 0.68rem;">ID: {{ match.id }}</small>
                </div>

                <div id="extraOptions_{{ match.id }}" style="display: none;" class="mt-2 p-2 rounded border border-secondary" style="background-color: #0b132b;">
                    <div class="market-sub-header" onclick="toggleMarketSection('ou_section_{{ match.id }}')">
                        <span><i class="fa-solid fa-chart-line me-1 text-primary"></i> Over / Under Goal Lines</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </div>
                    <div id="ou_section_{{ match.id }}" style="display: block;" class="mb-2 p-2 rounded border border-secondary" style="background-color: #1e293b;">
                        <div class="d-flex flex-column gap-1">
                            {% set ou_dict = match.over_under_dict %}
                            {% for line, data in ou_dict.items() %}
                            <div class="d-flex justify-content-between align-items-center p-1 rounded border border-secondary" style="background-color: #0b132b;">
                                <span class="fw-bold text-light" style="font-size: 0.78rem;">{{ line }} Goals</span>
                                <div class="d-flex gap-1" style="width: 70%;">
                                    <button type="button" class="odds-btn py-1" style="font-size: 0.75rem;" id="btn_{{ match.id }}_Over_{{ line }}" onclick="togglePick({{ match.id }}, 'Over_{{ line }}', {{ data.over }}, '{{ match.team_home }} vs {{ match.team_away }} (Over {{ line }})')">
                                        Over {{ line }} <span class="text-light">({{ data.over }})</span>
                                    </button>
                                    <button type="button" class="odds-btn py-1" style="font-size: 0.75rem;" id="btn_{{ match.id }}_Under_{{ line }}" onclick="togglePick({{ match.id }}, 'Under_{{ line }}', {{ data.under }}, '{{ match.team_home }} vs {{ match.team_away }} (Under {{ line }})')">
                                        Under {{ line }} <span class="text-light">({{ data.under }})</span>
                                    </button>
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>

                    <div class="market-sub-header" onclick="toggleMarketSection('btts_section_{{ match.id }}')">
                        <span><i class="fa-solid fa-futbol me-1 text-primary"></i> Both Teams to Score (BTTS)</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </div>
                    <div id="btts_section_{{ match.id }}" style="display: block;" class="mb-2 p-2 rounded border border-secondary" style="background-color: #1e293b;">
                        <div class="d-flex gap-2">
                            <button type="button" class="odds-btn py-1" style="font-size: 0.75rem;" id="btn_{{ match.id }}_BTTS_Yes" onclick="togglePick({{ match.id }}, 'BTTS Yes', {{ match.odds_btts_yes }}, '{{ match.team_home }} vs {{ match.team_away }} (BTTS Yes)')">
                                Yes <span class="text-light">({{ match.odds_btts_yes }})</span>
                            </button>
                            <button type="button" class="odds-btn py-1" style="font-size: 0.75rem;" id="btn_{{ match.id }}_BTTS_No" onclick="togglePick({{ match.id }}, 'BTTS No', {{ match.odds_btts_no }}, '{{ match.team_home }} vs {{ match.team_away }} (BTTS No)')">
                                No <span class="text-light">({{ match.odds_btts_no }})</span>
                            </button>
                        </div>
                    </div>

                    <div class="market-sub-header" onclick="toggleMarketSection('cs_section_{{ match.id }}')">
                        <span><i class="fa-solid fa-award me-1 text-primary"></i> Correct Score Market</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </div>
                    <div id="cs_section_{{ match.id }}" style="display: block;" class="p-2 rounded border border-secondary" style="background-color: #1e293b;">
                        <div class="row g-1">
                            {% set cs_dict = match.correct_scores_dict %}
                            {% for score, odd in cs_dict.items() %}
                            <div class="col-4 col-md-2">
                                <button type="button" class="odds-btn py-1" style="font-size: 0.72rem;" id="btn_{{ match.id }}_CS_{{ score }}" onclick="togglePick({{ match.id }}, 'CS_{{ score }}', {{ odd }}, '{{ match.team_home }} vs {{ match.team_away }} (CS {{ score }})')">
                                    {{ score }} <span class="text-light">({{ odd }})</span>
                                </button>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
                {% endif %}
            </div>
            {% endfor %}
        {% else %}
            <div class="card p-3 text-center text-muted">
                <i class="fa-solid fa-triangle-exclamation fs-4 mb-2 text-warning"></i>
                <p class="mb-0 fw-bold small">No real matches currently returned from the API. Check back shortly!</p>
            </div>
        {% endif %}
    </div>
</div>

{% if auto_load_slip %}
<script>
    document.addEventListener('DOMContentLoaded', () => {
        try {
            const parsedData = {{ auto_load_slip|safe }};
            if (Array.isArray(parsedData)) {
                parsedData.forEach(item => {
                    const key = `match_${item.matchId}_${item.pick}`;
                    selectedPicks[key] = item;
                    const btnId = `btn_${item.matchId}_${item.pick.replace(/\s+/g, '_').replace(/\./g, '_').replace(/-/g, '_')}`;
                    const btn = document.getElementById(btnId);
                    if (btn) btn.classList.add('selected');
                });
                renderBetslip();
                new bootstrap.Offcanvas(document.getElementById('betslipDrawer')).show();
            }
        } catch(e){}
    });
</script>
{% endif %}
""")

LOGIN_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
<div class="row justify-content-center">
    <div class="col-md-5">
        <div class="card p-3 shadow-sm border">
            <h4 class="text-center text-danger mb-3 fw-bold">Login to Winnerpari</h4>
            <form method="POST">
                <div class="mb-2"><label class="form-label fw-bold small">Email Address</label><input type="email" name="email" class="form-control" required></div>
                <div class="mb-3"><label class="form-label fw-bold small">Password</label><input type="password" name="password" class="form-control" required></div>
                <button type="submit" class="btn btn-success w-100 shadow-sm py-2 fw-bold">Login</button>
            </form>
            <p class="text-center mt-3 mb-0"><small>Don't have an account? <a href="/register" class="text-danger fw-bold">Sign Up here</a></small></p>
        </div>
    </div>
</div>
""")

REGISTER_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card p-3 shadow-sm border">
            <div class="alert alert-success text-center mb-3 py-2">
                <h6 class="fw-bold mb-1"><i class="fa-solid fa-gift me-1"></i>100% First Deposit Match Bonus</h6>
                <p class="small mb-0" style="font-size: 0.78rem;">Register now and get a 100% match bonus on your first deposit!</p>
            </div>
            <h4 class="text-center text-danger mb-3 fw-bold">Create Winnerpari Account</h4>
            <form method="POST">
                <input type="hidden" name="ref" value="{{ request.args.get('ref', '') }}">
                <div class="mb-2"><label class="form-label fw-bold small">Username</label><input type="text" name="username" class="form-control" required></div>
                <div class="mb-2"><label class="form-label fw-bold small">Email Address</label><input type="email" name="email" class="form-control" required></div>
                <div class="mb-2"><label class="form-label fw-bold small">Password</label><input type="password" name="password" class="form-control" required></div>
                <div class="mb-3">
                    <label class="form-label fw-bold small">Preferred Currency</label>
                    <select name="currency" class="form-select" required>
                        <option value="NGN" {% if detected_currency == 'NGN' %}selected{% endif %}>NGN (₦) - Nigerian Naira</option>
                        <option value="UZS" {% if detected_currency == 'UZS' %}selected{% endif %}>UZS (soʻm) - Uzbekistan Som</option>
                        <option value="TRY" {% if detected_currency == 'TRY' %}selected{% endif %}>TRY (₺) - Turkish Lira</option>
                        <option value="INR" {% if detected_currency == 'INR' %}selected{% endif %}>INR (₹) - Indian Rupee</option>
                        <option value="USD" {% if detected_currency == 'USD' %}selected{% endif %}>USD ($) - US Dollar</option>
                        <option value="EUR" {% if detected_currency == 'EUR' %}selected{% endif %}>EUR (€) - Euro</option>
                        <option value="GBP" {% if detected_currency == 'GBP' %}selected{% endif %}>GBP (£) - British Pound</option>
                        <option value="CAD" {% if detected_currency == 'CAD' %}selected{% endif %}>CAD ($) - Canadian Dollar</option>
                        <option value="AUD" {% if detected_currency == 'AUD' %}selected{% endif %}>AUD ($) - Australian Dollar</option>
                        <option value="JPY" {% if detected_currency == 'JPY' %}selected{% endif %}>JPY (¥) - Japanese Yen</option>
                        <option value="KES" {% if detected_currency == 'KES' %}selected{% endif %}>KES (KSh) - Kenyan Shilling</option>
                        <option value="GHS" {% if detected_currency == 'GHS' %}selected{% endif %}>GHS (₵) - Ghanaian Cedi</option>
                        <option value="ZAR" {% if detected_currency == 'ZAR' %}selected{% endif %}>ZAR (R) - South African Rand</option>
                    </select>
                </div>
                <button type="submit" class="btn btn-success w-100 shadow-sm py-2 fw-bold">Sign Up & Claim First Deposit Bonus</button>
            </form>
            <p class="text-center mt-3 mb-0"><small>Already have an account? <a href="/login" class="text-danger fw-bold">Login here</a></small></p>
        </div>
    </div>
</div>
""")

DASHBOARD_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
<div class="row">
    <div class="col-md-12 mb-3">
        <div class="card p-3 shadow-sm border">
            <div class="d-flex flex-column flex-md-row justify-content-between align-items-center gap-3">
                <div>
                    <h4 class="mb-1 text-light fs-5">Welcome back, <span class="text-danger fw-bold">{{ user.username }}</span>!</h4>
                    <p class="text-muted mb-0 fw-semibold small">Account ID: #{{ user.id }} | Currency: <span class="text-light fw-bold">{{ user.currency }}</span></p>
                </div>
                <div class="d-flex align-items-center gap-2">
                    <div class="px-3 py-1 rounded text-center border border-secondary" style="background-color: #0b132b;">
                        <small class="text-muted d-block text-uppercase fw-bold" style="font-size: 0.65rem;">Balance</small>
                        <span class="fs-5 fw-bold text-success">{{ user.currency }} {{ "%.2f"|format(user.balance) }}</span>
                    </div>
                    <div class="d-flex gap-1">
                        <button class="btn btn-success px-3 shadow-sm fw-bold btn-sm" data-bs-toggle="modal" data-bs-target="#depositModal"><i class="fa-solid fa-wallet me-1"></i> Deposit</button>
                        <button class="btn btn-outline-light px-3 shadow-sm fw-bold btn-sm" data-bs-toggle="modal" data-bs-target="#withdrawModal"><i class="fa-solid fa-money-bill-transfer me-1"></i> Withdraw</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    {% if withdrawal_error %}
    <div class="col-md-12 mb-3">
        <div class="alert alert-danger shadow-sm fw-bold small">{{ withdrawal_error }}</div>
    </div>
    {% endif %}

    <div class="col-md-12 mb-3">
        <div class="card p-3 shadow-sm border">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="text-danger m-0 fw-bold"><i class="fa-solid fa-clock-rotate-left me-2"></i>Deposit Requests & First Deposit Bonus Status</h6>
                <button class="btn btn-success btn-sm fw-bold shadow-sm py-1" data-bs-toggle="modal" data-bs-target="#depositModal"><i class="fa-solid fa-plus me-1"></i> Request Deposit</button>
            </div>
            <div class="table-responsive">
                <table class="table table-sm align-middle mb-0">
                    <thead><tr style="background-color: #0b132b;"><th>Amount</th><th>Method</th><th>Status</th><th>Payment Link / Instructions</th><th>Action</th></tr></thead>
                    <tbody>
                        {% for dep in deposits %}
                        <tr>
                            <td class="fw-bold">{{ user.currency }} {{ "%.2f"|format(dep.amount) }}</td>
                            <td>{{ dep.payment_method }}</td>
                            <td><span class="badge bg-{{ 'success' if dep.status == 'Approved' else ('danger' if dep.status == 'Declined' or dep.status == 'Cancelled' else ('info text-dark' if dep.user_acknowledged else 'warning text-dark')) }}">{{ 'Waiting for Approval' if dep.user_acknowledged else dep.status }}</span></td>
                            <td><small class="text-primary fw-semibold">{{ dep.support_message }}</small></td>
                            <td>
                                {% if dep.status == 'Cancelled' or dep.status == 'Declined' %}
                                <button class="btn btn-outline-success btn-xs fw-bold px-2 py-1" data-bs-toggle="modal" data-bs-target="#depositModal">Request Another</button>
                                {% elif not dep.user_acknowledged and dep.status == 'Pending' %}
                                    {% if 'Crypto' in dep.payment_method %}
                                    <span class="badge bg-info text-dark mb-1">Crypto Transfer</span>
                                    {% elif 'Support' in dep.payment_method %}
                                    <a href="https://wa.me/{{ support_whatsapp }}?text={{ urllib_quote('Hello Support Team, I need assistance with my deposit request of ' + user.currency + ' ' + '%.2f'|format(dep.amount) + ' via Other Payment Method.') }}" target="_blank" class="btn btn-success btn-xs fw-bold px-2 py-1 mb-1 shadow-sm"><i class="fab fa-whatsapp me-1"></i> WhatsApp Support</a>
                                    {% else %}
                                    <a href="{{ flutterwave_deposit_link }}" target="_blank" class="btn btn-success btn-xs fw-bold px-2 py-1 mb-1 shadow-sm"><i class="fa-solid fa-credit-card me-1"></i> Pay Now</a>
                                    {% endif %}
                                <form action="/acknowledge_deposit/{{ dep.id }}" method="POST" class="d-inline"><button type="submit" class="btn btn-outline-success btn-xs fw-bold px-2 py-1">Done</button></form>
                                {% else %}<span class="text-muted small">Acknowledged</span>{% endif %}
                            </td>
                        </tr>
                        {% else %}
                        <tr><td colspan="5" class="text-center text-muted py-2 small">No deposit requests submitted yet.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <div class="col-md-12 mb-3">
        <div class="card p-3 shadow-sm border">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h6 class="text-primary m-0 fw-bold"><i class="fa-solid fa-money-bill-transfer me-2"></i>Withdrawal History & Status</h6>
                <button class="btn btn-primary btn-sm fw-bold shadow-sm py-1" data-bs-toggle="modal" data-bs-target="#withdrawModal"><i class="fa-solid fa-plus me-1"></i> Request Withdrawal</button>
            </div>
            <div class="table-responsive">
                <table class="table table-sm align-middle mb-0">
                    <thead><tr style="background-color: #0b132b;"><th>Amount</th><th>Method & Details</th><th>Status</th><th>Date</th><th>Action / Receipt</th></tr></thead>
                    <tbody>
                        {% for w in withdrawals %}
                        <tr>
                            <td class="fw-bold">{{ user.currency }} {{ "%.2f"|format(w.amount) }}</td>
                            <td>{{ w.payout_method }}<br><small class="text-muted">{{ w.account_details }}</small></td>
                            <td>
                                {% if w.status == 'Successful' %}
                                    <span class="badge bg-success">Successful</span>
                                {% elif w.status == 'Declined' %}
                                    <span class="badge bg-danger">Declined</span>
                                {% else %}
                                    <span class="badge bg-warning text-dark">Pending Review</span>
                                {% endif %}
                            </td>
                            <td><small class="text-muted">{{ w.created_at.strftime('%Y-%m-%d %H:%M') }}</small></td>
                            <td>
                                {% if w.status == 'Successful' %}
                                <button type="button" class="btn btn-outline-success btn-xs fw-bold px-2 py-1" data-bs-toggle="modal" data-bs-target="#withdrawalReceiptModal{{ w.id }}">
                                    <i class="fa-solid fa-receipt me-1"></i> View Receipt
                                </button>
                                {% else %}
                                <span class="text-muted small">Under Review</span>
                                {% endif %}
                            </td>
                        </tr>

                        {% if w.status == 'Successful' %}
                        <!-- WITHDRAWAL RECEIPT MODAL -->
                        <div class="modal fade" id="withdrawalReceiptModal{{ w.id }}" tabindex="-1" aria-hidden="true">
                            <div class="modal-dialog modal-dialog-centered" style="max-width: 400px;">
                                <div class="modal-content border-0 shadow-lg" style="border-radius: 16px; overflow: hidden; background-color: #1e293b;">
                                    <div class="bg-success text-white p-3 text-center position-relative">
                                        <button type="button" class="btn-close btn-close-white position-absolute top-0 end-0 m-3" data-bs-dismiss="modal" aria-label="Close"></button>
                                        <div class="mb-1"><i class="fa-solid fa-circle-check fs-2"></i></div>
                                        <h5 class="fw-bold m-0">Withdrawal Successful</h5>
                                        <small class="text-white-50">Winnerpari Secure Payout</small>
                                    </div>
                                    <div class="modal-body p-4 text-light">
                                        <div class="text-center mb-3">
                                            <small class="text-muted d-block uppercase fw-bold" style="font-size: 0.7rem;">Amount Withdrawn</small>
                                            <h3 class="text-success fw-bold mb-0">{{ user.currency }} {{ "%.2f"|format(w.amount) }}</h3>
                                        </div>
                                        <div class="p-3 rounded border border-secondary shadow-sm d-flex flex-column gap-2 mb-3" style="font-size: 0.85rem; background-color: #0b132b;">
                                            <div class="d-flex justify-content-between">
                                                <span class="text-muted">Transaction ID:</span>
                                                <strong class="text-light font-monospace">WD-{{ w.id }}-2026</strong>
                                            </div>
                                            <div class="d-flex justify-content-between">
                                                <span class="text-muted">Date & Time:</span>
                                                <strong class="text-light">{{ w.created_at.strftime('%Y-%m-%d %H:%M:%S') }}</strong>
                                            </div>
                                            <div class="d-flex justify-content-between">
                                                <span class="text-muted">Payout Method:</span>
                                                <strong class="text-light">{{ w.payout_method }}</strong>
                                            </div>
                                            <div class="d-flex justify-content-between">
                                                <span class="text-muted">Crypto / Wallet Details:</span>
                                                <strong class="text-primary text-break" style="max-width: 180px; text-align: right;">{{ w.account_details }}</strong>
                                            </div>
                                            <div class="d-flex justify-content-between border-top border-secondary pt-2">
                                                <span class="text-muted">Status:</span>
                                                <span class="badge bg-success">Successful</span>
                                            </div>
                                        </div>
                                        <button type="button" class="btn btn-success w-100 fw-bold py-2 shadow-sm" data-bs-dismiss="modal">Close Receipt</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                        {% endif %}
                        {% else %}
                        <tr><td colspan="5" class="text-center text-muted py-2 small">No withdrawal history yet.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<!-- REQUEST DEPOSIT MODAL WITH VISIBLE PAYMENT OPTIONS -->
<div class="modal fade" id="depositModal" tabindex="-1">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content card border shadow">
            <div class="modal-header py-2" style="background-color: #0b132b;"><h6 class="modal-title text-danger fw-bold m-0">Request Deposit</h6><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
            <form action="/deposit" method="POST">
                <div class="modal-body text-light">
                    <div class="alert alert-success py-2 small mb-3"><i class="fa-solid fa-gift me-1"></i> First deposits receive a <strong>100% Match Bonus</strong>! Subsequent deposits credit the exact amount. Min deposit: <strong>{{ user.currency }} {{ "%.2f"|format(min_deposit_val) }}</strong>.</div>
                    <div class="mb-3"><label class="form-label fw-bold small">Deposit Amount ({{ user.currency }})</label><input type="number" step="0.01" name="amount" min="{{ min_deposit_val }}" class="form-control" placeholder="Enter amount" required></div>

                    <label class="form-label fw-bold small mb-2">Select Payment Method:</label>

                    <div class="payment-option-card selected" id="card_pm_instant" onclick="selectPaymentMethodOption('instant')">
                        <div class="form-check d-flex align-items-center justify-content-between p-0 m-0">
                            <div>
                                <input class="form-check-input me-2" type="radio" name="payment_method" id="pm_radio_instant" value="Instant Online Payment (Cards & Bank)" checked>
                                <label class="form-check-label fw-bold text-light" for="pm_radio_instant">
                                    <i class="fa-solid fa-credit-card text-success me-1"></i> Instant Online Payment (Cards & Bank)
                                </label>
                            </div>
                        </div>
                        <p class="text-muted mb-0 mt-1" style="font-size: 0.76rem; padding-left: 24px;">
                            Pay securely in your local currency via dynamic accounts, debit cards, or online transfer.
                        </p>
                    </div>

                    <div class="payment-option-card" id="card_pm_crypto" onclick="selectPaymentMethodOption('crypto')">
                        <div class="form-check d-flex align-items-center justify-content-between p-0 m-0">
                            <div>
                                <input class="form-check-input me-2" type="radio" name="payment_method" id="pm_radio_crypto" value="Crypto / USDT">
                                <label class="form-check-label fw-bold text-light" for="pm_radio_crypto">
                                    <i class="fa-brands fa-bitcoin text-warning me-1"></i> Crypto / USDT
                                </label>
                            </div>
                        </div>
                        <p class="text-muted mb-0 mt-1" style="font-size: 0.76rem; padding-left: 24px;">
                            Select this option to view and copy our official deposit wallet addresses (USDT, BTC, ETH, SOL, TRX).
                        </p>
                    </div>

                    <div class="payment-option-card" id="card_pm_other" onclick="selectPaymentMethodOption('other')">
                        <div class="form-check d-flex align-items-center justify-content-between p-0 m-0">
                            <div>
                                <input class="form-check-input me-2" type="radio" name="payment_method" id="pm_radio_other" value="Other Payment Method (Contact Support)">
                                <label class="form-check-label fw-bold text-light" for="pm_radio_other">
                                    <i class="fab fa-whatsapp text-success me-1"></i> Other Payment Method (Contact Support)
                                </label>
                            </div>
                        </div>
                        <p class="text-muted mb-0 mt-1" style="font-size: 0.76rem; padding-left: 24px;">
                            Need custom payment instructions or local transfers? Chat directly with support on WhatsApp.
                        </p>
                    </div>

                    <div id="cryptoWalletsContainer" style="display: none;" class="mt-3 p-2 rounded border border-secondary" style="background-color: #0b132b;">
                        <small class="text-muted fw-bold d-block mb-2">Select a Crypto Wallet / Network to Copy Address:</small>
                        <div class="d-flex flex-column gap-2">
                            {% for wallet in crypto_wallets %}
                            <div class="p-2 rounded border border-secondary" style="background-color: #1e293b;">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="fw-bold text-light" style="font-size: 0.78rem;"><i class="fa-solid fa-wallet text-success me-1"></i> {{ wallet.name }}</span>
                                    <button type="button" class="btn btn-outline-success btn-xs fw-bold px-2 py-0" style="font-size: 0.7rem;" onclick="copyCryptoAddress('{{ wallet.address }}', this)">
                                        <i class="fa-solid fa-copy me-1"></i> Copy
                                    </button>
                                </div>
                                <small class="text-muted d-block text-break font-monospace" style="font-size: 0.72rem;">{{ wallet.address }}</small>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
                <div class="modal-footer py-2" style="background-color: #0b132b;"><button type="submit" class="btn btn-success w-100 shadow-sm fw-bold py-2">Proceed Deposit Request</button></div>
            </form>
        </div>
    </div>
</div>

<div class="modal fade" id="withdrawModal" tabindex="-1">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content card border shadow">
            <div class="modal-header py-2" style="background-color: #0b132b;"><h6 class="modal-title text-primary fw-bold m-0">Request Withdrawal</h6><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div>
            <form action="/withdraw" method="POST">
                <div class="modal-body text-light">
                    <div class="alert alert-info py-2 small mb-3">Withdrawals require at least one approved deposit and are submitted to management for review and approval.</div>
                    <div class="mb-2"><label class="form-label fw-bold small">Withdrawal Amount</label><input type="number" step="0.01" name="amount" class="form-control" placeholder="Enter amount" required></div>
                    <div class="mb-2">
                        <label class="form-label fw-bold small">Payout Method</label>
                        <select name="payout_method" class="form-select" required>
                            <option value="Crypto / USDT (Wallet Address)">Crypto / USDT (Wallet Address)</option>
                            <option value="Bank Transfer">Bank Transfer</option>
                            <option value="e-Wallet">e-Wallet</option>
                        </select>
                    </div>
                    <div class="mb-2"><label class="form-label fw-bold small">Enter Your Crypto Wallet / Bank Details</label><textarea name="account_details" class="form-control" rows="3" placeholder="Paste your USDT wallet address or bank account details here..." required></textarea></div>
                </div>
                <div class="modal-footer py-2" style="background-color: #0b132b;"><button type="submit" class="btn btn-primary w-100 shadow-sm fw-bold py-2">Submit Withdrawal Request</button></div>
            </form>
        </div>
    </div>
</div>
""")

SETTINGS_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
<div class="row justify-content-center">
    <div class="col-md-8">
        <h4 class="text-danger mb-3 fw-bold fs-5"><i class="fa-solid fa-gear me-2"></i>Account Settings</h4>

        <div class="card p-3 shadow-sm border mb-3">
            <h6 class="text-light fw-bold mb-2"><i class="fa-solid fa-user me-2 text-danger"></i>Change Username</h6>
            <form method="POST">
                <input type="hidden" name="action" value="update_username">
                <div class="mb-2">
                    <label class="form-label small fw-bold">New Username</label>
                    <input type="text" name="username" class="form-control" value="{{ user.username }}" required>
                </div>
                <button type="submit" class="btn btn-success btn-sm fw-bold shadow-sm">Update Username</button>
            </form>
        </div>

        <div class="card p-3 shadow-sm border mb-3">
            <h6 class="text-light fw-bold mb-2"><i class="fa-solid fa-lock me-2 text-danger"></i>Change Password</h6>
            <form method="POST">
                <input type="hidden" name="action" value="update_password">
                <div class="mb-2">
                    <label class="form-label small fw-bold">Current Password</label>
                    <input type="password" name="current_password" class="form-control" required>
                </div>
                <div class="mb-2">
                    <label class="form-label small fw-bold">New Password</label>
                    <input type="password" name="new_password" class="form-control" required>
                </div>
                <button type="submit" class="btn btn-success btn-sm fw-bold shadow-sm">Update Password</button>
            </form>
        </div>

        <div class="card p-3 shadow-sm border mb-3">
            <h6 class="text-light fw-bold mb-2"><i class="fa-solid fa-wallet me-2 text-danger"></i>Preferred Currency</h6>
            <form method="POST">
                <input type="hidden" name="action" value="update_currency">
                <div class="mb-2">
                    <label class="form-label small fw-bold">Select Currency (Automatic Balance Conversion)</label>
                    <select name="currency" class="form-select" required>
                        <option value="NGN" {% if user.currency == 'NGN' %}selected{% endif %}>NGN (₦) - Nigerian Naira</option>
                        <option value="UZS" {% if user.currency == 'UZS' %}selected{% endif %}>UZS (soʻm) - Uzbekistan Som</option>
                        <option value="TRY" {% if user.currency == 'TRY' %}selected{% endif %}>TRY (₺) - Turkish Lira</option>
                        <option value="INR" {% if user.currency == 'INR' %}selected{% endif %}>INR (₹) - Indian Rupee</option>
                        <option value="USD" {% if user.currency == 'USD' %}selected{% endif %}>USD ($) - US Dollar</option>
                        <option value="EUR" {% if user.currency == 'EUR' %}selected{% endif %}>EUR (€) - Euro</option>
                        <option value="GBP" {% if user.currency == 'GBP' %}selected{% endif %}>GBP (£) - British Pound</option>
                        <option value="CAD" {% if user.currency == 'CAD' %}selected{% endif %}>CAD ($) - Canadian Dollar</option>
                        <option value="AUD" {% if user.currency == 'AUD' %}selected{% endif %}>AUD ($) - Australian Dollar</option>
                        <option value="JPY" {% if user.currency == 'JPY' %}selected{% endif %}>JPY (¥) - Japanese Yen</option>
                        <option value="KES" {% if user.currency == 'KES' %}selected{% endif %}>KES (KSh) - Kenyan Shilling</option>
                        <option value="GHS" {% if user.currency == 'GHS' %}selected{% endif %}>GHS (₵) - Ghanaian Cedi</option>
                        <option value="ZAR" {% if user.currency == 'ZAR' %}selected{% endif %}>ZAR (R) - South African Rand</option>
                    </select>
                </div>
                <button type="submit" class="btn btn-success btn-sm fw-bold shadow-sm">Save Currency</button>
            </form>
        </div>
    </div>
</div>
""")

BET_HISTORY_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
<h4 class="text-danger mb-3 fw-bold fs-5"><i class="fa-solid fa-ticket me-2"></i>My Bet History</h4>
<ul class="nav nav-pills mb-3 gap-2">
    <li class="nav-item"><a class="nav-link fw-bold btn-sm {% if filter_status == 'Running' %}active bg-danger text-white{% else %}text-light border border-secondary{% endif %}" href="/bets_history?status=Running">Running</a></li>
    <li class="nav-item"><a class="nav-link fw-bold btn-sm {% if filter_status == 'Won' %}active bg-danger text-white{% else %}text-light border border-secondary{% endif %}" href="/bets_history?status=Won">Won</a></li>
    <li class="nav-item"><a class="nav-link fw-bold btn-sm {% if filter_status == 'Lost' %}active bg-danger text-white{% else %}text-light border border-secondary{% endif %}" href="/bets_history?status=Lost">Lost</a></li>
</ul>

<div class="d-flex flex-column gap-2">
    {% for ticket in tickets %}
    <div class="card p-3 shadow-sm border text-light" style="border-radius: 8px;">
        <div class="d-flex justify-content-between align-items-center mb-2 pb-2 border-bottom border-secondary">
            <div>
                <span class="badge bg-secondary me-1" style="font-size: 0.65rem;">{{ ticket.ticket_type }}</span>
                <span class="text-primary fw-bold" style="font-size: 0.8rem;"><i class="fa-solid fa-barcode me-1"></i> Code: {{ ticket.booking_code or ('WP-' ~ ticket.id) }}</span>
            </div>
            <div>
                <span class="badge bg-{{ 'success' if ticket.status == 'Won' else ('danger' if ticket.status == 'Lost' else 'warning text-dark') }}" style="font-size: 0.72rem;">{{ ticket.status }}</span>
            </div>
        </div>

        <div class="row align-items-center g-2 mb-2">
            <div class="col-7">
                <small class="text-muted d-block text-uppercase fw-bold" style="font-size: 0.62rem;">Match / Selection Preview</small>
                <span class="text-light fw-bold" style="font-size: 0.82rem;">
                    {% set first_item = ticket.parsed_items[0] if ticket.parsed_items else None %}
                    {% if first_item %}
                        {{ first_item.matchName }} <span class="text-success">({{ first_item.pick }})</span>
                        {% if ticket.parsed_items|length > 1 %}
                            <span class="badge bg-dark text-light border border-secondary ms-1" style="font-size: 0.6rem;">+{{ ticket.parsed_items|length - 1 }} more</span>
                        {% endif %}
                    {% else %}No selections{% endif %}
                </span>
            </div>
            <div class="col-5 text-end">
                <small class="text-muted d-block text-uppercase fw-bold" style="font-size: 0.62rem;">Stake / Potential Win</small>
                <div class="text-light fw-bold" style="font-size: 0.8rem;">{{ user.currency }} {{ "%.2f"|format(ticket.amount) }}</div>
                <div class="text-success fw-bold" style="font-size: 0.88rem;">{{ user.currency }} {{ "%.2f"|format(ticket.potential_win) }}</div>
            </div>
        </div>

        <div class="d-flex justify-content-between align-items-center pt-2 border-top border-secondary">
            <small class="text-muted" style="font-size: 0.68rem;"><i class="fa-regular fa-clock me-1"></i> {{ ticket.created_at.strftime('%b %d, %H:%M') }} | Odds: <strong>{{ "%.2f"|format(ticket.total_odds) }}</strong></small>
            <button type="button" class="btn btn-outline-success btn-sm py-0 px-2 fw-bold" style="font-size: 0.72rem;" data-bs-toggle="modal" data-bs-target="#ticketModal{{ ticket.id }}">
                <i class="fa-solid fa-eye me-1"></i> Details
            </button>
        </div>
    </div>

    <!-- TICKET DETAILS MODAL -->
    <div class="modal fade" id="ticketModal{{ ticket.id }}" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered" style="max-width: 420px;">
            <div class="modal-content border-0 shadow-lg" style="border-radius: 18px; overflow: hidden; background-color: #1e293b;">
                <div class="d-flex justify-content-between align-items-center px-3 py-3 border-bottom border-secondary" style="background-color: #0b132b;">
                    <h6 class="fw-bold m-0 text-light d-flex align-items-center gap-2" style="font-size: 1.05rem;">
                        <i class="fa-solid fa-receipt text-danger fs-5"></i> Ticket Details
                    </h6>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close" style="font-size: 0.85rem;"></button>
                </div>

                <div class="modal-body p-3">
                    <div class="p-3 mb-3 text-white shadow-sm" style="background-color: #0b132b; border-radius: 16px;">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="text-white-50 font-monospace small" style="font-size: 0.82rem;">
                                #{{ ticket.booking_code or ('WP-' ~ ticket.id) }} &bull; {{ ticket.created_at.strftime('%d %b, %H:%M') }}
                            </span>
                            <div>
                                {% if ticket.status == 'Won' %}
                                    <span class="badge px-2 py-1 text-white fw-bold" style="background-color: #00c853; font-size: 0.75rem; border-radius: 8px;"><i class="fa-solid fa-trophy me-1"></i> Won</span>
                                {% elif ticket.status == 'Lost' %}
                                    <span class="badge px-2 py-1 text-white fw-bold" style="background-color: #dc3545; font-size: 0.75rem; border-radius: 8px;"><i class="fa-solid fa-xmark me-1"></i> Lost</span>
                                {% else %}
                                    <span class="badge px-2 py-1 text-white fw-bold" style="background-color: #00c853; font-size: 0.75rem; border-radius: 8px;"><i class="fa-solid fa-trophy me-1"></i> Pending</span>
                                {% endif %}
                            </div>
                        </div>

                        <h4 class="fw-bold text-white mb-3" style="font-size: 1.35rem; letter-spacing: 0.3px;">{{ ticket.ticket_type }}</h4>

                        <div class="d-flex flex-column gap-2 border-top border-secondary border-opacity-25 pt-2">
                            <div class="d-flex justify-content-between align-items-center">
                                <span class="text-white-50 small fw-semibold">Total Return</span>
                                <span class="fw-bold" style="color: #00e676; font-size: 1.05rem;">{{ user.currency }} {{ "%.2f"|format(ticket.potential_win) }}</span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center">
                                <span class="text-white-50 small fw-semibold">Total Stake</span>
                                <span class="fw-bold text-white" style="font-size: 0.98rem;">{{ user.currency }} {{ "%.2f"|format(ticket.amount) }}</span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center">
                                <span class="text-white-50 small fw-semibold">Total Odds</span>
                                <span class="fw-bold text-white" style="font-size: 0.98rem;">{{ "%.2f"|format(ticket.total_odds) }}</span>
                            </div>
                        </div>
                    </div>

                    <div class="p-3 rounded-3 shadow-sm border border-secondary mb-3 d-flex justify-content-between align-items-center" style="background-color: #0b132b;">
                        <span class="fw-bold text-light small">Verify Code :</span>
                        <span class="fw-bold text-light font-monospace" style="font-size: 0.95rem; letter-spacing: 0.5px;">{{ ticket.booking_code or ('WP-' ~ ticket.id) }}</span>
                    </div>

                    <div class="d-flex align-items-center gap-2 mb-2 px-1">
                        <i class="fa-solid fa-futbol text-danger"></i>
                        <span class="fw-bold text-light" style="font-size: 0.92rem;">Selections</span>
                    </div>

                    <div class="d-flex flex-column gap-2">
                        {% for p_item in ticket.parsed_items %}
                        <div class="p-3 rounded-3 shadow-sm border border-secondary" style="background-color: #0b132b;">
                            <div class="d-flex justify-content-between align-items-start mb-1">
                                <div class="d-flex align-items-center gap-2">
                                    <div class="rounded-circle bg-secondary bg-opacity-25 d-flex align-items-center justify-content-center text-light" style="width: 24px; height: 24px; font-size: 0.75rem;">
                                        <i class="fa-solid fa-futbol"></i>
                                    </div>
                                    <span class="fw-bold text-light" style="font-size: 0.92rem;">{{ p_item.matchName }}</span>
                                </div>
                                {% if ticket.status == 'Won' or p_item.is_won %}
                                    <span class="badge text-white fw-bold px-2 py-1" style="background-color: #00c853; font-size: 0.68rem; border-radius: 6px;">Won</span>
                                {% elif ticket.status == 'Lost' %}
                                    <span class="badge text-white fw-bold px-2 py-1" style="background-color: #dc3545; font-size: 0.68rem; border-radius: 6px;">Lost</span>
                                {% else %}
                                    <span class="badge text-dark fw-bold px-2 py-1" style="background-color: #ffc107; font-size: 0.68rem; border-radius: 6px;">Running</span>
                                {% endif %}
                            </div>

                            <div class="text-muted fw-semibold ps-4 mb-2" style="font-size: 0.78rem;">
                                Score: {{ p_item.score_display }}
                            </div>

                            <div class="p-2 rounded border border-secondary d-flex justify-content-between align-items-center" style="background-color: #1e293b;">
                                <span class="fw-bold text-primary" style="font-size: 0.85rem;">Pick: {{ p_item.pick }} @ {{ "%.2f"|format(p_item.odds) }}</span>
                                <span class="text-muted small" style="font-size: 0.72rem;">Market: {{ p_item.market }}</span>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
    </div>
    {% else %}
    <div class="card p-3 text-center text-muted">
        <i class="fa-solid fa-ticket fs-4 mb-2 text-warning"></i>
        <p class="mb-0 fw-bold small">No tickets found in this category.</p>
    </div>
    {% endfor %}
</div>
""")

ADMIN_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
<h3 class="text-danger mb-3 fw-bold fs-4"><i class="fa-solid fa-user-shield me-2"></i>Winnerpari Management Console</h3>

<div class="row g-3 mb-3">
    <div class="col-md-4">
        <div class="card p-3 text-center shadow-sm border">
            <small class="text-muted text-uppercase fw-bold" style="font-size: 0.7rem;">Total Registered Players</small>
            <h3 class="text-success fw-bold m-0">{{ total_users }}</h3>
        </div>
    </div>
    <div class="col-md-8">
        <div class="card p-3 shadow-sm border">
            <h6 class="fw-bold mb-2 text-light" style="font-size: 0.88rem;"><i class="fa-solid fa-user-magnifying-glass me-1 text-danger"></i> Player ID Lookup & Account Control</h6>
            <form action="/admin/lookup_user" method="GET" class="input-group input-group-sm">
                <input type="number" name="user_id" class="form-control" placeholder="Enter User ID (e.g. 1, 2...)" required>
                <button type="submit" class="btn btn-danger px-3 fw-bold">Search Player</button>
            </form>
        </div>
    </div>
</div>

<div class="card p-3 mb-3 shadow-sm border">
    <h6 class="text-light mb-2 fw-bold"><i class="fa-solid fa-envelope me-2 text-danger"></i> Notification Email Settings</h6>
    <form action="/admin/update_email" method="POST" class="row g-2 align-items-center">
        <div class="col-md-8"><input type="email" name="notification_email" class="form-control" value="{{ notification_email }}" required></div>
        <div class="col-md-4"><button type="submit" class="btn btn-success w-100 fw-bold shadow-sm btn-sm py-2">Save Email</button></div>
    </form>
</div>

<div class="card p-3 mb-3 shadow-sm border">
    <h6 class="text-light mb-2 fw-bold"><i class="fa-solid fa-plus me-2 text-danger"></i> Create Custom Match</h6>
    <form action="/admin/create_match" method="POST" class="row g-2">
        <div class="col-6 col-md-2"><select name="sport" class="form-select form-select-sm" required><option value="Football">Football</option><option value="Basketball">Basketball</option><option value="Tennis">Tennis</option></select></div>
        <div class="col-6 col-md-2"><input type="text" name="league" class="form-control form-control-sm" placeholder="League" required></div>
        <div class="col-6 col-md-2"><input type="text" name="team_home" class="form-control form-control-sm" placeholder="Home Team" required></div>
        <div class="col-6 col-md-2"><input type="text" name="team_away" class="form-control form-control-sm" placeholder="Away Team" required></div>
        <div class="col-6 col-md-2"><input type="date" name="match_date" class="form-control form-control-sm" required value="2026-10-18"></div>
        <div class="col-6 col-md-2"><input type="time" name="match_time" class="form-control form-control-sm" required value="20:00"></div>
        <div class="col-4 col-md-2"><input type="number" step="0.01" name="odds_home" class="form-control form-control-sm" placeholder="1 Odds" required></div>
        <div class="col-4 col-md-2"><input type="number" step="0.01" name="odds_draw" class="form-control form-control-sm" placeholder="X Odds" required></div>
        <div class="col-4 col-md-2"><input type="number" step="0.01" name="odds_away" class="form-control form-control-sm" placeholder="2 Odds" required></div>
        <div class="col-12 col-md-3">
            <div class="input-group input-group-sm">
                <span class="input-group-text bg-dark text-light border-secondary fw-bold">Target</span>
                <input type="number" name="target_score_home" class="form-control text-center text-success" value="2" required>
                <input type="number" name="target_score_away" class="form-control text-center text-success" value="1" required>
            </div>
        </div>
        <div class="col-12 col-md-3"><button type="submit" class="btn btn-success w-100 shadow-sm fw-bold btn-sm py-1">Create Match</button></div>
    </form>
</div>

<div class="card p-3 mb-3 shadow-sm border">
    <h6 class="text-light mb-2 fw-bold"><i class="fa-solid fa-wallet me-2 text-danger"></i> Pending Deposits & Support Messaging</h6>
    <div class="table-responsive">
        <table class="table table-sm align-middle mb-0">
            <thead><tr style="background-color: #0b132b;"><th>User</th><th>Amount & Method</th><th>Status</th><th>Instructions</th><th>Actions</th></tr></thead>
            <tbody>
                {% for dep in deposits %}
                <tr>
                    <td class="fw-bold">#{{ dep.user.id }} - {{ dep.user.username }}</td>
                    <td class="fw-bold">{{ dep.user.currency }} {{ "%.2f"|format(dep.amount) }} <br><small class="text-muted">{{ dep.payment_method }}</small></td>
                    <td>
                        {% if dep.status == 'Cancelled' %}
                            <span class="badge bg-danger text-white fw-bold px-2 py-1" style="font-size: 0.72rem;">Payment Cancelled</span>
                        {% elif dep.user_acknowledged %}
                            <span class="badge bg-info text-dark fw-bold px-2 py-1" style="font-size: 0.72rem;">Waiting Approval (Done)</span>
                        {% else %}
                            <span class="badge bg-warning text-dark fw-bold px-2 py-1" style="font-size: 0.72rem;">Pending Review</span>
                        {% endif %}
                    </td>
                    <td>
                        <div class="p-1 border border-secondary rounded text-light fw-semibold mb-1" style="max-width: 200px; font-size: 0.75rem; background-color: #0b132b;">{{ dep.support_message }}</div>
                        <button type="button" class="btn btn-success btn-xs fw-bold px-2 py-0" style="font-size: 0.7rem;" onclick="openAdminMessageModal('{{ dep.id }}', {{ dep.support_message|tojson }})">Edit Msg</button>
                    </td>
                    <td>
                        <div class="d-flex gap-1 align-items-center">
                            <a href="https://wa.me/{{ support_whatsapp }}?text={{ dep.whatsapp_url_text }}" target="_blank" class="btn btn-success btn-xs fw-bold px-2 py-1"><i class="fab fa-whatsapp"></i></a>
                            <form action="/admin/approve_deposit/{{ dep.id }}" method="POST" class="d-inline"><button type="submit" class="btn btn-success btn-xs fw-bold px-2 py-1 shadow-sm">Approve</button></form>
                            <form action="/admin/decline_deposit/{{ dep.id }}" method="POST" class="d-inline"><button type="submit" class="btn btn-outline-danger btn-xs px-2 py-1 shadow-sm">Decline</button></form>
                        </div>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="5" class="text-center text-muted py-2 small">No pending deposits.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<div class="card p-3 mb-3 shadow-sm border">
    <h6 class="text-light mb-2 fw-bold"><i class="fa-solid fa-money-bill-transfer me-2 text-danger"></i> Pending Withdrawal Requests</h6>
    <div class="table-responsive">
        <table class="table table-sm align-middle mb-0">
            <thead><tr style="background-color: #0b132b;"><th>User</th><th>Amount</th><th>Method & Details</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
                {% for w in withdrawals %}
                <tr>
                    <td class="fw-bold">#{{ w.user.id }} - {{ w.user.username }}</td>
                    <td class="fw-bold text-danger">{{ w.user.currency }} {{ "%.2f"|format(w.amount) }}</td>
                    <td>{{ w.payout_method }}<br><small class="text-muted">{{ w.account_details }}</small></td>
                    <td><span class="badge bg-warning text-dark">Pending Review</span></td>
                    <td>
                        <div class="d-flex gap-1">
                            <form action="/admin/approve_withdrawal/{{ w.id }}" method="POST" class="d-inline"><button type="submit" class="btn btn-success btn-xs fw-bold px-2 py-1">Approve</button></form>
                            <form action="/admin/decline_withdrawal/{{ w.id }}" method="POST" class="d-inline"><button type="submit" class="btn btn-outline-danger btn-xs px-2 py-1">Decline</button></form>
                        </div>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="5" class="text-center text-muted py-2 small">No pending withdrawal requests.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<div class="card p-3 shadow-sm border">
    <h6 class="text-light mb-2 fw-bold"><i class="fa-solid fa-futbol me-2 text-danger"></i> Manage Matches, Target Scores & Exact Score Settlement</h6>
    <div class="table-responsive">
        <table class="table table-sm align-middle mb-0">
            <thead><tr style="background-color: #0b132b;"><th>Date & Time</th><th>Match</th><th>Status</th><th>Set Target Score</th><th>Final Settle</th><th>Action</th></tr></thead>
            <tbody>
                {% for match in matches %}
                <tr>
                    <td><small class="text-muted fw-bold" style="font-size: 0.72rem;">{{ match.pretty_date }}</small></td>
                    <td><strong>{{ match.team_home }} vs {{ match.team_away }}</strong></td>
                    <td><span class="badge bg-{{ 'danger' if match.status == 'Live' else ('secondary' if match.status == 'Finished' else 'dark border border-secondary') }}" style="font-size: 0.68rem;">{{ match.status }}</span></td>
                    <td>
                        <form action="/admin/update_target_score/{{ match.id }}" method="POST" class="d-flex align-items-center gap-1">
                            <div class="input-group input-group-sm" style="width: 110px;">
                                <input type="number" name="target_home" class="form-control text-center fw-bold text-success" value="{{ match.target_score_home }}" required min="0">
                                <span class="input-group-text bg-dark text-light border-secondary fw-bold">-</span>
                                <input type="number" name="target_away" class="form-control text-center fw-bold text-success" value="{{ match.target_score_away }}" required min="0">
                            </div>
                            <button type="submit" class="btn btn-success btn-xs fw-bold py-1 px-2">Set</button>
                        </form>
                    </td>
                    <td>
                        <form action="/admin/settle_match/{{ match.id }}" method="POST" class="d-flex align-items-center gap-1">
                            <div class="input-group input-group-sm" style="width: 100px;">
                                <input type="number" name="final_home" class="form-control text-center fw-bold text-light" value="{{ match.target_score_home }}" required placeholder="H">
                                <span class="input-group-text bg-dark text-light border-secondary fw-bold">-</span>
                                <input type="number" name="final_away" class="form-control text-center fw-bold text-light" value="{{ match.target_score_away }}" required placeholder="A">
                            </div>
                            <button type="submit" class="btn btn-outline-primary btn-xs fw-bold py-1">Settle</button>
                        </form>
                    </td>
                    <td>
                        <form action="/admin/delete_match/{{ match.id }}" method="POST" onsubmit="return confirm('Delete match?');" class="d-inline">
                            <button type="submit" class="btn btn-outline-danger btn-xs py-1"><i class="fa-solid fa-trash"></i></button>
                        </form>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="6" class="text-center text-muted py-2 small">No active matches found.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
""")

USER_PROFILE_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
<div class="d-flex justify-content-between align-items-center mb-3">
    <h4 class="text-danger fw-bold m-0 fs-5"><i class="fa-solid fa-user me-2"></i>Player Profile: #{{ target_user.id }}</h4>
    <a href="/admin" class="btn btn-outline-secondary btn-sm fw-bold">Back to Admin Console</a>
</div>

<div class="card p-3 mb-3 shadow-sm border">
    <div class="row g-3 align-items-center mb-3">
        <div class="col-md-3">
            <small class="text-muted d-block uppercase fw-bold" style="font-size: 0.7rem;">Username</small>
            <span class="fw-bold text-light fs-6">{{ target_user.username }}</span>
        </div>
        <div class="col-md-3">
            <small class="text-muted d-block uppercase fw-bold" style="font-size: 0.7rem;">Email Address</small>
            <span class="fw-bold text-light fs-6">{{ target_user.email }}</span>
        </div>
        <div class="col-md-2">
            <small class="text-muted d-block uppercase fw-bold" style="font-size: 0.7rem;">Current Balance</small>
            <span class="fw-bold text-success fs-6">{{ target_user.currency }} {{ "%.2f"|format(target_user.balance) }}</span>
        </div>
        <div class="col-md-4">
            <span class="text-muted d-block uppercase fw-bold" style="font-size: 0.7rem;">Status</span>
            {% if target_user.is_blocked %}
                <span class="badge bg-danger">Blocked</span>
            {% else %}
                <span class="badge bg-success">Active</span>
            {% endif %}
        </div>
    </div>

    <hr class="my-2 border-secondary">

    <!-- MANUAL BALANCE ADJUSTMENT -->
    <h6 class="fw-bold text-light mb-2"><i class="fa-solid fa-wallet me-1 text-danger"></i> Manual Balance Adjustment (Add / Deduct)</h6>
    <form action="/admin/adjust_balance/{{ target_user.id }}" method="POST" class="row g-2 align-items-center mb-3">
        <div class="col-md-4">
            <input type="number" step="0.01" name="amount" class="form-control form-control-sm" placeholder="Enter amount..." required>
        </div>
        <div class="col-md-4">
            <select name="action_type" class="form-select form-select-sm" required>
                <option value="add">Add Funds (Plus)</option>
                <option value="subtract">Deduct / Withdraw Funds (Minus)</option>
            </select>
        </div>
        <div class="col-md-4">
            <button type="submit" class="btn btn-success btn-sm w-100 fw-bold shadow-sm">Apply Balance Adjustment</button>
        </div>
    </form>

    <hr class="my-2 border-secondary">

    <h6 class="fw-bold text-light mb-2"><i class="fa-solid fa-ban me-1 text-danger"></i> Account Restriction & Custom Message Control</h6>
    {% if target_user.is_blocked %}
        <div class="alert alert-danger py-2 small mb-2">
            <strong>Current Block Message / Instructions:</strong> {{ target_user.block_reason }}
        </div>
        <form action="/admin/unblock_user/{{ target_user.id }}" method="POST">
            <button type="submit" class="btn btn-success btn-sm fw-bold shadow-sm">Unblock User Account</button>
        </form>
    {% else %}
        <form action="/admin/block_user/{{ target_user.id }}" method="POST">
            <div class="mb-2">
                <label class="form-label small fw-bold">Custom Block Message & Instructions for User Screen:</label>
                <textarea name="block_reason" class="form-control" rows="3" placeholder="Enter instructions here..." required></textarea>
            </div>
            <button type="submit" class="btn btn-danger btn-sm fw-bold shadow-sm">Block Account & Display Message</button>
        </form>
    {% endif %}
</div>

<!-- PLAYER DEPOSIT HISTORY -->
<div class="card p-3 mb-3 shadow-sm border">
    <h6 class="text-danger mb-2 fw-bold"><i class="fa-solid fa-clock-rotate-left me-2"></i>Player Deposit History</h6>
    <div class="table-responsive">
        <table class="table table-sm align-middle mb-0">
            <thead><tr style="background-color: #0b132b;"><th>Amount</th><th>Method</th><th>Status</th><th>Date</th></tr></thead>
            <tbody>
                {% for dep in target_user.deposits %}
                <tr>
                    <td class="fw-bold">{{ target_user.currency }} {{ "%.2f"|format(dep.amount) }}</td>
                    <td>{{ dep.payment_method }}</td>
                    <td><span class="badge bg-{{ 'success' if dep.status == 'Approved' else ('danger' if dep.status == 'Declined' else 'warning text-dark') }}">{{ dep.status }}</span></td>
                    <td><small class="text-muted">{{ dep.created_at.strftime('%Y-%m-%d %H:%M') }}</small></td>
                </tr>
                {% else %}
                <tr><td colspan="4" class="text-center text-muted py-2 small">No deposit records found for this player.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<!-- PLAYER WITHDRAWAL HISTORY -->
<div class="card p-3 mb-3 shadow-sm border">
    <h6 class="text-primary mb-2 fw-bold"><i class="fa-solid fa-money-bill-transfer me-2"></i>Player Withdrawal History</h6>
    <div class="table-responsive">
        <table class="table table-sm align-middle mb-0">
            <thead><tr style="background-color: #0b132b;"><th>Amount</th><th>Method & Details</th><th>Status</th><th>Date</th></tr></thead>
            <tbody>
                {% for w in target_user.withdrawals %}
                <tr>
                    <td class="fw-bold">{{ target_user.currency }} {{ "%.2f"|format(w.amount) }}</td>
                    <td>{{ w.payout_method }}<br><small class="text-muted">{{ w.account_details }}</small></td>
                    <td><span class="badge bg-{{ 'success' if w.status == 'Successful' else ('danger' if w.status == 'Declined' else 'warning text-dark') }}">{{ w.status }}</span></td>
                    <td><small class="text-muted">{{ w.created_at.strftime('%Y-%m-%d %H:%M') }}</small></td>
                </tr>
                {% else %}
                <tr><td colspan="4" class="text-center text-muted py-2 small">No withdrawal records found for this player.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<!-- PLAYER BET HISTORY -->
<div class="card p-3 shadow-sm border">
    <h6 class="text-light mb-2 fw-bold"><i class="fa-solid fa-ticket me-2 text-danger"></i>Player Bet History</h6>
    <div class="table-responsive">
        <table class="table table-sm align-middle mb-0">
            <thead><tr style="background-color: #0b132b;"><th>Code</th><th>Type</th><th>Stake</th><th>Potential Win</th><th>Odds</th><th>Status</th><th>Date</th></tr></thead>
            <tbody>
                {% for b in target_user.bets %}
                <tr>
                    <td class="fw-bold text-primary">{{ b.booking_code or ('WP-' ~ b.id) }}</td>
                    <td>{{ b.ticket_type }}</td>
                    <td>{{ target_user.currency }} {{ "%.2f"|format(b.amount) }}</td>
                    <td class="fw-bold text-success">{{ target_user.currency }} {{ "%.2f"|format(b.potential_win) }}</td>
                    <td>{{ "%.2f"|format(b.total_odds) }}</td>
                    <td><span class="badge bg-{{ 'success' if b.status == 'Won' else ('danger' if b.status == 'Lost' else 'warning text-dark') }}">{{ b.status }}</span></td>
                    <td><small class="text-muted">{{ b.created_at.strftime('%Y-%m-%d %H:%M') }}</small></td>
                </tr>
                {% else %}
                <tr><td colspan="7" class="text-center text-muted py-2 small">No betting records found for this player.</td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
""")

def attach_match_dictionaries(matches):
    for m in matches:
        try: m.correct_scores_dict = json.loads(m.correct_scores_json)
        except: m.correct_scores_dict = {}
        try: m.over_under_dict = json.loads(m.over_under_json)
        except: m.over_under_dict = {}
        m.pretty_date = format_match_pretty_date(m.match_date, m.match_time)
    return matches

@app.context_processor
def inject_global_vars():
    check_request_expirations()
    unacknowledged_deposit = None
    unacknowledged_withdrawal = None
    uncelebrated_win = None
    blocked_user_notice = None
    show_welcome_modal = False
    ref_count = 0

    curr = session.get('currency', 'USD')
    flutterwave_deposit_link = get_flutterwave_link_for_currency(curr)

    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            if user.is_blocked:
                blocked_user_notice = user.block_reason or "Your account has been restricted. Please contact support."
            session['balance'] = user.balance
            curr = user.currency
            flutterwave_deposit_link = get_flutterwave_link_for_currency(curr)
            if not user.welcomed: show_welcome_modal = True
            ref_count = User.query.filter_by(referred_by=user.username).count()

        unacknowledged_deposit = DepositRequest.query.filter_by(user_id=session['user_id'], status='Pending', user_acknowledged=False).order_by(DepositRequest.created_at.desc()).first()
        unacknowledged_withdrawal = WithdrawalRequest.query.filter_by(user_id=session['user_id'], status='Pending', user_acknowledged=False).order_by(WithdrawalRequest.created_at.desc()).first()
        uncelebrated_win = Bet.query.filter_by(user_id=session['user_id'], status='Won', celebrated=False).order_by(Bet.created_at.desc()).first()

    recent_winners = Bet.query.filter_by(status='Won').order_by(Bet.created_at.desc()).limit(5).all()
    for rw in recent_winners:
        rw.masked_name = mask_username(rw.user.username)

    min_deposit_val = get_min_deposit(curr)
    min_stake_val = get_min_stake(curr)

    return dict(
        unacknowledged_deposit=unacknowledged_deposit,
        unacknowledged_withdrawal=unacknowledged_withdrawal,
        uncelebrated_win=uncelebrated_win,
        blocked_user_notice=blocked_user_notice,
        show_welcome_modal=show_welcome_modal,
        recent_winners=recent_winners,
        support_whatsapp=SUPPORT_WHATSAPP_NUMBER,
        flutterwave_deposit_link=flutterwave_deposit_link,
        min_deposit_val=min_deposit_val,
        min_stake_val=min_stake_val,
        ref_count=ref_count,
        crypto_wallets=CRYPTO_WALLETS,
        urllib_quote=urllib.parse.quote
    )

@app.route('/dismiss_welcome', methods=['POST'])
def dismiss_welcome():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user: user.welcomed = True; db.session.commit()
    return jsonify({'success': True})

@app.route('/dismiss_deposit/<int:dep_id>', methods=['POST'])
def dismiss_deposit(dep_id):
    if 'user_id' in session: session[f'dismissed_deposit_{dep_id}'] = True
    return jsonify({'success': True})

@app.route('/dismiss_celebration/<int:ticket_id>', methods=['POST'])
def dismiss_celebration(ticket_id):
    if 'user_id' in session:
        ticket = Bet.query.get(ticket_id)
        if ticket and ticket.user_id == session['user_id']:
            ticket.celebrated = True
            user = User.query.get(ticket.user_id)
            if user: session['balance'] = user.balance
            db.session.commit()
    return jsonify({'success': True})

@app.route('/')
def index():
    run_automated_bookmaker_engine()
    tab = request.args.get('tab', 'today')
    now_dt = get_now_local()
    today_str = now_dt.strftime('%Y-%m-%d')
    tomorrow_str = (now_dt + timedelta(days=1)).strftime('%Y-%m-%d')

    if tab == 'today':
        matches = Match.query.filter(
            Match.sport == 'Football',
            Match.status == 'Upcoming',
            Match.match_date.in_([today_str, tomorrow_str])
        ).order_by(Match.match_date.asc(), Match.match_time.asc()).all()
    elif tab == 'live':
        matches = Match.query.filter(Match.status == 'Live').order_by(Match.match_date.asc(), Match.match_time.asc()).all()
    elif tab == 'basketball':
        matches = Match.query.filter(Match.sport == 'Basketball', Match.status != 'Finished').order_by(Match.match_date.asc(), Match.match_time.asc()).all()
    elif tab == 'tennis':
        matches = Match.query.filter(Match.sport == 'Tennis', Match.status != 'Finished').order_by(Match.match_date.asc(), Match.match_time.asc()).all()
    else:
        matches = Match.query.filter(Match.status == 'Upcoming').order_by(Match.match_date.asc(), Match.match_time.asc()).all()

    matches = attach_match_dictionaries(matches)
    return render_template_string(HOME_TEMPLATE, matches=matches, current_tab=tab, auto_load_slip=None)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_username':
            new_username = request.form.get('username', '').strip()
            if new_username and new_username != user.username:
                existing = User.query.filter_by(username=new_username).first()
                if existing:
                    flash('Username already taken!', 'danger')
                else:
                    user.username = new_username
                    session['username'] = new_username
                    db.session.commit()
                    flash('Username updated successfully!', 'success')

        elif action == 'update_password':
            current_pwd = request.form.get('current_password')
            new_pwd = request.form.get('new_password')

            if user.password != current_pwd:
                flash('Current password is incorrect!', 'danger')
            elif not new_pwd:
                flash('Please enter a valid new password.', 'danger')
            else:
                user.password = new_pwd
                db.session.commit()
                flash('Password updated successfully!', 'success')

        elif action == 'update_currency':
            new_currency = request.form.get('currency')
            if new_currency in CURRENCY_RATES_TO_USD and new_currency != user.currency:
                old_rate = CURRENCY_RATES_TO_USD.get(user.currency, 1.0)
                new_rate = CURRENCY_RATES_TO_USD.get(new_currency, 1.0)

                balance_in_usd = user.balance / old_rate
                user.balance = round(balance_in_usd * new_rate, 2)

                user.currency = new_currency
                session['currency'] = new_currency
                session['balance'] = user.balance
                db.session.commit()
                flash(f'Currency changed to {new_currency}! Balance adjusted.', 'success')

        return redirect(url_for('settings'))

    return render_template_string(SETTINGS_TEMPLATE, user=user)

@app.route('/share/<code_id>')
def share_slip(code_id):
    run_automated_bookmaker_engine()
    matches = attach_match_dictionaries(Match.query.filter(Match.sport == 'Football', Match.status != 'Finished').order_by(Match.match_date.asc(), Match.match_time.asc()).all())
    booking = BookingSlip.query.filter_by(code=code_id.upper()).first()
    auto_data = booking.slip_data if booking else None
    return render_template_string(HOME_TEMPLATE, matches=matches, current_tab='today', auto_load_slip=auto_data)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        currency = request.form['currency']
        ref_by = request.form.get('ref', None)

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
        user = User(username=username, email=email, password=password, currency=currency, balance=0.0, bonus_balance=0.0, welcomed=False, referred_by=ref_by)
        db.session.add(user); db.session.commit()
        session['user_id'] = user.id; session['username'] = user.username; session['balance'] = user.balance; session['currency'] = user.currency; session['is_admin'] = user.is_admin
        flash('Registration successful! Make your first deposit to claim your 100% deposit match bonus!', 'success')
        return redirect(url_for('index'))

    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if user_ip and ',' in user_ip: user_ip = user_ip.split(',')[0].strip()
    detected_currency = detect_currency_by_ip(user_ip)
    return render_template_string(REGISTER_TEMPLATE, detected_currency=detected_currency)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email'], password=request.form['password']).first()
        if user:
            session['user_id'] = user.id; session['username'] = user.username; session['balance'] = user.balance; session['currency'] = user.currency; session['is_admin'] = user.is_admin
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        flash('Invalid email or password.', 'danger')
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    check_request_expirations()
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    session['balance'] = user.balance
    deposits = DepositRequest.query.filter_by(user_id=user.id).order_by(DepositRequest.created_at.desc()).all()
    withdrawals = WithdrawalRequest.query.filter_by(user_id=user.id).order_by(WithdrawalRequest.created_at.desc()).all()
    return render_template_string(DASHBOARD_TEMPLATE, user=user, deposits=deposits, withdrawals=withdrawals, withdrawal_error=session.pop('withdrawal_error', None))

@app.route('/bets_history')
def bets_history():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    session['balance'] = user.balance
    status_filter = request.args.get('status', 'Running')
    if status_filter == 'Running': tickets = Bet.query.filter_by(user_id=user.id, status='Pending').order_by(Bet.created_at.desc()).all()
    elif status_filter == 'Won': tickets = Bet.query.filter_by(user_id=user.id, status='Won').order_by(Bet.created_at.desc()).all()
    elif status_filter == 'Lost': tickets = Bet.query.filter_by(user_id=user.id, status='Lost').order_by(Bet.created_at.desc()).all()
    else: tickets = Bet.query.filter_by(user_id=user.id).order_by(Bet.created_at.desc()).all()

    for t in tickets:
        try:
            raw_items = json.loads(t.ticket_items_json)
            parsed = []
            for item in raw_items:
                match_id = item.get('matchId')
                m_obj = Match.query.get(match_id)
                pick_raw = item.get('pick', '')

                market = "1X2"
                display_pick = pick_raw
                if pick_raw.startswith('CS_'):
                    market = "Correct Score"
                    display_pick = pick_raw.replace('CS_', '')
                elif pick_raw.startswith('Over_'):
                    market = "Over / Under"
                    display_pick = f"Over {pick_raw.replace('Over_', '')}"
                elif pick_raw.startswith('Under_'):
                    market = "Over / Under"
                    display_pick = f"Under {pick_raw.replace('Under_', '')}"
                elif 'BTTS' in pick_raw:
                    market = "BTTS"
                    display_pick = pick_raw.replace('BTTS ', '')
                elif pick_raw in ['Home', 'Draw', 'Away']:
                    market = "1X2"
                    display_pick = pick_raw

                if not m_obj or m_obj.status == 'Upcoming':
                    score_display = "Not Started"
                elif m_obj.status == 'Live':
                    score_display = f"{m_obj.score_home}-{m_obj.score_away} ({m_obj.match_minute})"
                else:
                    score_display = f"FT: {m_obj.score_home}-{m_obj.score_away}"

                is_won = False
                if t.status == 'Won':
                    is_won = True
                elif m_obj and m_obj.status == 'Finished':
                    m_tot = m_obj.score_home + m_obj.score_away
                    if pick_raw == 'Home' and m_obj.winner == 'Home': is_won = True
                    elif pick_raw == 'Draw' and m_obj.winner == 'Draw': is_won = True
                    elif pick_raw == 'Away' and m_obj.winner == 'Away': is_won = True
                    elif pick_raw.startswith('Over_'):
                        line = float(pick_raw.replace('Over_', ''))
                        if m_tot > line: is_won = True
                    elif pick_raw.startswith('Under_'):
                        line = float(pick_raw.replace('Under_', ''))
                        if m_tot < line: is_won = True
                    elif pick_raw == 'BTTS Yes' and m_obj.score_home > 0 and m_obj.score_away > 0: is_won = True
                    elif pick_raw == 'BTTS No' and (m_obj.score_home == 0 or m_obj.score_away == 0): is_won = True
                    elif pick_raw.startswith('CS_'):
                        if pick_raw.replace('CS_', '') == f"{m_obj.score_home}-{m_obj.score_away}": is_won = True

                parsed.append({
                    'matchName': item.get('matchName', 'Match').split(' (')[0],
                    'pick': display_pick,
                    'odds': item.get('odds', 1.0),
                    'market': market,
                    'score_display': score_display,
                    'is_won': is_won
                })
            t.parsed_items = parsed
        except:
            t.parsed_items = []

    return render_template_string(BET_HISTORY_TEMPLATE, user=user, tickets=tickets, filter_status=status_filter)

@app.route('/deposit', methods=['POST'])
def deposit():
    if 'user_id' not in session: return redirect(url_for('login'))
    try:
        user = User.query.get(session['user_id'])
        amount = float(request.form['amount'])
        min_dep = get_min_deposit(user.currency)

        if amount < min_dep:
            flash(f'Minimum deposit is {user.currency} {min_dep:.2f}.', 'danger')
            return redirect(url_for('dashboard'))

        pm = request.form['payment_method']

        # Initialize deposit request
        dep = DepositRequest(
            user_id=user.id,
            amount=amount,
            payment_method=pm,
            support_message="Processing payment instructions...",
            support_has_updated=True
        )
        db.session.add(dep)
        db.session.commit()

        # Hybrid Flutterwave Charge Generation for Local Currencies vs Links
        if user.currency in ['NGN', 'GHS'] and 'Instant' in pm and FLUTTERWAVE_SECRET_KEY:
            payload = {
                "tx_ref": f"WP-DEP-{dep.id}-{int(datetime.utcnow().timestamp())}",
                "amount": str(amount),
                "currency": user.currency,
                "redirect_url": f"https://{request.host}/dashboard?payment=verified",
                "customer": {
                    "email": user.email,
                    "name": user.username,
                    "phonenumber": "08000000000"
                },
                "customizations": {
                    "title": "Winnerpari Deposit",
                    "description": f"Funding account #{user.id}"
                }
            }

            headers = {
                "Authorization": f"Bearer {FLUTTERWAVE_SECRET_KEY}",
                "Content-Type": "application/json"
            }

            try:
                flw_res = requests.post("https://api.flutterwave.com/v3/payments", json=payload, headers=headers, timeout=10)
                flw_data = flw_res.json()

                if flw_data.get("status") == "success":
                    dynamic_link = flw_data["data"]["link"]
                    dep.support_message = f"Dynamic checkout generated. Complete your payment of {user.currency} {amount:.2f}."
                    return redirect(dynamic_link)
                else:
                    dep.support_message = f"Please use our standard secure payment link to complete your deposit of {user.currency} {amount:.2f}."
            except Exception as api_err:
                print(f"Flutterwave API Error: {api_err}")
                dep.support_message = f"Please complete your deposit via the secure payment gateway link."

        elif 'Crypto' in pm:
            dep.support_message = f"Crypto Deposit Request.\nPlease transfer {user.currency} {amount:.2f} equivalent to any of our accepted wallets and click 'Done'."
        elif 'Support' in pm:
            dep.support_message = f"Other Payment Method Request for {user.currency} {amount:.2f}.\nPlease contact support on WhatsApp for alternative payment details."
        else:
            dep.support_message = f"Please wait for your payment confirmation. Once confirmed, your payment will be reflected in your balance. Click 'Done' if your payment is complete."

        db.session.commit()
        session.pop(f'dismissed_deposit_{dep.id}', None)
        flash('Deposit request created successfully!', 'success')
        return redirect(url_for('dashboard'))

    except Exception:
        flash('Error submitting deposit.', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/acknowledge_deposit/<int:dep_id>', methods=['POST'])
def acknowledge_deposit(dep_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    dep = DepositRequest.query.get(dep_id)
    if dep and dep.user_id == session['user_id']:
        dep.user_acknowledged = True; db.session.commit()
        flash('Deposit marked as paid. Waiting for admin approval.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        user = User.query.get(session['user_id'])
        amount = float(request.form['amount'])

        if user.balance <= 0:
            flash('You do not have any funds in your balance to withdraw.', 'danger')
            return redirect(url_for('dashboard'))

        if user.balance < amount:
            flash(f'Insufficient balance for withdrawal. Your balance is {user.currency} {user.balance:.2f}.', 'danger')
            return redirect(url_for('dashboard'))

        payout_method = request.form['payout_method']
        account_details = request.form['account_details']

        if user.is_admin:
            user.balance -= amount
            session['balance'] = user.balance
            w = WithdrawalRequest(
                user_id=user.id, amount=amount, payout_method=payout_method,
                account_details=account_details, status='Successful',
                support_message='Admin instant withdrawal processed successfully.',
                support_has_updated=True, user_acknowledged=True
            )
            db.session.add(w)
            db.session.commit()
            flash('Admin withdrawal processed instantly! View receipt in your history.', 'success')
            return redirect(url_for('dashboard'))

        user_deposits = DepositRequest.query.filter_by(user_id=user.id, status='Approved').all()
        total_deposited = sum(d.amount for d in user_deposits)

        if len(user_deposits) == 0:
            flash('You must complete at least one approved deposit before requesting a withdrawal.', 'danger')
            return redirect(url_for('dashboard'))

        if len(user_deposits) == 1:
            required_double = total_deposited * 2.0
            flash(f'Security Rule: You currently have only a single deposit ({user.currency} {total_deposited:.2f}). To be eligible for withdrawals, you are required to make at least two additional deposits (or reach a total deposit of at least {user.currency} {required_double:.2f}) to increase your wagering activity.', 'danger')
            return redirect(url_for('dashboard'))

        user.balance -= amount
        session['balance'] = user.balance

        w = WithdrawalRequest(
            user_id=user.id, amount=amount, payout_method=payout_method,
            account_details=account_details, status='Pending',
            support_message='Your withdrawal request is received and under review by management.',
            support_has_updated=False, user_acknowledged=False
        )
        db.session.add(w)
        db.session.commit()
        flash('Withdrawal request submitted successfully! Your account is under review and waiting for admin approval.', 'success')

    except Exception as e:
        flash('Error processing withdrawal.', 'danger')

    return redirect(url_for('dashboard'))

@app.route('/place_accumulator', methods=['POST'])
def place_accumulator():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    try:
        stake = float(request.form['stake'])
        min_stake = get_min_stake(user.currency)
        if stake < min_stake:
            flash(f'Minimum stake allowed is {user.currency} {min_stake:.2f}!', 'danger')
            return redirect(url_for('index'))
        if user.balance < stake:
            flash(f'Insufficient balance! You need {user.currency} {stake:.2f}. Please deposit funds.', 'danger')
            return redirect(url_for('index'))
        raw_data = request.form['slip_data']
        slip_data = json.loads(raw_data)
        if not slip_data: return redirect(url_for('index'))
        total_odds = 1.00
        for item in slip_data: total_odds *= float(item['odds'])
        potential_win = stake * total_odds
        tt = 'Single' if len(slip_data) == 1 else 'Accumulator'
        code = "WP-" + uuid.uuid4().hex[:5].upper()
        db.session.add(BookingSlip(code=code, slip_data=raw_data))
        user.balance -= stake; session['balance'] = user.balance
        db.session.add(Bet(user_id=user.id, ticket_items_json=raw_data, total_odds=total_odds, amount=stake, potential_win=potential_win, ticket_type=tt, booking_code=code, status='Pending'))
        db.session.commit()
        flash(f'🎉 {tt} bet placed successfully! Booking Code: {code}', 'success')
    except Exception:
        flash('Error placing bet.', 'danger')
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    if not session.get('is_admin'): return redirect(url_for('login'))
    matches = Match.query.order_by(Match.match_date.asc(), Match.match_time.asc()).all()
    deposits = DepositRequest.query.filter_by(status='Pending').all()
    withdrawals = WithdrawalRequest.query.filter_by(status='Pending').all()
    notif = Setting.query.filter_by(key='notification_email').first()
    return render_template_string(ADMIN_TEMPLATE, total_users=User.query.count(), matches=matches, deposits=deposits, withdrawals=withdrawals, support_whatsapp=SUPPORT_WHATSAPP_NUMBER, notification_email=notif.value if notif else 'admin@winnerpari.com')

@app.route('/admin/lookup_user', methods=['GET'])
def admin_lookup_user():
    if not session.get('is_admin'): return redirect(url_for('login'))
    target_user = User.query.get(request.args.get('user_id', type=int))
    if not target_user:
        flash('User ID not found.', 'danger')
        return redirect(url_for('admin'))
    return render_template_string(USER_PROFILE_TEMPLATE, target_user=target_user)

@app.route('/admin/adjust_balance/<int:user_id>', methods=['POST'])
def admin_adjust_balance(user_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    try:
        user = User.query.get(user_id)
        amount = float(request.form['amount'])
        action_type = request.form['action_type']
        if user:
            if action_type == 'add':
                user.balance += amount
                flash(f'Successfully added {user.currency} {amount:.2f} to user #{user.id}.', 'success')
            elif action_type == 'subtract':
                user.balance -= amount
                flash(f'Successfully deducted {user.currency} {amount:.2f} from user #{user.id}.', 'success')
            db.session.commit()
    except Exception:
        flash('Error adjusting balance.', 'danger')
    return redirect(url_for('admin_lookup_user', user_id=user_id))

@app.route('/admin/block_user/<int:user_id>', methods=['POST'])
def admin_block_user(user_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    user = User.query.get(user_id)
    if user:
        user.is_blocked = True
        user.block_reason = request.form.get('block_reason', 'Your account has been restricted by management.')
        db.session.commit()
        flash(f'User #{user.id} has been blocked successfully.', 'success')
    return redirect(url_for('admin_lookup_user', user_id=user_id))

@app.route('/admin/unblock_user/<int:user_id>', methods=['POST'])
def admin_unblock_user(user_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    user = User.query.get(user_id)
    if user:
        user.is_blocked = False
        user.block_reason = None
        db.session.commit()
        flash(f'User #{user.id} has been unblocked successfully.', 'success')
    return redirect(url_for('admin_lookup_user', user_id=user_id))

@app.route('/admin/create_match', methods=['POST'])
def admin_create_match():
    if not session.get('is_admin'): return redirect(url_for('login'))
    try:
        oh = float(request.form['odds_home'])
        od = float(request.form['odds_draw'])
        oa = float(request.form['odds_away'])
        db.session.add(Match(
            sport=request.form['sport'], league=request.form['league'], team_home=request.form['team_home'], team_away=request.form['team_away'],
            match_date=request.form['match_date'], match_time=request.form['match_time'], odds_home=oh,
            odds_draw=od, odds_away=oa, target_score_home=int(request.form['target_score_home']),
            target_score_away=int(request.form['target_score_away']), over_under_json=generate_over_under_lines(), correct_scores_json=generate_correct_scores(oh, oa, od), is_auto=False
        ))
        db.session.commit()
        flash('Match created successfully!', 'success')
    except: flash('Error creating match.', 'danger')
    return redirect(url_for('admin'))

@app.route('/admin/delete_match/<int:match_id>', methods=['POST'])
def admin_delete_match(match_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    m = Match.query.get(match_id)
    if m: db.session.delete(m); db.session.commit()
    flash('Match deleted successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/update_target_score/<int:match_id>', methods=['POST'])
def update_target_score(match_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    m = Match.query.get(match_id)
    if m:
        m.target_score_home = int(request.form['target_home'])
        m.target_score_away = int(request.form['target_away'])
        db.session.commit()
        flash('Target score updated successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/approve_deposit/<int:dep_id>', methods=['POST'])
def approve_deposit(dep_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    dep = DepositRequest.query.get(dep_id)
    if dep and dep.status == 'Pending':
        dep.status = 'Approved'; dep.user_acknowledged = True
        usr = User.query.get(dep.user_id)
        usr.balance += dep.amount
        db.session.commit()
        flash('Deposit approved successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/decline_deposit/<int:dep_id>', methods=['POST'])
def decline_deposit(dep_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    dep = DepositRequest.query.get(dep_id)
    if dep and dep.status == 'Pending':
        dep.status = 'Declined'; dep.user_acknowledged = True
        db.session.commit()
        flash('Deposit declined.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/approve_withdrawal/<int:w_id>', methods=['POST'])
def approve_withdrawal(w_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    w = WithdrawalRequest.query.get(w_id)
    if w and w.status == 'Pending':
        w.status = 'Successful'
        w.support_message = 'Your withdrawal request has been approved and processed by management.'
        w.support_has_updated = True
        w.user_acknowledged = True
        db.session.commit()
        flash('Withdrawal request approved successfully!', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/decline_withdrawal/<int:w_id>', methods=['POST'])
def decline_withdrawal(w_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    w = WithdrawalRequest.query.get(w_id)
    if w and w.status == 'Pending':
        w.status = 'Declined'
        w.support_message = 'Your withdrawal request was declined by management.'
        w.support_has_updated = True
        w.user_acknowledged = True
        usr = User.query.get(w.user_id)
        if usr:
            usr.balance += w.amount
        db.session.commit()
        flash('Withdrawal request declined and funds refunded to user balance.', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/settle_match/<int:match_id>', methods=['POST'])
def settle_match(match_id):
    if not session.get('is_admin'): return redirect(url_for('login'))
    match = Match.query.get(match_id)
    match.score_home = int(request.form['final_home'])
    match.score_away = int(request.form['final_away'])
    process_match_settlement(match)
    db.session.commit()
    flash('Match settled successfully!', 'success')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)
