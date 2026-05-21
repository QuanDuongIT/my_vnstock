import resend

from flask import current_app

def send_email(subject, body, to_email):

    resend.api_key = current_app.config["RESEND_API_KEY"]

    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": to_email,
        "subject": subject,
        "text": body
    })