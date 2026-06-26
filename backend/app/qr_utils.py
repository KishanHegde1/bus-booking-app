import uuid
import io
import base64

import qrcode


def generate_secure_token() -> str:
    """
    Generate a unique QR token for each booking.
    Example:
    2d8b8c8a1d9c4d61b8bb0ef7d0c0d9d2
    """
    return uuid.uuid4().hex


def generate_qr_image(token: str) -> str:
    """
    Generate QR image and return it as a Base64 string.
    Flutter can display this directly if needed.
    """

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )

    qr.add_data(token)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def verify_token(token: str) -> bool:
    """
    Basic validation.
    More verification will happen using the database.
    """
    return bool(token and len(token) == 32)