import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

# MiDaS_small expects 256×256 input, normalised with ImageNet stats
_NET_SIZE = 256
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def _preprocess(img_rgb: np.ndarray) -> torch.Tensor:
    img = cv2.resize(img_rgb, (_NET_SIZE, _NET_SIZE), interpolation=cv2.INTER_CUBIC)
    img = img.astype(np.float32) / 255.0
    img = (img - _MEAN) / _STD
    img = img.transpose(2, 0, 1)          # HWC → CHW
    return torch.from_numpy(img).unsqueeze(0)   # (1, 3, H, W)


class MiDaSProcessor:
    def __init__(self):
        self._model = None
        self._device = None

    def _load(self):
        if self._model is not None:
            return
        print("Loading MiDaS model …")
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model = torch.hub.load(
            "intel-isl/MiDaS", "MiDaS_small", trust_repo=True
        )
        self._model.to(self._device).eval()
        print(f"MiDaS loaded on {self._device}.")

    def process(self, image: Image.Image, out_h: int = 512, out_w: int = 512) -> np.ndarray:
        """Return a float32 [0, 1] grayscale heightmap at out_h × out_w."""
        self._load()
        img_rgb = np.array(image.convert("RGB"))
        batch = _preprocess(img_rgb).to(self._device)

        with torch.no_grad():
            pred = self._model(batch)
            pred = F.interpolate(
                pred.unsqueeze(1),
                size=(out_h, out_w),
                mode="bicubic",
                align_corners=False,
            ).squeeze()

        depth = pred.cpu().numpy().astype(np.float32)
        lo, hi = depth.min(), depth.max()
        return (depth - lo) / (hi - lo + 1e-6)
