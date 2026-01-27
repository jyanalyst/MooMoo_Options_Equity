#!/usr/bin/env python3
"""
Earnings Calendar Monitor for Wheel Strategy

Weekly email alert system that categorizes WHEEL_UNIVERSE stocks by earnings proximity:
- AVOID: Earnings <14 days away (do not open new CSPs)
- CAUTION: Earnings 14-30 days away (monitor closely)
- SAFE: Earnings >30 days away or no scheduled earnings

Designed to run:
- Manually: python earnings_monitor.py
- Cron job: 0 9 * * 0 (every Sunday 9 AM SGT)

Uses FMP API for earnings calendar data.
SMTP credentials should be set via environment variables for security.
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Import universe
from universe import WHEEL_UNIVERSE

# Import FMP API key
from config import FMP_API_KEY

# =============================================================================
# CONFIGURATION
# =============================================================================

# SMTP Configuration (use environment variables for security)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SENDER_EMAIL = os.getenv('SENDER_EMAIL')  # Your Gmail address
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')  # App-specific password
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL')  # Destination email (defaults to sender)

# Earnings categorization thresholds (days)
AVOID_THRESHOLD = 14  # <14 days = AVOID
CAUTION_THRESHOLD = 30  # 14-30 days = CAUTION
CALENDAR_HORIZON = 45  # Look ahead 45 days

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# FMP API FUNCTIONS
# =============================================================================

def fetch_earnings_for_ticker(ticker: str) -> Optional[str]:
    """
    Fetch next FUTURE earnings date for a single ticker using FMP stable API.

    Uses the same endpoint pattern as fmp_data_fetcher.py which works
    on the Starter plan.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Earnings date string (YYYY-MM-DD) or None if not found/no future earnings
    """
    # Use stable API endpoint (same as fmp_data_fetcher.py)
    url = f"https://financialmodelingprep.com/stable/earnings-calendar"
    params = {
        'symbol': ticker,
        'apikey': FMP_API_KEY
    }

    today = datetime.now().date()

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data and len(data) > 0:
            # Look for FUTURE earnings dates (FMP may return multiple or past dates)
            for event in data:
                date_str = event.get('date')
                if date_str:
                    try:
                        earnings_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        # Only return future dates (tomorrow or later)
                        if earnings_date > today:
                            return date_str
                    except ValueError:
                        continue

            # If all dates are in the past, return None (no upcoming earnings)
            logger.debug(f"{ticker}: All earnings dates are in the past")
            return None

        return None

    except requests.exceptions.HTTPError as e:
        logger.debug(f"HTTP error for {ticker}: {e.response.status_code}")
        return None
    except Exception as e:
        logger.debug(f"Error fetching earnings for {ticker}: {e}")
        return None


def fetch_earnings_batch(tickers: List[str], delay: float = 0.5) -> Dict[str, str]:
    """
    Fetch earnings dates for multiple tickers with rate limiting.

    Args:
        tickers: List of ticker symbols
        delay: Delay between API calls (seconds)

    Returns:
        Dict mapping ticker -> earnings date string
    """
    import time

    earnings_map: Dict[str, str] = {}
    total = len(tickers)

    logger.info(f"Fetching earnings for {total} tickers...")

    for i, ticker in enumerate(tickers, 1):
        if i % 10 == 0:
            logger.info(f"  Progress: {i}/{total} tickers")

        date = fetch_earnings_for_ticker(ticker)
        if date:
            earnings_map[ticker] = date

        # Rate limiting
        if i < total:
            time.sleep(delay)

    logger.info(f"Found earnings dates for {len(earnings_map)}/{total} tickers")
    return earnings_map


# =============================================================================
# CATEGORIZATION LOGIC
# =============================================================================

def categorize_earnings(universe: List[str]) -> Tuple[List[Tuple], List[Tuple], List[Tuple]]:
    """
    Categorize universe stocks by earnings proximity.

    Args:
        universe: List of ticker symbols

    Returns:
        Tuple of (avoid_list, caution_list, safe_list)
        Each list contains tuples: (ticker, date_str, days_away)
        - avoid_list: <14 days (DO NOT open new CSPs)
        - caution_list: 14-30 days (monitor closely)
        - safe_list: >30 days or no earnings scheduled
    """
    today = datetime.now()

    # Fetch earnings for each ticker individually (works on Starter plan)
    universe_earnings = fetch_earnings_batch(universe, delay=0.5)

    # Categorize each ticker
    avoid_list: List[Tuple] = []     # <14 days
    caution_list: List[Tuple] = []   # 14-30 days
    safe_list: List[Tuple] = []      # >30 days or no earnings

    for ticker in sorted(universe):
        if ticker in universe_earnings:
            date_str = universe_earnings[ticker]
            try:
                earnings_date = datetime.strptime(date_str, '%Y-%m-%d')
                days_away = (earnings_date - today).days

                # Future earnings categorization
                if days_away < AVOID_THRESHOLD:
                    avoid_list.append((ticker, date_str, days_away))
                elif days_away < CAUTION_THRESHOLD:
                    caution_list.append((ticker, date_str, days_away))
                else:
                    safe_list.append((ticker, date_str, days_away))
            except ValueError as e:
                logger.warning(f"Invalid date format for {ticker}: {date_str}")
                safe_list.append((ticker, f"Invalid date: {date_str}", None))
        else:
            # No FUTURE earnings found - safe to trade
            safe_list.append((ticker, "No upcoming earnings scheduled", None))

    # Sort by days away (closest first for avoid/caution)
    avoid_list.sort(key=lambda x: x[2] if x[2] is not None else 999)
    caution_list.sort(key=lambda x: x[2] if x[2] is not None else 999)

    return avoid_list, caution_list, safe_list


# =============================================================================
# EMAIL GENERATION
# =============================================================================

def generate_html_email(
    avoid: List[Tuple],
    caution: List[Tuple],
    safe: List[Tuple],
    api_error: Optional[str] = None
) -> str:
    """
    Generate HTML email body.

    Args:
        avoid: List of (ticker, date, days) for <14 days
        caution: List of (ticker, date, days) for 14-30 days
        safe: List of (ticker, date, days) for >30 days
        api_error: Optional error message if API failed

    Returns:
        HTML string
    """
    today = datetime.now()
    today_str = today.strftime('%b %d, %Y')
    week_of = today.strftime('%b %d')

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{
            color: #1a1a1a;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #333;
            margin-top: 30px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{
            background-color: #4a4a4a;
            color: white;
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px 15px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{ background-color: #f5f5f5; }}
        .avoid {{ background-color: #ffebee; }}
        .avoid th {{ background-color: #d32f2f; }}
        .caution {{ background-color: #fff8e1; }}
        .caution th {{ background-color: #ff8f00; }}
        .safe {{ background-color: #e8f5e9; }}
        .safe th {{ background-color: #388e3c; }}
        .safe-list {{
            list-style-type: none;
            padding: 0;
        }}
        .safe-list li {{
            padding: 8px 15px;
            background-color: #e8f5e9;
            margin-bottom: 5px;
            border-radius: 4px;
        }}
        .ticker {{ font-weight: bold; color: #1976d2; }}
        .days {{ color: #666; }}
        .error {{
            background-color: #ffcdd2;
            border: 1px solid #ef5350;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
        }}
        .summary {{
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 20px;
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
    <h1>Earnings Alert - Week of {week_of}</h1>
    <p>Generated: {today_str}</p>
"""

    # API error warning
    if api_error:
        html += f"""
    <div class="error">
        <strong>API Error:</strong> {api_error}<br>
        <em>Data below may be incomplete or cached. Verify manually before trading.</em>
    </div>
"""

    # Summary section
    html += f"""
    <div class="summary">
        <strong>Summary:</strong>
        {len(avoid)} stocks to AVOID |
        {len(caution)} stocks with CAUTION |
        {len(safe)} stocks SAFE to trade
    </div>
"""

    # AVOID section
    html += """
    <h2>AVOID NEW CSPs (Earnings &lt;14 days)</h2>
"""

    if avoid:
        html += """
    <table class="avoid">
        <tr><th>Ticker</th><th>Earnings Date</th><th>Days Away</th></tr>
"""
        for ticker, date_str, days in avoid:
            html += f"""        <tr>
            <td class="ticker">{ticker}</td>
            <td>{date_str}</td>
            <td class="days">{days} days</td>
        </tr>
"""
        html += "    </table>\n"
    else:
        html += """    <p style="color: #388e3c;">No stocks with earnings &lt;14 days. All clear!</p>
"""

    # CAUTION section
    html += """
    <h2>CAUTION (Earnings 14-30 days)</h2>
"""

    if caution:
        html += """
    <table class="caution">
        <tr><th>Ticker</th><th>Earnings Date</th><th>Days Away</th></tr>
"""
        for ticker, date_str, days in caution:
            html += f"""        <tr>
            <td class="ticker">{ticker}</td>
            <td>{date_str}</td>
            <td class="days">{days} days</td>
        </tr>
"""
        html += "    </table>\n"
    else:
        html += "    <p>No stocks in caution zone.</p>\n"

    # SAFE section
    html += """
    <h2>SAFE TO TRADE (&gt;30 days or no earnings scheduled)</h2>
    <ul class="safe-list">
"""

    for ticker, date_info, days in safe:
        if days is not None:
            html += f"""        <li><span class="ticker">{ticker}</span> - Earnings: {date_info} ({days} days)</li>
"""
        else:
            html += f"""        <li><span class="ticker">{ticker}</span> - {date_info}</li>
"""

    html += """    </ul>
"""

    # Footer
    html += f"""
    <div class="footer">
        <p>
            Generated automatically by <strong>earnings_monitor.py</strong><br>
            Data source: Financial Modeling Prep (FMP) API<br>
            Universe size: {len(WHEEL_UNIVERSE)} stocks<br>
            Calendar horizon: {CALENDAR_HORIZON} days<br>
            Thresholds: AVOID &lt;{AVOID_THRESHOLD} days | CAUTION &lt;{CAUTION_THRESHOLD} days
        </p>
        <p><em>Note: Always verify earnings dates before trading. Dates may change.</em></p>
    </div>
</body>
</html>
"""

    return html


