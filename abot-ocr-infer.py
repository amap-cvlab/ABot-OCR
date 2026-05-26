import os
import json
from pathlib import Path
from vllm import LLM, SamplingParams
from PIL import Image
from transformers import AutoProcessor

def generate_prompt(image_path):
    PROMPT = '''You are an AI assistant specialized in converting PDF images to Markdown format. Please follow these instructions for the conversion:

            1. Text Processing:
            - Accurately recognize all text content in the PDF image without guessing or inferring.
            - Convert the recognized text into Markdown format.
            - Maintain the original document structure, including headings, paragraphs, lists, etc.

            2. Mathematical Formula Processing:
            - Convert all mathematical formulas to LaTeX format.
            - Enclose inline formulas with,(,). For example: This is an inline formula,( E = mc^2,)
            - Enclose block formulas with,\[,\]. For example:,[,frac{-b,pm,sqrt{b^2 - 4ac}}{2a},]

            3. Table Processing:
            - Convert tables to HTML format.
            - Wrap the entire table with <table> and </table>.

            4. Figure Handling:
            - Ignore figures content in the PDF image. Do not attempt to describe or convert images.

            5. Output Format:
            - Ensure the output Markdown document has a clear structure with appropriate line breaks between elements.
            - For complex layouts, try to maintain the original document's structure and format as closely as possible.

            Please strictly follow these guidelines to ensure accuracy and consistency in the conversion. Your task is to accurately convert the content of the PDF image into Markdown format without adding any extra explanations or comments.
            '''
    user_conversation = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_path},
                    {"type": "text", "text": PROMPT},
                ],
            },
        ]
    return user_conversation


MODEL_PATH = str(Path(__file__).resolve().parent / "abot-ocr")

TOKENIZER_PATH: str | None = None

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def append_failed_image_log(image_path: Path, reason: str, log_file: str = "failed_images.log") -> None:
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{image_path}\t{reason}\n")


