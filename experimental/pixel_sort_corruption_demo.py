import gradio as gr
import gradio.themes
from pixel_sort_corruption import pixel_sort_corruption
from typing import Optional, Dict, Any, Tuple
from PIL import Image as PILImage
import random


def gradio_pixel_sort_corruption(
    input_image: Optional[PILImage.Image],
    edge_guide_image: Optional[PILImage.Image] = None,
    intensity: float = 0.3,
    x_jitter: int = 15,
    sort_method: str = "euclidean",
    seed: int = -1,
    use_edge_guide: bool = False,
    y_span: int = 1,
    block_size: int = 1,
    angle: float = 0,
    quality_scale: float = 1,
) -> Tuple[Optional[PILImage.Image], int]:
    """
    Gradio包装函数，处理图像输入输出

    参数:
        input_image: 输入PIL图像
        edge_guide_image: 边缘引导图像
        intensity: 效果强度
        x_jitter: 水平抖动范围
        sort_method: 相似度计算方法
        seed: 随机种子
        use_edge_guide: 是否使用边缘引导
        y_span: 垂直跨度
        block_size: 块大小
        angle: 角度
        quality_scale: 质量缩放因子

    返回:
        元组: (处理后的PIL图像, 实际使用的种子)
    """
    try:
        if input_image is None:
            raise ValueError("请上传输入图片")

        # 转换PIL图像为RGB模式（确保兼容性）
        if hasattr(input_image, "mode") and input_image.mode != "RGB":
            input_image = input_image.convert("RGB")

        # 处理随机种子
        actual_seed = seed if seed != -1 else random.randint(0, 2**31 - 1)

        # 处理边缘引导图像 - 检查edge_guide_image是否是字典（Gradio隐藏组件的默认值）
        edge_guide: Optional[PILImage.Image] = None
        if (
            use_edge_guide
            and edge_guide_image is not None
            and not isinstance(edge_guide_image, dict)
        ):
            if hasattr(edge_guide_image, "mode") and edge_guide_image.mode != "L":
                edge_guide_image = edge_guide_image.convert("L")
            edge_guide = edge_guide_image

        # 调用处理函数
        result_img: PILImage.Image = pixel_sort_corruption(
            image=input_image,
            edge_guide=edge_guide,
            intensity=intensity,
            x_jitter=x_jitter,
            sort_method=sort_method,
            seed=actual_seed,
            y_span=y_span,
            block_size=block_size,
            angle=angle,
            quality_scale=quality_scale,
        )

        return result_img, actual_seed

    except Exception as e:
        raise gr.Error(str(e)) from e


def update_parameters_based_on_image(
    input_image: Optional[PILImage.Image],
):
    """
    根据上传的图像尺寸更新参数范围

    参数:
        input_image: 上传的PIL图像

    返回:
        包含更新后参数值的字典
    """
    if input_image is None:
        # 如果没有图像，无操作
        return

    # 获取图像尺寸
    width, height = input_image.size

    return [
        gr.update(
            maximum=width,
        ),
        gr.update(
            maximum=height,
        ),
        gr.update(
            maximum=height,
        ),
    ]


def toggle_edge_guide_visibility(use_edge_guide: bool) -> Dict[str, Any]:
    """
    切换边缘引导图可见性

    参数:
        use_edge_guide: 是否使用边缘引导图

    返回:
        更新后的组件属性字典
    """
    return gr.update(visible=use_edge_guide)


def copy_seed_to_input(seed_value: str) -> int:
    """
    将输出种子值复制到输入参数

    参数:
        seed_value: 种子值字符串

    返回:
        种子整数值
    """
    try:
        # 尝试将种子值转换为整数
        if seed_value and seed_value.isdigit():
            return int(seed_value)
        else:
            return -1  # 如果种子值无效，返回-1（随机种子）
    except (ValueError, AttributeError):
        return -1


