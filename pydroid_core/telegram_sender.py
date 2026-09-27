"""
Project MIP Pydroid 3: Pure-Python Telegram Bot Dispatcher
Directive: DIR-PROD-PYDROID3-PORT-01

Pure Python REST client for Telegram Bot API:
  - Uses curl_cffi with Chrome TLS impersonation if available, else requests/urllib.
  - Zero external binary dependency (/usr/local/bin/telegram-notify not needed).
  - Sends text messages, high-res PNG charts, and documents/tearsheets.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from .data_engine import get_base_dir


def load_env_credentials() -> Dict[str, str]:
    """Reads credentials from .env file or system environment."""
    base_dir = get_base_dir()
    env_file = base_dir / ".env"
    creds = {
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
    }

    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k == "TELEGRAM_BOT_TOKEN" and not creds["bot_token"]:
                        creds["bot_token"] = v
                    elif k == "TELEGRAM_CHAT_ID" and not creds["chat_id"]:
                        creds["chat_id"] = v

    return creds


class PydroidTelegramSender:
    """Dispatches Telegram notifications and deliverables natively inside Pydroid 3."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        creds = load_env_credentials()
        self.bot_token = bot_token or creds.get("bot_token", "")
        self.chat_id = chat_id or creds.get("chat_id", "")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def _get_session(self):
        """Attempts to return curl_cffi Chrome-impersonated session, else requests session."""
        try:
            from curl_cffi import requests as cffi_requests
            return cffi_requests.Session(impersonate="chrome")
        except ImportError:
            try:
                import requests
                return requests.Session()
            except ImportError:
                return None

    def send_message(self, text: str, parse_mode: str = "HTML", dry_run: bool = False) -> bool:
        """Sends an HTML/text message to the designated Telegram chat."""
        if dry_run:
            print("[Telegram] DRY RUN — Message content:")
            print("-" * 50)
            print(text)
            print("-" * 50)
            return True

        if not self.is_configured():
            print("⚠ Telegram credentials missing! Please configure .env with TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
            return False

        session = self._get_session()
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        url = f"{self.api_url}/sendMessage"
        try:
            if session:
                resp = session.post(url, json=payload, timeout=15)
                res_data = resp.json()
            else:
                import urllib.request
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    res_data = json.loads(r.read().decode())

            if res_data.get("ok"):
                print(f"✓ Telegram message sent successfully (Msg ID: {res_data.get('result', {}).get('message_id')})")
                return True
            else:
                print(f"✗ Telegram API Error: {res_data.get('description')}")
                return False
        except Exception as e:
            print(f"✗ Telegram transmission failed: {e}")
            return False

    def send_photo(self, photo_path: Path, caption: Optional[str] = None, dry_run: bool = False) -> bool:
        """Sends a photo/chart directly to Telegram."""
        if dry_run:
            print(f"[Telegram] DRY RUN — Would dispatch photo: {photo_path} (Caption: {caption})")
            return True

        if not self.is_configured() or not photo_path.exists():
            print(f"⚠ Photo dispatch cancelled: configured={self.is_configured()}, exists={photo_path.exists()}")
            return False

        url = f"{self.api_url}/sendPhoto"
        try:
            import requests
            with open(photo_path, "rb") as f:
                data = {"chat_id": self.chat_id}
                if caption:
                    data["caption"] = caption
                    data["parse_mode"] = "HTML"
                files = {"photo": f}
                resp = requests.post(url, data=data, files=files, timeout=30)
                res_data = resp.json()
            
            if res_data.get("ok"):
                print(f"✓ Telegram photo sent: {photo_path.name}")
                return True
            else:
                print(f"✗ Telegram photo API Error: {res_data.get('description')}")
                return False
        except Exception as e:
            print(f"✗ Telegram photo transmission failed: {e}")
            return False

    def send_document(self, doc_path: Path, caption: Optional[str] = None, dry_run: bool = False) -> bool:
        """Sends a document or HTML tearsheet directly to Telegram."""
        if dry_run:
            print(f"[Telegram] DRY RUN — Would dispatch document: {doc_path} (Caption: {caption})")
            return True

        if not self.is_configured() or not doc_path.exists():
            return False

        url = f"{self.api_url}/sendDocument"
        try:
            import requests
            with open(doc_path, "rb") as f:
                data = {"chat_id": self.chat_id}
                if caption:
                    data["caption"] = caption
                    data["parse_mode"] = "HTML"
                files = {"document": (doc_path.name, f)}
                resp = requests.post(url, data=data, files=files, timeout=30)
                res_data = resp.json()

            if res_data.get("ok"):
                print(f"✓ Telegram document sent: {doc_path.name}")
                return True
            else:
                print(f"✗ Telegram document API Error: {res_data.get('description')}")
                return False
        except Exception as e:
            print(f"✗ Telegram document transmission failed: {e}")
            return False


def format_telegram_alert(
    top_df: pd.DataFrame,
    breadth: Dict,
    sectors: Dict,
    regime: Dict,
    as_of_date: str
) -> str:
    """Formats institutional Telegram HTML message within 4,096 char limit."""
    tp = breadth.get("trend_participation", {})
    hp = breadth.get("high_proximity", {})
    nhl = breadth.get("net_highs_lows", {})
    b_reg = breadth.get("regime", {})

    msg = f"🚀 <b>PROJECT MIP: WEEKLY MOMENTUM ALERT</b>\n"
    msg += f"📅 <b>As of Date:</b> <code>{as_of_date}</code>\n"
    msg += f"🛡️ <b>Benchmark Regime:</b> {regime.get('label', 'N/A')}\n"
    msg += f"📊 <b>Market Breadth:</b> {b_reg.get('label', 'N/A')}\n\n"

    msg += f"📈 <b>BREADTH & TREND PARTICIPATION</b>\n"
    msg += f"• <b>> 200 EMA:</b> {tp.get('pct_above_200_ema', 0)}% ({tp.get('count_above_200_ema', 0)}/{breadth.get('universe_size', 0)})\n"
    msg += f"• <b>> 50 EMA:</b> {tp.get('pct_above_50_ema', 0)}% | <b>> 20 EMA:</b> {tp.get('pct_above_20_ema', 0)}%\n"
    msg += f"• <b>Near 52w High:</b> {hp.get('pct_within_20pct_52wh', 0)}% (Within 20%)\n"
    msg += f"• <b>52w Net Highs:</b> +{nhl.get('new_52w_highs', 0)} / -{nhl.get('new_52w_lows', 0)} (Net: {nhl.get('net_highs_lows', 0):+d})\n\n"

    msg += f"🔄 <b>SECTOR ROTATION (TOP LEADING)</b>\n<pre>"
    msg += f"{'Rank':<4}{'Sector':<11}{'1M Ret':<8}{'Alpha':<8}{'Breadth'}\n"
    msg += "-" * 38 + "\n"
    for s in sectors.get("sectors", [])[:5]:
        msg += f"{s['rank']:<4}{s['sector']:<11}{s['ret_1m']:+5.1f}%  {s['alpha_1m']:+5.1f}%  {s['breadth_200_pct']:4.0f}%\n"
    msg += "</pre>\n"

    msg += f"🏆 <b>TOP MOMENTUM ALLOCATIONS</b>\n<pre>"
    msg += f"{'#':<3}{'Symbol':<12}{'Price':<9}{'Volar':<6}{'RRG'}\n"
    msg += "-" * 38 + "\n"
    for _, r in top_df.head(15).iterrows():
        quad_code = r.get('rrg_quadrant', '')[:4]
        msg += f"{int(r['rank']):<3}{r['symbol']:<12}{r['close']:<9.1f}{r['volar_score']:<6.2f}{quad_code}\n"
    msg += "</pre>\n"
    msg += f"<i>Generated standalone on Samsung Galaxy S23 via Pydroid 3</i>"

    return msg
