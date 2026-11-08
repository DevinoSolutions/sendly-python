"""Uploads resource."""

from __future__ import annotations

import mimetypes
import os
from typing import TYPE_CHECKING

#: The four image types the API accepts, by extension. Checked before
#: ``mimetypes`` because that module reads the OS registry on Windows (which maps
#: ``.png`` to ``image/x-png``, a type the server refuses) and older Pythons do
#: not know ``.webp``.
_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


if TYPE_CHECKING:
    from sendly.client import Sendly
    from sendly.types import ImageUpload


class UploadsResource:
    """Host files for use in emails.

    Needs the ``templates:write`` scope. A deployment without S3 storage answers
    503 ``S3_DISABLED``.
    """

    def __init__(self, client: Sendly) -> None:
        self._client = client

    def image(self, data: bytes, *, filename: str, content_type: str | None = None) -> ImageUpload:
        """Host an image (JPEG, PNG, GIF or WebP) and answer its URL.

        ``data`` is the file's bytes and ``content_type`` its MIME type. When
        ``content_type`` is omitted it is chosen from the ``filename`` extension (``.jpg``, ``.jpeg``,
        ``.png``, ``.gif``, ``.webp``, case-insensitive, then ``mimetypes``);
        if it cannot be guessed, :class:`ValueError` is raised rather than sending
        a type the API would refuse. The API checks both the type and the file's
        leading bytes, so a mislabelled file is refused with 400.
        The server's limit is 10 MB (``MAX_IMAGE_UPLOAD_BYTES``); a larger file
        raises :class:`~sendly.errors.SendlyError` with status 413 and code
        ``PAYLOAD_TOO_LARGE``. Sent as ``multipart/form-data`` under the field
        ``image``. Returns ``{url, key, filename, contentType, size}``; ``url`` is
        what goes in an email's HTML.
        """
        if content_type is None:
            content_type = _IMAGE_TYPES.get(os.path.splitext(filename)[1].lower())
        if content_type is None:
            content_type, _encoding = mimetypes.guess_type(filename)
        if content_type is None:
            raise ValueError(
                f"Sendly: cannot guess the image type of {filename!r}; pass `content_type` "
                "(image/jpeg, image/png, image/gif or image/webp)."
            )
        envelope = self._client.request(
            method="POST",
            path="/api/uploads/image",
            files={"image": (filename, data, content_type)},
        )
        uploaded: ImageUpload = self._client.unwrap(envelope)
        return uploaded
