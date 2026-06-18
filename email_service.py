import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv

load_dotenv()

SENDGRID_API_KEY   = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")


def send_email(to_email, subject, body):
    try:
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            plain_text_content=body
        )
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"Email sent to {to_email} — status {response.status_code}")
        return True

    except Exception as e:
        print(f"EMAIL ERROR: {e}")
        return False


def send_address_change_email(to_email, order_id, new_address):
    subject = f"Delivery Address Updated — {order_id}"
    body = (
        f"Hi,\n\n"
        f"Your delivery address for order {order_id} has been updated.\n\n"
        f"New Delivery Address:\n{new_address}\n\n"
        f"If you did not request this change, please contact support immediately.\n\n"
        f"Thank you for shopping with us.\n"
        f"— ShopBot Support Team"
    )
    return send_email(to_email, subject, body)


def send_cancellation_email(to_email, order_id):
    subject = f"Order Cancelled — {order_id}"
    body = (
        f"Hi,\n\n"
        f"Your order {order_id} has been successfully cancelled.\n\n"
        f"If you paid for this order, a refund will be processed within 5-7 business days.\n\n"
        f"If you did not request this cancellation, please contact support immediately.\n\n"
        f"Thank you for shopping with us.\n"
        f"— ShopBot Support Team"
    )
    return send_email(to_email, subject, body)


def send_ticket_created_email(to_email, ticket_id, issue_type, description):
    subject = f"Support Ticket Created — #{ticket_id}"
    body = (
        f"Hi,\n\n"
        f"We've created a support ticket for your recent request.\n\n"
        f"Ticket ID: #{ticket_id}\n"
        f"Issue Type: {issue_type}\n"
        f"Details: {description}\n\n"
        f"Our team will get back to you as soon as possible.\n\n"
        f"Thank you for your patience.\n"
        f"— ShopBot Support Team"
    )
    return send_email(to_email, subject, body)
