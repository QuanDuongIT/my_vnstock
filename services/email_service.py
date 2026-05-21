import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import current_app


def send_email(subject, body, to_email):

    sender_email = current_app.config["MAIL_USERNAME"]
    sender_password = current_app.config["MAIL_PASSWORD"]
    sender_server = current_app.config["MAIL_SERVER"]
    port = current_app.config["MAIL_PORT"]

    msg = MIMEMultipart()

    msg["From"] = sender_email
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    server = smtplib.SMTP(sender_server, port)

    try:

        # kết nối bảo mật TLS
        server.starttls()

        # login gmail
        server.login(sender_email, sender_password)

        # gửi mail
        server.send_message(msg)

    except Exception as e:

        print("Send mail error:", e)

    finally:

        server.quit()