def generate_plain_text_email(
    avoid: List[Tuple],
    caution: List[Tuple],
    safe: List[Tuple],
    api_error: Optional[str] = None
) -> str:
    """
    Generate plain text email body (fallback).

    Args:
        avoid: List of (ticker, date, days) for <14 days
        caution: List of (ticker, date, days) for 14-30 days
        safe: List of (ticker, date, days) for >30 days
        api_error: Optional error message if API failed

    Returns:
        Plain text string
    """
    today = datetime.now()
    today_str = today.strftime('%b %d, %Y')

    text = f"""EARNINGS ALERT - Week of {today.strftime('%b %d')}
Generated: {today_str}
{'='*60}

"""

    if api_error:
        text += f"""WARNING: API Error - {api_error}
Data below may be incomplete. Verify manually before trading.

"""

    text += f"""SUMMARY: {len(avoid)} AVOID | {len(caution)} CAUTION | {len(safe)} SAFE

"""

    # AVOID
    text += """AVOID NEW CSPs (Earnings <14 days)
{'-'*40}
"""
    if avoid:
        for ticker, date_str, days in avoid:
            text += f"  {ticker:6} - {date_str} ({days} days)\n"
    else:
        text += "  No stocks to avoid. All clear!\n"

    text += "\n"

    # CAUTION
    text += """CAUTION (Earnings 14-30 days)
{'-'*40}
"""
    if caution:
        for ticker, date_str, days in caution:
            text += f"  {ticker:6} - {date_str} ({days} days)\n"
    else:
        text += "  None\n"

    text += "\n"

    # SAFE
    text += """SAFE TO TRADE (>30 days or no earnings)
{'-'*40}
"""
    for ticker, date_info, days in safe:
        if days is not None:
            text += f"  {ticker:6} - {date_info} ({days} days)\n"
        else:
            text += f"  {ticker:6} - {date_info}\n"

    text += f"""

{'='*60}
Generated by earnings_monitor.py
Data source: FMP API | Universe: {len(WHEEL_UNIVERSE)} stocks
"""

    return text


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
            "  export RECIPIENT_EMAIL='destination@email.com' (optional)\n\n"
            "For Gmail, create an app-specific password:\n"
            "  https://support.google.com/accounts/answer/185833"
        )
        return False

    recipient = RECIPIENT_EMAIL or SENDER_EMAIL

    # Create multipart message (HTML + plain text fallback)
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient

    # Attach both versions (email client will use preferred format)
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        logger.info(f"Connecting to SMTP server {SMTP_SERVER}:{SMTP_PORT}...")

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email sent successfully to {recipient}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        logger.error("Check your SENDER_EMAIL and SENDER_PASSWORD environment variables")
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

