""" This module contains bespoke code for using HitSave with pytorch objects. """

import torch
from torch.utils.tensorboard.writer import SummaryWriter
from hitsave.deep import register_opaque

register_opaque(SummaryWriter)
