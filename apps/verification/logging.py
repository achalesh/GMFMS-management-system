import logging
import re

TOKEN_PATH = re.compile(r"((?:/api/v1)?/verify/)[^/\s?\"']+")
RESET_PATH = re.compile(r"(/accounts/password/reset/)[^/\s?\"']+/[^/\s?\"']+/")
TOKEN_QUERY = re.compile(r"([?&](?:card|token|access_token|reset_token)=)[^&\s\"']+", re.IGNORECASE)


class RedactVerificationToken(logging.Filter):
    """Retained class name for configuration compatibility; also protects reset credentials."""

    def filter(self, record):
        message = record.getMessage()
        message = TOKEN_PATH.sub(r"\1[redacted]", message)
        message = RESET_PATH.sub(r"\1[redacted]/[redacted]/", message)
        record.msg = TOKEN_QUERY.sub(r"\1[redacted]", message)
        record.args = ()
        return True