def run_monitor(dry_run: bool = False, console_only: bool = False) -> Dict:
    """
    Run the earnings monitor.

    Args:
        dry_run: If True, don't send email (just print summary)
        console_only: If True, print to console and skip email

    Returns:
        Dict with results: {'avoid': [...], 'caution': [...], 'safe': [...], 'email_sent': bool}
    """
    print("\n" + "="*60)
    print("EARNINGS CALENDAR MONITOR")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Universe: {len(WHEEL_UNIVERSE)} stocks")
    print("="*60 + "\n")

    # Categorize earnings
    api_error = None
    try:
        avoid, caution, safe = categorize_earnings(WHEEL_UNIVERSE)
    except Exception as e:
        logger.error(f"Error categorizing earnings: {e}")
        api_error = str(e)
        avoid, caution, safe = [], [], [(t, "Error - verify manually", None) for t in WHEEL_UNIVERSE]

    # Print summary to console
    print(f"AVOID ({len(avoid)} stocks):")
    if avoid:
        for ticker, date_str, days in avoid:
            print(f"  {ticker:6} - {date_str} ({days} days)")
    else:
        print("  None - all clear!")

    print(f"\nCAUTION ({len(caution)} stocks):")
    if caution:
        for ticker, date_str, days in caution:
            print(f"  {ticker:6} - {date_str} ({days} days)")
    else:
        print("  None")

    print(f"\nSAFE ({len(safe)} stocks)")

    # Generate email content
    today = datetime.now().strftime('%b %d')
    subject = f"Earnings Alert - Week of {today}"

    html_body = generate_html_email(avoid, caution, safe, api_error)
    text_body = generate_plain_text_email(avoid, caution, safe, api_error)

    # Send email (unless dry run or console only)
    email_sent = False

    if dry_run:
        print("\n[DRY RUN] Email would be sent with subject:")
        print(f"  {subject}")
        print("\n[DRY RUN] Skipping email send.")
    elif console_only:
        print("\n[CONSOLE ONLY] Skipping email send.")
    else:
        print("\nSending email...")
        email_sent = send_email(subject, html_body, text_body)

    print("\n" + "="*60)
    print("Monitor complete.")
    print("="*60 + "\n")

    return {
        'avoid': avoid,
        'caution': caution,
        'safe': safe,
        'email_sent': email_sent,
        'api_error': api_error
    }


def main():
    """Main entry point with CLI argument handling."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Earnings Calendar Monitor - Weekly email alerts for Wheel Strategy'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print summary without sending email'
    )
    parser.add_argument(
        '--console-only',
        action='store_true',
        help='Print to console only (no email)'
    )
    parser.add_argument(
        '--save-html',
        type=str,
        metavar='FILE',
        help='Save HTML email to file (for testing)'
    )

    args = parser.parse_args()

    # Run monitor
    result = run_monitor(dry_run=args.dry_run, console_only=args.console_only)

    # Optionally save HTML to file
    if args.save_html:
        html = generate_html_email(result['avoid'], result['caution'], result['safe'], result['api_error'])
        with open(args.save_html, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"HTML saved to: {args.save_html}")

    # Exit with appropriate code
    if result.get('api_error'):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
