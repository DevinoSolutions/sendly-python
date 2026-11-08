"""Uploads resource."""

from __future__ import annotations

import mimetypes
from typing import TYPE_CHECKING

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
        ``content_type`` is omitted it is guessed from the ``filename`` extension;
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
