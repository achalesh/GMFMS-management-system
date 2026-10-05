import hashlib
import io
import uuid
import warnings
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject, NameObject


def validate_upload(upload, *, max_bytes, photo=False, crop=(50, 50, 1)):
    raw = upload.read(max_bytes + 1)
    if not raw or len(raw) > max_bytes:
        raise ValidationError("The file is empty or exceeds the configured size limit.")
    suffix = Path(upload.name).suffix.lower()
    allowed = {".jpg", "jpeg", ".jpeg", ".png"} if photo else {".jpg", ".jpeg", ".png", ".pdf"}
    if suffix not in allowed:
        raise ValidationError("Use JPG, JPEG or PNG" + ("." if photo else ", or PDF."))
    if suffix == ".pdf":
        if upload.content_type not in {
            "application/pdf",
            "application/octet-stream",
        } or not raw.startswith(b"%PDF-"):
            raise ValidationError("The file does not match the PDF format.")
        try:
            reader = PdfReader(io.BytesIO(raw), strict=True)
            if reader.is_encrypted:
                raise ValueError("Encrypted PDF")
            if not 1 <= len(reader.pages) <= 30:
                raise ValueError("Page count")
            seen, pending, count = set(), [(reader.trailer, 0)], 0
            banned = {
                "/JS",
                "/JavaScript",
                "/Launch",
                "/OpenAction",
                "/AA",
                "/EmbeddedFiles",
                "/EF",
                "/RichMedia",
                "/XFA",
                "/AcroForm",
            }
            unsafe_values = {
                "/JavaScript",
                "/Launch",
                "/RichMedia",
                "/GoToR",
                "/SubmitForm",
                "/ImportData",
                "/Rendition",
                "/Movie",
                "/Sound",
                "/FileAttachment",
                "/Filespec",
            }
            while pending:
                obj, depth = pending.pop()
                count += 1
                if count > 20000 or depth > 50:
                    raise ValueError("Complex PDF")
                if isinstance(obj, IndirectObject):
                    identity = (obj.idnum, obj.generation)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    obj = obj.get_object()
                if isinstance(obj, DictionaryObject):
                    if banned.intersection(obj.keys()):
                        raise ValueError("Active content")
                    pending.extend((value, depth + 1) for value in obj.values())
                elif isinstance(obj, NameObject) and str(obj) in unsafe_values:
                    raise ValueError("Active content")
                elif isinstance(obj, ArrayObject):
                    pending.extend((value, depth + 1) for value in obj)
        except Exception as exc:
            raise ValidationError(
                "Use an unencrypted PDF of 1–30 pages without scripts, embedded files or interactive forms."
            ) from exc
        result, mime = raw, "application/pdf"
    else:
        expected = "PNG" if suffix == ".png" else "JPEG"
        if upload.content_type not in {
            "image/png" if expected == "PNG" else "image/jpeg",
            "application/octet-stream",
        }:
            raise ValidationError("The image content type is invalid.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.format != expected or image.width * image.height > 20_000_000:
                        raise ValueError("Format or dimensions")
                    image.verify()
                with Image.open(io.BytesIO(raw)) as original:
                    image = ImageOps.exif_transpose(original).convert("RGB")
                    if photo:
                        if min(image.size) < 100:
                            raise ValueError("Small photo")
                        x, y, zoom = crop
                        if not (0 <= x <= 100 and 0 <= y <= 100 and 1 <= zoom <= 3):
                            raise ValueError("Invalid crop")
                        width = min(image.width, image.height * 0.75) / zoom
                        height = width / 0.75
                        left = (image.width - width) * x / 100
                        top = (image.height - height) * y / 100
                        image = image.crop((left, top, left + width, top + height))
                        image.thumbnail((600, 800))
                    else:
                        image.thumbnail((2400, 2400))
                    buffer = io.BytesIO()
                    image.save(buffer, format="JPEG", quality=90)
                    result = buffer.getvalue()
            mime, suffix = "image/jpeg", ".jpg"
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ) as exc:
            raise ValidationError(
                "Use a valid JPG/PNG image of at most 20 megapixels; photographs must be at least 100 pixels on each side."
            ) from exc
    if len(result) > max_bytes:
        raise ValidationError("The processed file exceeds the size limit.")
    return {
        "content": ContentFile(result, name=uuid.uuid4().hex + suffix),
        "content_type": mime,
        "byte_size": len(result),
        "sha256": hashlib.sha256(result).hexdigest(),
    }
