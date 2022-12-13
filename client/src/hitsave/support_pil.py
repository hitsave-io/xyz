""" HitSave bindings for the PIL.Image type """
import logging
from hitsave.visualize import visualize
import hitsave.visualize as vis
from hitsave.blobstore import BlobStore
import tempfile
from PIL.Image import Image


@visualize.register(Image)
def _viz_pil_image(x: Image, rec):
    blobstore = BlobStore.current()

    with tempfile.SpooledTemporaryFile() as tape:
        x.save(tape, format="JPEG")
        tape.seek(0)
        info = blobstore.add_blob(tape, label="visualisation image")
        blobstore.push_blob(info.digest)

    return {
        **vis.init(x),
        "__kind__": vis.Kind.image.name,
        "digest": info.digest,
        "content_length": info.content_length,
        "mime_type": "image/jpeg",
    }


logging.getLogger("hitsave").debug("Loaded PIL support")
