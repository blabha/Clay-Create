import torch
from pathlib import Path
from PIL import Image

MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "v1-5-pruned-emaonly.safetensors"

# Prepended to every user prompt to force macro texture output
_PREFIX = (
    "seamless macro close-up photograph of a surface texture, "
    "flat overhead view, high contrast relief pattern, "
    "sharp focus, fine detail, "
)

_NEGATIVE = (
    "landscape, sky, horizon, wide angle, depth of field, bokeh, blur, "
    "people, faces, text, watermark, logo, signature, "
    "3D render, CGI, painting, illustration, cartoon, "
    "smooth gradient, flat, featureless, low contrast, washed out"
)


class SDGenerator:
    def __init__(self):
        self._pipe = None

    def _load(self):
        if self._pipe is not None:
            return
        from diffusers import StableDiffusionPipeline

        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model not found at {MODEL_PATH}. "
                "Copy v1-5-pruned-emaonly.safetensors into the models/ folder."
            )

        print(f"Loading SD model from {MODEL_PATH} …")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        self._pipe = StableDiffusionPipeline.from_single_file(
            str(MODEL_PATH),
            torch_dtype=dtype,
            use_safetensors=True,
        ).to(device)

        if device == "cpu":
            self._pipe.enable_attention_slicing()

        print(f"SD model loaded on {device}.")

    def generate(self, prompt: str, steps: int = 25) -> Image.Image:
        self._load()
        full_prompt = _PREFIX + prompt
        with torch.inference_mode():
            result = self._pipe(
                prompt=full_prompt,
                negative_prompt=_NEGATIVE,
                num_inference_steps=steps,
                guidance_scale=8.5,     # higher CFG = crisper pattern adherence
                height=512,
                width=512,
            )
        return result.images[0]