def create_demo() -> gr.Blocks:
    """
    创建Gradio演示界面

    返回:
        配置好的Gradio Blocks实例
    """
    with gr.Blocks(
        title="高级像素排序损坏效果演示",
        theme=gradio.themes.Soft(),
    ) as demo:
        gr.Markdown(
            """
        # 🎨 高级像素排序损坏效果演示
        
        基于相似度的像素排序损坏效果，支持边缘引导控制和多种相似度计算方法。
        """
        )

        with gr.Row():
            with gr.Column():
                # 输入图像
                input_image: gr.Image = gr.Image(
                    label="输入图片",
                    type="pil",
                    height=300,
                )

                # 边缘引导图控制
                use_edge_guide_checkbox: gr.Checkbox = gr.Checkbox(
                    label="使用边缘引导图",
                    value=False,
                    info="启用后使用边缘引导图确定处理区域",
                )

                edge_guide_image: gr.Image = gr.Image(
                    label="边缘引导图（可选）",
                    type="pil",
                    height=200,
                    visible=False,
                    value=None,
                )

                # 处理按钮
                process_btn: gr.Button = gr.Button(
                    "🚀 应用像素排序效果", variant="primary", size="lg"
                )

                # 参数设置
                with gr.Accordion("参数设置", open=True):
                    intensity: gr.Slider = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        value=0.5,
                        label="效果强度",
                        info="0-1之间，表示要处理的行比例",
                    )

                    x_jitter: gr.Slider = gr.Slider(
                        minimum=0,
                        value=15,
                        step=1,
                        label="水平抖动范围",
                        info="起始点水平抖动的最大像素范围",
                    )

                    sort_method: gr.Dropdown = gr.Dropdown(
                        choices=[
                            "euclidean",
                            "manhattan",
                            "brightness",
                            "dark-to-light",
                            "light-to-dark",
                        ],
                        value="euclidean",
                        label="像素排序方法",
                        info="选择像素排序方式",
                    )

                    seed: gr.Number = gr.Number(
                        value=-1,
                        label="随机种子",
                        info="-1表示使用随机种子，其他数值确保结果可重现",
                        precision=0,
                    )

                    y_span: gr.Slider = gr.Slider(
                        minimum=1,
                        value=1,
                        step=1,
                        label="垂直跨度",
                        info="一旦损坏某行，自动同时损坏下面n-1行",
                    )

                    block_size: gr.Slider = gr.Slider(
                        minimum=1,
                        value=1,
                        step=1,
                        label="块大小",
                        info="一次处理的行数，将多行视为一个块处理",
                    )

                    angle: gr.Slider = gr.Slider(
                        minimum=-180,
                        maximum=180,
                        value=0,
                        label="方向",
                        info="损坏方向",
                    )

                    quality_scale: gr.Slider = gr.Slider(
                        minimum=1,
                        maximum=8,
                        value=1,
                        label="质量缩放因子",
                        info="放大处理后再缩小输出，用于提高效果精度",
                    )

            with gr.Column():
                # 输出图像和种子信息
                output_image: gr.Image = gr.Image(
                    label="处理结果", type="pil", height=400, show_download_button=True
                )
                seed_display = gr.Textbox(
                    label="🎲 本次处理使用的随机种子",
                    value="等待处理...",
                    interactive=False,
                    scale=4,
                )
                copy_seed_btn = gr.Button(
                    "📋 使用此种子",
                    size="sm",
                    scale=1,
                )

        # 事件处理
        # 上传图片时更新参数范围
        input_image.upload(
            fn=update_parameters_based_on_image,
            inputs=input_image,
            outputs=[x_jitter, y_span, block_size],
        )

        # 边缘引导图可见性控制
        use_edge_guide_checkbox.change(
            fn=toggle_edge_guide_visibility,
            inputs=use_edge_guide_checkbox,
            outputs=edge_guide_image,
        )

        # 处理按钮点击事件 - 现在返回两个输出
        process_btn.click(
            fn=gradio_pixel_sort_corruption,
            inputs=[
                input_image,
                edge_guide_image,
                intensity,
                x_jitter,
                sort_method,
                seed,
                use_edge_guide_checkbox,
                y_span,
                block_size,
                angle,
                quality_scale,
            ],
            outputs=[output_image, seed_display],
        )

        # 添加种子复制功能
        copy_seed_btn.click(
            fn=copy_seed_to_input,
            inputs=seed_display,
            outputs=seed,
        )

    return demo


def main() -> None:
    demo: gr.Blocks = create_demo()
    demo.launch(
        server_port=7860,
        share=False,
        show_error=True,
    )


if __name__ == "__main__":
    main()
