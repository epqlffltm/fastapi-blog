#app/service/email.py

'''
2026-07-24
이메일 발송 서비스 (Gmail SMTP)
비밀번호 변경 구현
'''

import smtplib
from email.message import EmailMessage
from ..database.connection import settings


class EmailService:
    def _send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = settings.smtp_user
        message["To"] = to
        message.set_content(body)

        # 587 + starttls = 평문 연결을 연 뒤 TLS로 승격
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)

    def send_otp(self, to: str, otp: int) -> None:
        self._send(
            to=to,
            subject="[blog] 이메일 인증 코드",
            body=(
                f"인증 코드: {otp}\n\n"
                "3분 안에 입력해 주세요.\n"
                "본인이 요청하지 않았다면 이 메일을 무시하세요."
            ),
        )
        
    def send_password_reset(self, to: str, otp: int) -> None:
        self._send(
            to=to,
            subject="[blog] 비밀번호 재설정 코드",
            body=(
                f"인증 코드: {otp}\n\n"
                "3분 안에 입력해 주세요.\n"
                "본인이 요청하지 않았다면 이 메일을 무시하세요. "
                "비밀번호는 변경되지 않습니다."
            ),
        )