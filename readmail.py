import imaplib
import email
import time
import os
from twilio.rest import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Email credentials from .env
EMAIL = os.getenv("EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER")
IMAP_PORT = int(os.getenv("IMAP_PORT"))

# Twilio credentials from .env
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FROM_WA = os.getenv("FROM_WA")
TO_WA = os.getenv("TO_WA")

UID_FILE = 'last_uid.txt'

# Twilio client
client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

# Load UID from file
def load_last_uid():
    if os.path.exists(UID_FILE):
        with open(UID_FILE, 'r') as f:
            return f.read().strip()
    return None

# Save UID to file
def save_last_uid(uid):
    with open(UID_FILE, 'w') as f:
        f.write(str(uid))

# Get the latest UID in the mailbox
def init_last_uid(mail):
    result, data = mail.uid('search', None, 'ALL')
    if result == 'OK':
        all_uids = data[0].split()
        if all_uids:
            return all_uids[-1].decode()
    return None

def check_new_mail():
    last_seen_uid = load_last_uid()

    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL, EMAIL_PASSWORD)
    mail.select("inbox")

    if not last_seen_uid:
        last_seen_uid = init_last_uid(mail)
        if last_seen_uid:
            save_last_uid(last_seen_uid)
        mail.logout()
        print("[*] Initialized UID tracking. No messages forwarded on first run.")
        return

    # Get emails newer than last seen UID
    result, data = mail.uid('search', None, f'(UID {int(last_seen_uid)+1}:*)')
    new_uids = data[0].split()
    print("new_uids:",new_uids)

    if not new_uids or new_uids[0].decode()==last_seen_uid:
        mail.logout()
        print("[*] No new emails.")
        return

    for uid in new_uids:
        print("uid:  ",uid)
        uid_str = uid.decode()
        result, msg_data = mail.uid('fetch', uid_str, '(RFC822)')
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = msg["subject"]
        from_email = msg["from"]

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    body = part.get_payload(decode=True).decode(errors='ignore')
                    break
        else:
            body = msg.get_payload(decode=True).decode(errors='ignore')

        # Send WhatsApp message
        message = f"📧 *New Mail from {from_email}*\n*Subject:* {subject}\n\n{body[:1000]}"
        client.messages.create(body=message, from_=FROM_WA, to=TO_WA)

        print(f"[✓] Forwarded UID {uid_str} - Subject: {subject}")
        save_last_uid(uid_str)

    mail.logout()

if __name__ == "__main__":
    while True:
        try:
            check_new_mail()
        except Exception as e:
            print("[!] Error:", e)
        time.sleep(60)  # check every 15 seconds
