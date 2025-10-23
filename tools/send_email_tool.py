import os
from langchain_core.tools import tool
import smtplib 
from email.mime.text import MIMEText

@tool
def send_email_tool(recipient_email: str, subject: str, body: str) -> str:
    """Sends an email to a specified recipient."""
    sender_email = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_PASSWORD") 

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
            smtp_server.login(sender_email, password)
            smtp_server.sendmail(sender_email, recipient_email, msg.as_string())
        return f"Email sent successfully to {recipient_email}"
    except Exception as e:
        return f"Failed to send email: {e}"