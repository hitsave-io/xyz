"""
Inference using detectron2
==========================

In this example, we use detectron2 to create detections on the `MS COCO <https://cocodataset.org>`_ dataset.


First, `install detectron2 <https://detectron2.readthedocs.io/en/latest/tutorials/install.html>`_.

::
        pip install plotly pandas

        # set up the data
        cd ~/data
        curl -O http://images.cocodataset.org/zips/val2017.zip


"""

#%%
# Some basic setup:
# Setup detectron2 logger
from io import BytesIO
from itertools import islice
from pathlib import Path
import pandas as pd

# import some common libraries
import numpy as np
import os

# import some common detectron2 utilities
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2.data import MetadataCatalog
from detectron2 import model_zoo
import torch
from PIL import Image
import base64
import plotly.express as px
import plotly.graph_objects as go

from hitsave import experiment


def create_fig(im):
    with BytesIO() as stream:
        im.save(stream, format="png")
        prefix = "data:image/png;base64,"
        base64_string = prefix + base64.b64encode(stream.getvalue()).decode("utf-8")
    fig = go.Figure(go.Image(source=base64_string))
    fig.update_xaxes(showticklabels=False)
    fig.update_yaxes(showticklabels=False)
    return fig


thing_classes = MetadataCatalog.get("coco_2017_val").thing_classes
cfg = get_cfg()
# add project-specific config (e.g., TensorMask) here if you're not running a model in detectron2's core library
cfg.merge_from_file(
    model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml")
)
if not torch.cuda.is_available():
    cfg.MODEL.DEVICE = "cpu"
cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5  # set threshold for this model
# Find a model from detectron2's model zoo. You can use the https://dl.fbaipublicfiles... url as well
cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url(
    "COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"
)
predictor = DefaultPredictor(cfg)
predictor.model = predictor.model.to("cpu")


@experiment
def semseg(im: Image.Image):
    outputs = predictor(np.array(im)[:, :, ::-1])
    return outputs


def add_bbox(fig: go.Figure, instances):
    def mk():
        for i in range(len(instances)):
            instance = instances[i]
            bbox = np.array(instance.pred_boxes.tensor[0])
            xs = bbox[[0, 2, 2, 0, 0]]
            ys = bbox[[1, 1, 3, 3, 1]]
            for x, y in zip(xs, ys):
                yield dict(
                    id=i,
                    x=x,
                    y=y,
                    score=instance.scores.item(),
                    category=thing_classes[instance.pred_classes.item()],
                )

    df = pd.DataFrame(mk())
    fig2 = px.line(
        df,
        x="x",
        y="y",
        line_group="id",
        hover_data=["score", "category"],
        color="category",
    )
    fig = go.Figure(data=fig.data + fig2.data, layout=fig.layout)  # type: ignore
    fig.update_layout(showlegend=False)
    return fig


coco_path = (
    Path(os.environ.get("DETECTRON2_DATASETS", "~/data")).expanduser()
    / "coco"
    / "val2017"
)


@experiment
def show_detection(im):

    result = semseg(im)
    fig = add_bbox(create_fig(im), result["instances"])

    return fig


for p in islice(coco_path.iterdir(), 10):
    im = Image.open(p)
    fig = show_detection(im)
