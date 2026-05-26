<div align="center">

<img src="./assets/logo.png" alt="ABot-OCR" width="720">

<br>

**将文档页面图像高精度转换为结构化 Markdown**

<br>

[![Technical Report](https://img.shields.io/badge/Technical%20Report-PDF-B31B1B)](./report/ABot_OCR_Technical_Report.pdf)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![HuggingFace](https://img.shields.io/badge/🤗%20HuggingFace-acvlab%2FABot--OCR-yellow)](https://huggingface.co/acvlab/ABot-OCR)
[![vLLM](https://img.shields.io/badge/Inference-vLLM-00A3FF)](#-推理用法)

[English](./README.md)

</div>

---

## 📖 模型简介

ABot-OCR 是一款面向文档图像的 OCR 模型，可将 PDF / 文档页面图片转换为结构化 **Markdown** 输出，支持文本、数学公式（LaTeX）与表格（HTML）等元素的识别与还原。

<!-- TODO: 在此补充 1～2 段更详细的模型背景、训练数据、适用场景等 -->

---

## 🏆 评测结果

<!-- TODO: 补充 benchmark 名称、评测设置、对比说明等 -->
下图是在 [OmniDocBench v1.5](https://github.com/opendatalab/OmniDocBench/tree/main) 数据集上的overall评估结果对比。

<div align="center">

<img src="./assets/metric.png" alt="ABot-OCR Benchmark Results" width="860">

<br>
<sub><!-- TODO: 图注，例如：OmniDocBench Overall 指标对比 --></sub>

</div>

<!-- TODO: 可选 — 补充更多分场景 / 分语言指标表格
| Benchmark | 指标 | ABot-OCR | 备注 |
| :--- | :---: | :---: | :--- |
| TODO | TODO | TODO | |
-->

---

## 📦 模型下载

模型权重体积较大，未直接包含在本仓库中。请从 HuggingFace 下载后，放置到本地目录：

| 模型 | 平台 | 链接 |
| :--- | :---: | :--- |
| **ABot-OCR** | 🤗 HuggingFace | [`acvlab/ABot-OCR`](https://huggingface.co/acvlab/ABot-OCR) |


```text
repo/
└── abot-ocr/          # 将下载的模型权重解压/放置于此
    ├── config.json
    ├── model.safetensors
    └── ...
```

---

## 🚀 快速开始

### 环境依赖

建议使用 **Python 3.11+**，并安装以下依赖：

```bash
pip install vllm==0.18.0 transformers==5.5.4 torch==2.10.0
```

> **说明：** 推理基于 vLLM 加载模型，需具备足够 GPU 显存（模型约 4GB 权重，实际占用与 `batch_size` 及图片分辨率相关）。

### 运行推理

1. 下载模型权重至 `./abot-ocr/`
2. 准备待识别的图片（单张或目录均可）
3. 运行推理脚本：

```bash
python abot-ocr-infer.py
```

默认会在 `images/` 目录读取图片，并将 Markdown 结果输出到 `./abot-ocr-infer-output/`。

---

## 💻 推理用法

推理脚本：[`abot-ocr-infer.py`](./abot-ocr-infer.py)

### 配置模型路径

脚本默认从同级目录加载模型，如需修改：

```python
MODEL_PATH = str(Path(__file__).resolve().parent / "abot-ocr")
```

### 自定义输入输出

编辑 `abot-ocr-infer.py` 底部 `__main__` 中的参数：

```python
run_infer(
    input_path="images",                  # 单张图片或目录（支持多级子目录）
    llm=llm,
    processor=processor,
    sampling_params=sampling_params,
    batch_size=8,                         # 每批图片数；0 表示一次性推理全部
    output_dir="./abot-ocr-infer-output"  # 不传则 .md 与图片同目录
)
```

### 输入与输出说明

| 行为 | 说明 |
| :--- | :--- |
| 默认输出 | 每张图片生成同名 `.md` 文件 |
| 指定 `output_dir` | 输出到指定目录，并保留相对子目录结构 |
| 断点续跑 | 已存在对应 `.md` 的图片会自动跳过 |
| 失败记录 | 无法读取的图片写入 `failed_images.log` |


---

## 📄 引用

<!-- TODO: 填写作者与正式引用信息 -->

```bibtex
@misc{abot-ocr,
  title  = {ABot-OCR},
  author = {AMAP CV Lab},
  year   = {2026},
}
```

---

## 🙏 致谢

我们的工作受启发于很多优秀开源项目，衷心感谢以下优秀开源项目的开发者，包括 [Qwen-VL](https://github.com/QwenLM/Qwen-VL)、[PaddleOCR-VL](https://github.com/PaddlePaddle/PaddleOCR)、[MinerU](https://github.com/opendatalab/MinerU) 以及其他相关的 OCR 社区。
