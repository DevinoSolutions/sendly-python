"""Uploads resource."""

from __future__ import annotations

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

    def image(
        self, data: bytes, *, filename: str, content_type: str = "application/octet-stream"
    ) -> ImageUpload:
        """Host an image (JPEG, PNG, GIF or WebP) and answer its URL.

        ``data`` is the file's bytes and ``content_type`` its MIME type; the API
        checks both the type and the file's leading bytes, so a mislabelled file
        is refused with 400. Sent as ``multipart/form-data`` under the field
        ``image``. Returns ``{url, key, filename, contentType, size}``; ``url`` is
        what goes in an email's HTML.
        """
        envelope = self._client.request(
            method="POST",
            path="/api/uploads/image",
            files={"image": (filename, data, content_type)},
        )
        uploaded: ImageUpload = self._client.unwrap(envelope)
        return uploaded
