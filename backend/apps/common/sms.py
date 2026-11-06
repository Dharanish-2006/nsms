"""Send a text message to an Indian mobile number given as 10 digits.

SMS_BACKEND:
  console  log the message (default; development)
  sns      AWS SNS transactional SMS. Needs boto3, IAM permission sns:Publish and,
           for India, a registered DLT sender ID / template (SNS console).
  locmem   keep messages in `outbox` (tests)
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

outbox = []  # used by the locmem backend


def send_sms(digits, text):
    backend = settings.SMS_BACKEND
    if backend == "sns":
        import boto3

        boto3.client("sns", region_name=settings.AWS_REGION).publish(
            PhoneNumber=f"+91{digits}",
            Message=text,
            MessageAttributes={
                "AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"}
            },
        )
    elif backend == "locmem":
        outbox.append((digits, text))
    else:
        logger.info("SMS to +91%s: %s", digits, text)
