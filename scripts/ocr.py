#!/usr/bin/env python3
"""截图 OCR —— 统一接口，平台检测，可扩展后端。

- macOS：使用系统 Vision 框架（无需额外安装，通过 swift 子进程调用）
- 其他平台：使用 Tesseract（需 `tesseract` 可执行文件 + 中文语言包）

统一接口 `ocr_image(path, backend="auto") -> str`。
新增后端只需实现一个 `_ocr_xxx(path) -> str` 并在 OCR_BACKENDS 注册。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

# Swift 源码：用 macOS Vision 框架做中文 OCR
_VISION_SWIFT = r"""
import Foundation
import Vision
import AppKit

let path = CommandLine.arguments[1]
guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("无法读取图片\n".data(using: .utf8)!)
    exit(1)
}
let req = VNRecognizeTextRequest { r, _ in
    guard let obs = r.results as? [VNRecognizedTextObservation] else { return }
    for o in obs {
        if let top = o.topCandidates(1).first {
            print(top.string)
        }
    }
}
req.recognitionLevel = .accurate
req.recognitionLanguages = ["zh-Hans", "en-US"]
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
try? handler.perform([req])
"""


def _ocr_darwin_vision(path: str) -> str:
    if shutil.which("swift") is None:
        raise RuntimeError("未找到 swift（macOS Vision OCR 需要 Xcode Command Line Tools）")
    fd, sp = tempfile.mkstemp(suffix=".swift", prefix="wxocr_")
    with os.fdopen(fd, "w") as f:
        f.write(_VISION_SWIFT)
    try:
        proc = subprocess.run(
            ["swift", sp, path], capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Vision OCR 失败: {proc.stderr[:200]}")
        return proc.stdout.strip()
    finally:
        try:
            os.unlink(sp)
        except OSError:
            pass


def _ocr_tesseract(path: str) -> str:
    if shutil.which("tesseract") is None:
        raise RuntimeError("未找到 tesseract（请安装：brew install tesseract tesseract-lang）")
    proc = subprocess.run(
        ["tesseract", path, "-", "-l", "chi_sim+eng"],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"tesseract 失败: {proc.stderr[:200]}")
    return proc.stdout.strip()


def default_backend() -> str:
    return "darwin_vision" if sys.platform == "darwin" else "tesseract"


def ocr_image(path: str, backend: str = "auto") -> str:
    """统一 OCR 接口。backend: auto / darwin_vision / tesseract"""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    if backend == "auto":
        backend = default_backend()
    backend = backend.lower()
    if backend in ("darwin_vision", "vision", "darwin"):
        return _ocr_darwin_vision(path)
    if backend in ("tesseract", "tess"):
        return _ocr_tesseract(path)
    raise ValueError(f"未知 OCR 后端: {backend}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="图片 OCR")
    ap.add_argument("image", help="图片路径")
    ap.add_argument("--backend", default="auto")
    args = ap.parse_args()
    print(ocr_image(args.image, args.backend))
