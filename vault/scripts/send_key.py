import smtplib, os, datetime, sys
from email.mime.text import MIMEText
from pathlib import Path

uuid         = os.environ['UUID']
unlock_year  = int(os.environ['UNLOCK_YEAR'])
unlock_month = int(os.environ['UNLOCK_MONTH'])
unlock_day   = int(os.environ['UNLOCK_DAY'])
name         = os.environ['SECRET_NAME']
DELIVERY_EMAIL = os.environ['DELIVERY_EMAIL']
SMTP_USER    = os.environ['SMTP_USER']
SMTP_PASS    = os.environ['SMTP_PASS']

unlock_date = datetime.date(unlock_year, unlock_month, unlock_day)
if datetime.date.today() < unlock_date:
    print(f'Not yet unlocked. Unlock date: {unlock_date}')
    sys.exit(0)

key_file = Path(f'vault/keys/{uuid}.key')
if not key_file.exists():
    print(f'Key file not found: {key_file}')
    sys.exit(1)

VAULT_KEY = key_file.read_text().strip()

body = (
    f'Your time-safe vault has unlocked.\n\n'
    f'Secret name: {name}\n'
    f'Decryption key (base64): {VAULT_KEY}\n\n'
    f'Enter this key in the time-safe app when prompted to decrypt.'
)
msg = MIMEText(body)
msg['Subject'] = f'Vault Unlock: {name}'
msg['From']    = SMTP_USER
msg['To']      = DELIVERY_EMAIL

with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
    s.login(SMTP_USER, SMTP_PASS)
    s.sendmail(SMTP_USER, [DELIVERY_EMAIL], msg.as_string())
    print('Key delivered successfully.')