def post_process_text(text: str) -> str:
    n = len(text)
    if n < 8000:
        return text
    for length in range(2, n // 10 + 1):
        candidate = text[-length:]
        count = 0
        i = n - length
        while i >= 0 and text[i:i + length] == candidate:
            count += 1
            i -= length
        if count >= 10:
            return text[:n - length * (count - 1)]
    return text


def resolve_markdown_path(
    image_path: Path,
    output_dir: Path | None = None,
    input_root: Path | None = None,
) -> Path:
    """
    计算 Markdown 输出路径。

    - 未指定 output_dir：与图片同目录，仅替换后缀为 .md。
    - 指定 output_dir：
      - 若提供 input_root（目录输入场景），保留相对 input_root 的子目录结构；
      - 否则直接输出到 output_dir 下。
    """
    if output_dir is None:
        return image_path.parent / (image_path.stem + ".md")
    if input_root is None:
        return output_dir / (image_path.stem + ".md")
    relative_parent = image_path.relative_to(input_root).parent
    return output_dir / relative_parent / (image_path.stem + ".md")


def load_model(model_path: str = MODEL_PATH, tokenizer_path: str | None = TOKENIZER_PATH):
    """初始化 vLLM 引擎和处理器，返回 (llm, processor, sampling_params)。"""
    tok = tokenizer_path or model_path
    llm = LLM(model=model_path, tokenizer=tok, trust_remote_code=False)
    processor = AutoProcessor.from_pretrained(tok)
    sampling_params = SamplingParams(temperature=0, max_tokens=8192)
    return llm, processor, sampling_params


def collect_pending_images(
    image_files: list[Path],
    output_dir: Path | None = None,
    input_root: Path | None = None,
) -> list[Path]:
    """过滤掉已存在对应 Markdown 的图片，返回待处理列表。"""
    pending = [
        f for f in image_files
        if not resolve_markdown_path(f, output_dir, input_root).exists()
    ]
    skipped = len(image_files) - len(pending)
    if skipped > 0:
        print(f"[~] 跳过已完成 {skipped} 张，待处理 {len(pending)} 张")
    return pending


def batch_infer(
    image_files: list[Path], llm, processor, sampling_params
) -> list[tuple[Path, str]]:
    """
    批量推理：一次性将所有图片送入 vLLM，充分利用连续批处理加速。

    Returns:
        (图片路径, 文本结果) 列表，仅包含成功读取并推理的图片。
    """
    inputs = []
    valid_image_files: list[Path] = []
    for image_file in image_files:
        try:
            # verify() 先做完整性校验，随后重新 open 才可正常读取像素
            with Image.open(image_file) as probe:
                probe.verify()
            img = Image.open(image_file).convert("RGB")
        except Exception as e:
            reason = f"{type(e).__name__}: {e}"
            print(f"[跳过] 坏图或不可读: {image_file} ({reason})")
            append_failed_image_log(image_file, reason)
            continue
        messages = generate_prompt(str(image_file))
        prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs.append({"prompt": prompt, "multi_modal_data": {"image": [img]}})
        valid_image_files.append(image_file)

    if not inputs:
        return []

    outputs = llm.generate(inputs, sampling_params)
    texts = [post_process_text(output.outputs[0].text) for output in outputs]
    return list(zip(valid_image_files, texts))


def save_markdown(
    image_path: Path,
    text: str,
    output_dir: Path | None = None,
    input_root: Path | None = None,
) -> str:
    """将推理结果写入 Markdown 文件，返回文件路径。"""
    markdown_file = resolve_markdown_path(image_path, output_dir, input_root)
    markdown_file.parent.mkdir(parents=True, exist_ok=True)
    with open(markdown_file, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[OK] {image_path.name} -> {markdown_file}")
    return str(markdown_file)


def run_infer(
    input_path: str,
    llm,
    processor,
    sampling_params,
    batch_size: int = 0,
    output_dir: str | None = None,
) -> list[str]:
    """
    对单张图片或目录（含多级子目录）批量执行 OCR。
    Markdown 文件名与图片一致，后缀为 .md。
    提供 output_dir 时输出到该目录；不提供则默认输出到输入目录。

    Args:
        input_path: 单张图片路径，或包含图片的目录路径（支持多级子目录）。
        llm: 已初始化的 vLLM 引擎。
        processor: 已加载的处理器。
        sampling_params: 采样参数。
        batch_size: 每批推理的图片数量，0 表示全部一次性推理（显存充足时最快）。
        output_dir: 指定 Markdown 输出目录；不传时默认输出到输入图片所在目录。

    Returns:
        所有生成的 Markdown 文件路径列表。
    """
    input_path = Path(input_path)
    output_dir_path = Path(output_dir) if output_dir else None

    if input_path.is_file():
        if input_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: {input_path.suffix}")
        image_files = [input_path]
        input_root = None
    elif input_path.is_dir():
        # rglob 递归遍历多级子目录
        image_files = sorted([
            f for f in input_path.rglob("*")
            if f.is_file() and f.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        ])
        if not image_files:
            print(f"[!] 目录中未找到支持的图片文件: {input_path}")
            return []
        input_root = input_path
    else:
        raise FileNotFoundError(f"路径不存在: {input_path}")

    print(f"[*] 共找到 {len(image_files)} 张图片")
    pending_files = collect_pending_images(image_files, output_dir_path, input_root)
    if not pending_files:
        print("[完成] 所有图片均已处理，无需重新推理。")
        return [
            str(resolve_markdown_path(f, output_dir_path, input_root))
            for f in image_files
        ]

    # 按 batch_size 分批推理；batch_size=0 时一次性全量推理
    chunk_size = batch_size if batch_size > 0 else len(pending_files)
    output_files = []
    for start in range(0, len(pending_files), chunk_size):
        chunk = pending_files[start:start + chunk_size]
        print(f"[*] 推理第 {start + 1}~{start + len(chunk)} 张...")
        pairs = batch_infer(chunk, llm, processor, sampling_params)
        for image_file, text in pairs:
            output_files.append(
                save_markdown(image_file, text, output_dir_path, input_root)
            )

    # 已跳过的文件也加入返回列表
    skipped_files = [
        str(resolve_markdown_path(f, output_dir_path, input_root))
        for f in image_files if f not in pending_files
    ]
    all_output_files = skipped_files + output_files
    print(f"\n[完成] 新生成 {len(output_files)} 个，共 {len(all_output_files)} 个 Markdown 文件。")
    return all_output_files


# ── 调用示例 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    llm, processor, sampling_params = load_model()

    run_infer(
        input_path="images",
        llm=llm,
        processor=processor,
        sampling_params=sampling_params,
        batch_size=8,
        output_dir="./abot-ocr-infer-output"
    )
