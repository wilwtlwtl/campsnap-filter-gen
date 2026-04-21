"""
.flt ファイルの読み書きモジュール
"""

import configparser
import io
from pathlib import Path
from .analyzer import FltParams


def save_flt(params: FltParams, path: str | Path) -> None:
    """FltParams を .flt ファイルとして保存する"""
    path = Path(path)
    content = _build_flt_text(params)
    path.write_text(content, encoding="utf-8")


def to_flt_bytes(params: FltParams) -> bytes:
    """.flt のバイト列を返す（Streamlit ダウンロード用）"""
    return _build_flt_text(params).encode("utf-8")


def load_flt(source) -> FltParams:
    """
    .flt ファイルを読み込んで FltParams を返す。
    source: ファイルパス (str/Path) または bytes または file-like object
    """
    if isinstance(source, (str, Path)):
        text = Path(source).read_text(encoding="utf-8")
    elif isinstance(source, bytes):
        text = source.decode("utf-8")
    else:
        text = source.read().decode("utf-8")

    return _parse_flt_text(text)


def _build_flt_text(params: FltParams) -> str:
    lines = [
        "[Filter]",
        f"Brightness={params.brightness}",
        f"Contrast={params.contrast}",
        f"Saturation={params.saturation}",
        f"Hue={params.hue}",
        f"GammaR={params.gamma_r}",
        f"GammaG={params.gamma_g}",
        f"GammaB={params.gamma_b}",
    ]
    return "\n".join(lines) + "\n"


def _parse_flt_text(text: str) -> FltParams:
    cp = configparser.ConfigParser()
    cp.read_string(text)
    sec = cp["Filter"]

    def f(key, default=1.0):
        return float(sec.get(key, default))

    return FltParams(
        brightness=f("Brightness"),
        contrast=f("Contrast"),
        saturation=f("Saturation"),
        hue=int(sec.get("Hue", 0)),
        gamma_r=f("GammaR"),
        gamma_g=f("GammaG"),
        gamma_b=f("GammaB"),
    )
