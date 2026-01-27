#!/usr/bin/env python3
"""
VIX Regime Alert System for Wheel Strategy

Real-time monitoring of VIX level with email alerts when crossing regime thresholds:
- VIX < 14: LOW volatility (reduce position sizes, consider waiting)
- VIX 14-18: NORMAL (start/continue trading, standard sizing)
- VIX 18-25: ELEVATED (favorable conditions, normal-to-aggressive sizing)
- VIX > 25: HIGH (aggressive deployment, increase position sizes)

Designed to run:
- Manually: python vix_monitor.py
- Cron job: Every 4 hours during market hours (9:30 AM - 4:00 PM ET)
  Example: 30 9,13 * * 1-5 (9:30 AM and 1:30 PM ET on weekdays)

State is persisted in .vix_state.json to detect threshold crossings.
SMTP credentials should be set via environment variables for security.
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from pathlib import Path
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Import FMP API key
from config import FMP_API_KEY

# =============================================================================
# CONFIGURATION
# =============================================================================

# VIX regime thresholds
VIX_THRESHOLDS = [14, 18, 25]

# Regime definitions
VIX_REGIMES = {
    'LOW': {'min': 0, 'max': 14, 'action': 'Reduce position sizes, consider waiting for better IV'},
    'NORMAL': {'min': 14, 'max': 18, 'action': 'Standard trading, normal position sizes'},
    'ELEVATED': {'min': 18, 'max': 25, 'action': 'Favorable conditions, normal-to-aggressive sizing'},
    'HIGH': {'min': 25, 'max': 100, 'action': 'Aggressive deployment, increase position sizes'}
}

# State file for tracking VIX history
STATE_FILE = Path('.vix_state.json')

# SMTP Configuration (use environment variables for security)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# STATE MANAGEMENT
# =============================================================================

def load_state() -> Dict:
    """
    Load VIX state from file.

    Returns:
        State dict with keys: last_vix, last_check, last_regime
    """
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                logger.info(f"Loaded state: VIX={state.get('last_vix')}, Regime={state.get('last_regime')}")
                return state
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load state file: {e}")

    # Default state (no history)
    return {
        'last_vix': None,
        'last_check': None,
        'last_regime': None
    }


def save_state(vix: float, regime: str) -> None:
    """
    Save VIX state to file.

    Args:
        vix: Current VIX value
        regime: Current regime name (LOW, NORMAL, ELEVATED, HIGH)
    """
    state = {
        'last_vix': vix,
        'last_check': datetime.now().isoformat(),
        'last_regime': regime
    }

    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        logger.info(f"Saved state: VIX={vix:.2f}, Regime={regime}")
    except IOError as e:
        logger.error(f"Could not save state file: {e}")


# =============================================================================
# VIX DATA FETCHING
# =============================================================================

def get_vix_from_fmp() -> Optional[float]:
    """
    Fetch current VIX level from FMP stable API.

    Returns:
        VIX value as float, or None if fetch fails
    """
    # Try stable API quote endpoint
    url = "https://financialmodelingprep.com/stable/quote"
    params = {
        'symbol': '^VIX',
        'apikey': FMP_API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data and len(data) > 0:
            vix = data[0].get('price')
            if vix is not None:
                logger.info(f"Fetched VIX from FMP: {vix:.2f}")
                return float(vix)

        logger.debug(f"FMP VIX response: {data}")
        return None

    except Exception as e:
        logger.debug(f"FMP VIX fetch failed: {e}")
        return None


def get_vix_from_yfinance() -> Optional[float]:
    """
    Fetch current VIX level from yfinance (fallback).

    Returns:
        VIX value as float, or None if fetch fails
    """
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="1d")

        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
            logger.info(f"Fetched VIX from yfinance: {price:.2f}")
            return price

        return None

    except ImportError:
        logger.debug("yfinance not installed")
        return None
    except Exception as e:
        logger.debug(f"yfinance VIX fetch failed: {e}")
        return None


def get_vix_quote() -> Optional[float]:
    """
    Fetch current VIX level (tries FMP first, then yfinance).

    Returns:
        VIX value as float, or None if all sources fail
    """
    # Try FMP stable API first
    vix = get_vix_from_fmp()

    # Fallback to yfinance
    if vix is None:
        logger.info("FMP VIX unavailable, trying yfinance...")
        vix = get_vix_from_yfinance()

    if vix is None:
        logger.error("Could not fetch VIX from any source")

    return vix


def get_vix_regime(vix: float) -> str:
    """
    Determine VIX regime from value.

    Args:
        vix: Current VIX value

    Returns:
        Regime name: 'LOW', 'NORMAL', 'ELEVATED', or 'HIGH'
    """
    if vix < 14:
        return 'LOW'
    elif vix < 18:
        return 'NORMAL'
    elif vix < 25:
        return 'ELEVATED'
    else:
        return 'HIGH'


def get_regime_details(regime: str) -> Dict:
    """
    Get regime configuration details.

    Args:
        regime: Regime name

    Returns:
        Dict with min, max, action keys
    """
    return VIX_REGIMES.get(regime, VIX_REGIMES['NORMAL'])


def detect_threshold_crossing(
    old_vix: Optional[float],
    new_vix: float
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Detect if VIX crossed any threshold.

    Args:
        old_vix: Previous VIX value (None if first check)
        new_vix: Current VIX value

    Returns:
        Tuple of (crossed, threshold, direction)
        - crossed: True if any threshold was crossed
        - threshold: The threshold that was crossed (14, 18, or 25)
        - direction: 'UP' or 'DOWN'
    """
    if old_vix is None:
        return (False, None, None)

    for threshold in VIX_THRESHOLDS:
        # Crossed UP
        if old_vix < threshold <= new_vix:
            return (True, threshold, 'UP')
        # Crossed DOWN
        if old_vix >= threshold > new_vix:
            return (True, threshold, 'DOWN')

    return (False, None, None)


