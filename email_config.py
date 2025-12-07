#!/usr/bin/env python3
"""
Email Configuration for Gmail SMTP
"""

import os
from flask_mail import Mail, Message

# Email Configuration
class EmailConfig:
    # Gmail SMTP Settings
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    
    # Your Gmail credentials
    MAIL_USERNAME = 'your-email@gmail.com'  # আপনার Gmail address
    MAIL_PASSWORD = 'your-app-password'     # Gmail App Password
    
    # Email settings
    MAIL_DEFAULT_SENDER = 'your-email@gmail.com'
    MAIL_MAX_EMAILS = 10
    MAIL_ASCII_ATTACHMENTS = False
    
    # Security settings
    MAIL_SUPPRESS_SEND = False  # Set to True for testing
    
    @classmethod
    def init_app(cls, app):
        """Initialize email configuration with Flask app"""
        app.config['MAIL_SERVER'] = cls.MAIL_SERVER
        app.config['MAIL_PORT'] = cls.MAIL_PORT
        app.config['MAIL_USE_TLS'] = cls.MAIL_USE_TLS
        app.config['MAIL_USE_SSL'] = cls.MAIL_USE_SSL
        app.config['MAIL_USERNAME'] = cls.MAIL_USERNAME
        app.config['MAIL_PASSWORD'] = cls.MAIL_PASSWORD
        app.config['MAIL_DEFAULT_SENDER'] = cls.MAIL_DEFAULT_SENDER
        app.config['MAIL_MAX_EMAILS'] = cls.MAIL_MAX_EMAILS
        app.config['MAIL_ASCII_ATTACHMENTS'] = cls.MAIL_ASCII_ATTACHMENTS
        app.config['MAIL_SUPPRESS_SEND'] = cls.MAIL_SUPPRESS_SEND

# Email utility functions
class EmailService:
    def __init__(self, mail):
        self.mail = mail
    
    def send_reset_password_email(self, user_email, reset_token, reset_url):
        """Send password reset email"""
        try:
            subject = "Password Reset Request - Academic Management System"
            
            html_body = f"""
            <html>
            <body>
                <h2>Password Reset Request</h2>
                <p>Hello,</p>
                <p>You have requested to reset your password for the Academic Management System.</p>
                <p>Click the link below to reset your password:</p>
                <p><a href="{reset_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
                <p>Or copy and paste this URL in your browser:</p>
                <p>{reset_url}</p>
                <p>This link will expire in 1 hour.</p>
                <p>If you did not request this password reset, please ignore this email.</p>
                <br>
                <p>Best regards,</p>
                <p>Academic Management System Team</p>
            </body>
            </html>
            """
            
            text_body = f"""
            Password Reset Request
            
            Hello,
            
            You have requested to reset your password for the Academic Management System.
            
            Click the link below to reset your password:
            {reset_url}
            
            This link will expire in 1 hour.
            
            If you did not request this password reset, please ignore this email.
            
            Best regards,
            Academic Management System Team
            """
            
            msg = Message(
                subject=subject,
                recipients=[user_email],
                html=html_body,
                body=text_body
            )
            
            self.mail.send(msg)
            return True, "Password reset email sent successfully"
            
        except Exception as e:
            return False, f"Error sending email: {str(e)}"
    
    def send_welcome_email(self, user_email, username):
        """Send welcome email to new users"""
        try:
            subject = "Welcome to Academic Management System"
            
            html_body = f"""
            <html>
            <body>
                <h2>Welcome to Academic Management System</h2>
                <p>Hello {username},</p>
                <p>Welcome to the Academic Management System!</p>
                <p>Your account has been created successfully.</p>
                <p>You can now log in to access all features.</p>
                <br>
                <p>Best regards,</p>
                <p>Academic Management System Team</p>
            </body>
            </html>
            """
            
            msg = Message(
                subject=subject,
                recipients=[user_email],
                html=html_body
            )
            
            self.mail.send(msg)
            return True, "Welcome email sent successfully"
            
        except Exception as e:
            return False, f"Error sending email: {str(e)}"
    
    def test_email_connection(self):
        """Test email connection"""
        try:
            # Send a test email to yourself
            msg = Message(
                subject="Test Email - Academic Management System",
                recipients=[EmailConfig.MAIL_USERNAME],
                body="This is a test email to verify SMTP configuration."
            )
            
            self.mail.send(msg)
            return True, "Test email sent successfully"
            
        except Exception as e:
            return False, f"Test email failed: {str(e)}"

# Usage example
def setup_email(app):
    """Setup email configuration"""
    EmailConfig.init_app(app)
    mail = Mail(app)
    return mail

def create_email_service(mail):
    """Create email service instance"""
    return EmailService(mail) 