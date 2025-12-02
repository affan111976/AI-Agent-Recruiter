import os
from exceptions import ValidationException

ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx'}
MAX_FILE_SIZE_MB = 5

def validate_resume_file(filename: str, file_size: int):
    """
    Validates file extension and size.
    """
    # Check extension
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise ValidationException(
            f"Invalid file format: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check size (convert MB to bytes)
    if file_size > (MAX_FILE_SIZE_MB * 1024 * 1024):
        raise ValidationException(
            f"File too large. Max size is {MAX_FILE_SIZE_MB}MB."
        )

def validate_phone_number(phone: str):
    """
    Basic phone number validation.
    """
    if phone and not phone.replace('+', '').isdigit():
         raise ValidationException("Phone number must contain only digits and optional +")