# =============================================================================
# EMAIL GENERATION
# =============================================================================

def generate_alert_email(
    vix: float,
    regime: str,
    old_vix: Optional[float],
    old_regime: Optional[str],
    threshold: int,
    direction: str
) -> Tuple[str, str, str]:
    """
    Generate VIX alert email (subject, HTML body, text body).

    Args:
        vix: Current VIX value
        regime: Current regime name
        old_vix: Previous VIX value
        old_regime: Previous regime name
        threshold: The threshold that was crossed
        direction: 'UP' or 'DOWN'

    Returns:
        Tuple of (subject, html_body, text_body)
    """
    # Determine alert type and emoji
    if direction == 'UP':
        if threshold == 25:
            emoji = ""
            alert_type = "HIGH VOL ALERT"
            color = "#d32f2f"
        elif threshold == 18:
            emoji = ""
            alert_type = "VOL ELEVATED"
            color = "#ff8f00"
        else:  # 14
            emoji = ""
            alert_type = "VOL NORMALIZED"
            color = "#388e3c"
    else:  # DOWN
        if threshold == 25:
            emoji = ""
            alert_type = "VOL COOLING"
            color = "#ff8f00"
        elif threshold == 18:
            emoji = ""
            alert_type = "VOL NORMALIZING"
            color = "#388e3c"
        else:  # 14
            emoji = ""
            alert_type = "LOW VOL ALERT"
            color = "#1976d2"

    regime_details = get_regime_details(regime)
    arrow = "" if direction == 'UP' else ""

    # Subject line
    subject = f"{emoji} VIX {alert_type}: {vix:.2f} ({arrow} crossed {threshold})"

    # HTML body
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .alert-box {{
            background-color: {color};
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            margin-bottom: 20px;
        }}
        .alert-box h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .vix-value {{
            font-size: 48px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .threshold {{
            font-size: 18px;
            opacity: 0.9;
        }}
        .details {{
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .details table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .details td {{
            padding: 8px 0;
            border-bottom: 1px solid #ddd;
        }}
        .details td:first-child {{
            font-weight: bold;
            width: 40%;
        }}
        .action {{
            background-color: #e3f2fd;
            border-left: 4px solid #1976d2;
            padding: 15px;
            margin-bottom: 20px;
        }}
        .action h3 {{
            margin-top: 0;
            color: #1976d2;
        }}
        .footer {{
            color: #666;
            font-size: 12px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="alert-box">
        <h1>{emoji} VIX {alert_type}</h1>
        <div class="vix-value">{vix:.2f}</div>
        <div class="threshold">{arrow} Crossed {threshold} threshold</div>
    </div>

    <div class="details">
        <table>
            <tr>
                <td>Current VIX:</td>
                <td>{vix:.2f}</td>
            </tr>
            <tr>
                <td>Previous VIX:</td>
                <td>{old_vix:.2f if old_vix else 'N/A'}</td>
            </tr>
            <tr>
                <td>Current Regime:</td>
                <td><strong>{regime}</strong> (VIX {regime_details['min']}-{regime_details['max']})</td>
            </tr>
            <tr>
                <td>Previous Regime:</td>
                <td>{old_regime or 'N/A'}</td>
            </tr>
            <tr>
                <td>Threshold Crossed:</td>
                <td>{threshold} ({direction})</td>
            </tr>
            <tr>
                <td>Timestamp:</td>
                <td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
        </table>
    </div>

    <div class="action">
        <h3>Recommended Action</h3>
        <p>{regime_details['action']}</p>
    </div>

    <div class="details">
        <h4>VIX Regime Guide</h4>
        <table>
            <tr><td>LOW (&lt;14)</td><td>Reduce positions, wait for better IV</td></tr>
            <tr><td>NORMAL (14-18)</td><td>Standard trading, normal sizing</td></tr>
            <tr><td>ELEVATED (18-25)</td><td>Favorable conditions, aggressive sizing OK</td></tr>
            <tr><td>HIGH (&gt;25)</td><td>Aggressive deployment, increase sizes</td></tr>
        </table>
    </div>

    <div class="footer">
        <p>
            Generated by <strong>vix_monitor.py</strong><br>
            Data source: Financial Modeling Prep (FMP) API<br>
            Thresholds: {', '.join(map(str, VIX_THRESHOLDS))}
        </p>
    </div>
</body>
</html>
"""

    # Plain text body
    text_body = f"""
VIX {alert_type}
{'='*50}

Current VIX: {vix:.2f}
Previous VIX: {old_vix:.2f if old_vix else 'N/A'}
Threshold Crossed: {threshold} ({direction})

Current Regime: {regime} (VIX {regime_details['min']}-{regime_details['max']})
Previous Regime: {old_regime or 'N/A'}

RECOMMENDED ACTION:
{regime_details['action']}

VIX REGIME GUIDE:
- LOW (<14): Reduce positions, wait for better IV
- NORMAL (14-18): Standard trading, normal sizing
- ELEVATED (18-25): Favorable conditions, aggressive sizing OK
- HIGH (>25): Aggressive deployment, increase sizes

{'='*50}
Generated by vix_monitor.py
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    return subject, html_body, text_body


# =============================================================================
# EMAIL SENDING
# =============================================================================

def send_email(subject: str, html_body: str, text_body: str) -> bool:
    """
    Send email via SMTP (Gmail by default).

    Args:
        subject: Email subject line
        html_body: HTML content
        text_body: Plain text fallback

    Returns:
        True if sent successfully, False otherwise
    """
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        logger.error(
            "Email credentials not configured.\n"
            "Set environment variables:\n"
            "  export SENDER_EMAIL='your-email@gmail.com'\n"
            "  export SENDER_PASSWORD='your-app-specific-password'\n"
            "  export RECIPIENT_EMAIL='destination@email.com' (optional)"
        )
        return False

    recipient = RECIPIENT_EMAIL or SENDER_EMAIL

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        logger.info(f"Connecting to SMTP server {SMTP_SERVER}:{SMTP_PORT}...")

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        logger.info(f"Alert email sent to {recipient}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return False

    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return False

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def check_market_hours() -> bool:
    """
    Check if US market is currently open (rough estimate).

    Note: Does not account for holidays. Use external API for production.

    Returns:
        True if likely during market hours, False otherwise
    """
    # Simple check: weekday and between 9:30 AM - 4:00 PM ET
    # This is a rough estimate; production should use market calendar API
    from datetime import timezone

    now = datetime.now()
    weekday = now.weekday()

    # Skip weekends
    if weekday >= 5:
        return False

    # Rough market hours check (local time - adjust for your timezone)
    # Note: This is approximate. For production, use pytz or timezone-aware logic
    hour = now.hour
    minute = now.minute

    # Assume we're roughly aligned with ET for simplicity
    # 9:30 AM - 4:00 PM ET
    if hour < 9 or (hour == 9 and minute < 30):
        return False
    if hour >= 16:
        return False

    return True


def run_monitor(
    force_alert: bool = False,
    dry_run: bool = False,
    skip_market_check: bool = False
) -> Dict:
    """
    Run the VIX monitor.

    Args:
        force_alert: Send alert even if no threshold crossed (for testing)
        dry_run: Don't send email (just print status)
        skip_market_check: Skip market hours check

    Returns:
        Dict with results
    """
    print("\n" + "="*60)
    print("VIX REGIME MONITOR")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")

    # Check market hours (optional)
    if not skip_market_check:
        is_market_hours = check_market_hours()
        print(f"Market hours check: {'OPEN' if is_market_hours else 'CLOSED'}")
        if not is_market_hours:
            print("Note: Running outside market hours (use --skip-market-check to ignore)")

    # Load previous state
    state = load_state()
    old_vix = state.get('last_vix')
    old_regime = state.get('last_regime')

    print(f"Previous state: VIX={old_vix}, Regime={old_regime}")

    # Fetch current VIX
    vix = get_vix_quote()

    if vix is None:
        print("ERROR: Could not fetch VIX. Check API key and connection.")
        return {'error': 'Failed to fetch VIX', 'email_sent': False}

    # Determine current regime
    regime = get_vix_regime(vix)
    regime_details = get_regime_details(regime)

    print(f"\nCurrent VIX: {vix:.2f}")
    print(f"Current Regime: {regime} (VIX {regime_details['min']}-{regime_details['max']})")
    print(f"Action: {regime_details['action']}")

    # Check for threshold crossing
    crossed, threshold, direction = detect_threshold_crossing(old_vix, vix)

    email_sent = False

    if crossed:
        print(f"\n*** THRESHOLD CROSSED: {threshold} ({direction}) ***")

        if not dry_run:
            subject, html_body, text_body = generate_alert_email(
                vix, regime, old_vix, old_regime, threshold, direction
            )
            email_sent = send_email(subject, html_body, text_body)
        else:
            print("[DRY RUN] Would send alert email")

    elif force_alert:
        print("\n[FORCE ALERT] Sending alert regardless of threshold crossing...")

        if not dry_run:
            # Use 0 as threshold for forced alert
            subject, html_body, text_body = generate_alert_email(
                vix, regime, old_vix, old_regime, 0, 'CHECK'
            )
            subject = f"VIX Status Check: {vix:.2f} ({regime})"
            email_sent = send_email(subject, html_body, text_body)
        else:
            print("[DRY RUN] Would send forced alert email")

    else:
        print("\nNo threshold crossed. No alert needed.")

    # Save current state
    save_state(vix, regime)

    print("\n" + "="*60)
    print("Monitor complete.")
    print("="*60 + "\n")

    return {
        'vix': vix,
        'regime': regime,
        'old_vix': old_vix,
        'old_regime': old_regime,
        'crossed': crossed,
        'threshold': threshold,
        'direction': direction,
        'email_sent': email_sent
    }


def show_status():
    """Display current VIX status without sending alerts."""
    print("\n" + "="*60)
    print("VIX STATUS CHECK")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60 + "\n")

    # Load state
    state = load_state()
    print(f"Last recorded VIX: {state.get('last_vix', 'N/A')}")
    print(f"Last regime: {state.get('last_regime', 'N/A')}")
    print(f"Last check: {state.get('last_check', 'N/A')}")

    # Fetch current
    vix = get_vix_quote()
    if vix:
        regime = get_vix_regime(vix)
        details = get_regime_details(regime)
        print(f"\nCurrent VIX: {vix:.2f}")
        print(f"Current Regime: {regime}")
        print(f"Recommended: {details['action']}")

        # Show distance to thresholds
        print("\nDistance to thresholds:")
        for t in VIX_THRESHOLDS:
            diff = vix - t
            direction = "above" if diff > 0 else "below"
            print(f"  {t}: {abs(diff):.2f} {direction}")
    else:
        print("\nCould not fetch current VIX.")


def main():
    """Main entry point with CLI argument handling."""
    import argparse

    parser = argparse.ArgumentParser(
        description='VIX Regime Monitor - Alert on threshold crossings'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Don't send email (just print status)"
    )
    parser.add_argument(
        '--force-alert',
        action='store_true',
        help='Send alert even if no threshold crossed (for testing)'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show current VIX status only (no alerts)'
    )
    parser.add_argument(
        '--skip-market-check',
        action='store_true',
        help='Skip market hours check'
    )
    parser.add_argument(
        '--reset-state',
        action='store_true',
        help='Reset state file (clear VIX history)'
    )

    args = parser.parse_args()

    # Reset state if requested
    if args.reset_state:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            print("State file reset.")
        else:
            print("No state file to reset.")
        return

    # Status check only
    if args.status:
        show_status()
        return

    # Run monitor
    result = run_monitor(
        force_alert=args.force_alert,
        dry_run=args.dry_run,
        skip_market_check=args.skip_market_check
    )

    # Exit with appropriate code
    if result.get('error'):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
