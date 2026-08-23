"""Minimal Titan SMTP smoke test, independent from application settings."""

from __future__ import annotations

import argparse
import getpass
import smtplib
from email.message import EmailMessage


SMTP_HOST = "smtp.titan.email"
SMTP_PORT = 465
SMTP_USERNAME = "event@iwbif.id"


def main() -> None:
    parser = argparse.ArgumentParser(description="Send one email through Titan SMTP")
    parser.add_argument("recipient", help="Test email recipient")
    args = parser.parse_args()

    password = getpass.getpass("Titan SMTP password: ")
    message = EmailMessage()
    message["Subject"] = "IWBIF SMTP test"
    message["From"] = f"IWBIF 2026 <{SMTP_USERNAME}>"
    message["To"] = args.recipient
    message.set_content("This is a direct SMTP test from the IWBIF backend development machine.")

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as client:
        client.ehlo()
        client.login(SMTP_USERNAME, password)
        client.send_message(message)

    print("SMTP authentication and test delivery succeeded.")


if __name__ == "__main__":
    main()
