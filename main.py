from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.all import *
import os
import math
from PIL import Image, ImageDraw, ImageFont


@register("custom_menu", "YourName", "自定义底图、字体与排版的菜单插件", "1.1.0")
class CustomMenu(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config

        # 确定资源目录路径
        self.res_dir = os.path.join(os.path.dirname(__file__), "resources")
        if not os.path.exists(self.res_dir):
            os.makedirs(self.res_dir)

    def _load_font(self, size):
        """
        加载配置指定的字体文件。
        如果指定文件不存在，尝试加载默认名 'font.ttf'。
        """
        config_font_name = self.config.get("font_filename", "font.ttf")
        font_path = os.path.join(self.res_dir, config_font_name)

        # 1. 尝试加载配置的字体
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                self.context.logger.error(f"字体加载失败: {e}")

        # 2. 如果失败，尝试加载默认 font.ttf
        fallback_path = os.path.join(self.res_dir, "font.ttf")
        if os.path.exists(fallback_path):
            return ImageFont.truetype(fallback_path, size)

        # 3. 如果还没有，使用系统默认（可能不支持中文）
        return ImageFont.load_default()

    def _process_background(self, target_width, target_height):
        """
        读取并裁剪底图，使其填满目标分辨率
        """
        bg_name = self.config.get("background_filename", "bg.jpg")
        bg_path = os.path.join(self.res_dir, bg_name)

        # 如果没有图，返回纯灰色背景
        if not os.path.exists(bg_path):
            return Image.new('RGBA', (target_width, target_height), color=(50, 50, 50, 255))

        try:
            img = Image.open(bg_path).convert('RGBA')
        except:
            return Image.new('RGBA', (target_width, target_height), color=(50, 50, 50, 255))

        img_w, img_h = img.size
        target_ratio = target_width / target_height
        img_ratio = img_w / img_h

        # 居中裁剪算法 (Center Crop)
        if img_ratio > target_ratio:
            # 图片比目标更宽：以高为基准，裁掉两边
            new_height = target_height
            new_width = int(img_h * target_ratio)  # 实际上这里应该是基于比例缩放
            # 正确逻辑：先resize再crop或者先计算crop区域

            # 更稳妥的方式：先按短边缩放
            scale = target_height / img_h
            resized_w = int(img_w * scale)
            resized_h = target_height  # exactly target_height
            img = img.resize((resized_w, resized_h), Image.Resampling.LANCZOS)

            # 裁剪中间
            offset = (resized_w - target_width) // 2
            img = img.crop((offset, 0, offset + target_width, target_height))

        else:
            # 图片比目标更高（或相等）：以宽为基准，裁掉上下
            scale = target_width / img_w
            resized_w = target_width  # exactly target_width
            resized_h = int(img_h * scale)
            img = img.resize((resized_w, resized_h), Image.Resampling.LANCZOS)

            # 裁剪中间
            offset = (resized_h - target_height) // 2
            img = img.crop((0, offset, target_width, offset + target_height))

        return img

    def _draw_menu(self):
        """
        绘制菜单主逻辑
        """
        # --- 1. 初始化配置参数 ---
        title_text = self.config.get("menu_title", "功能菜单")
        items = self.config.get("menu_items", {})
        layout_mode = self.config.get("layout_mode", "vertical")

        # 定义分辨率
        if layout_mode == "horizontal":
            W, H = 1920, 1080
            # 横屏每行多放几个
            cols = 4 if len(items) > 6 else 3
        else:
            W, H = 1080, 1920
            # 竖屏默认双列
            cols = 2

        # --- 2. 准备底图 ---
        image = self._process_background(W, H)

        # --- 3. 绘制标题 ---
        # 创建一个临时的 draw 对象用于计算文字大小
        draw_temp = ImageDraw.Draw(image)

        # 标题字体大小自适应（宽度 8%）
        title_size = int(W * 0.08)
        font_title = self._load_font(title_size)

        # 获取文字宽高 (left, top, right, bottom)
        bbox = draw_temp.textbbox((0, 0), title_text, font=font_title)
        title_w = bbox[2] - bbox[0]
        title_h = bbox[3] - bbox[1]

        title_x = (W - title_w) / 2
        title_y = int(H * 0.08)  # 距离顶部 8% 的位置

        # 绘制标题阴影
        draw_temp.text((title_x + 4, title_y + 4), title_text, font=font_title, fill=(0, 0, 0, 120))
        # 绘制标题正文
        draw_temp.text((title_x, title_y), title_text, font=font_title, fill=(255, 255, 255, 255))

        # --- 4. 绘制菜单网格 ---
        # 布局参数
        margin_x = 60
        start_y = title_y + title_h + 80  # 标题下方起始位置
        gap = 35  # 卡片间距

        # 计算卡片尺寸
        # W = 2*margin + cols*card_w + (cols-1)*gap
        card_w = (W - (2 * margin_x) - ((cols - 1) * gap)) / cols
        card_h = 160  # 固定高度

        # 字体准备
        font_trigger = self._load_font(45)  # 触发词大小
        font_desc = self._load_font(26)  # 简介大小

        # 创建半透明图层 (用于画圆角白底)
        overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)

        item_list = list(items.items())  # [("key", "value"), ...]

        for i, (trigger, desc) in enumerate(item_list):
            row = i // cols
            col = i % cols

            x = margin_x + col * (card_w + gap)
            y = start_y + row * (card_h + gap)

            # 4.1 绘制半透明白色背景 (圆角矩形)
            rect = [x, y, x + card_w, y + card_h]
            # fill=(255, 255, 255, 220) -> 白色, 不透明度 220/255
            draw_overlay.rounded_rectangle(rect, radius=20, fill=(255, 255, 255, 220))

            # 4.2 绘制文字 (需要画在合并后的图上，或者直接在 overlay 画不透明色)
            # 这里我们在 overlay 上直接画文字

            # 触发词
            t_text = f"➤ {trigger}"
            draw_overlay.text((x + 20, y + 25), t_text, font=font_trigger, fill=(40, 40, 40, 255))

            # 简介 (做简单的截断防止溢出)
            # 估算一行能容纳的字数
            max_char = int((card_w - 40) / 26)
            if len(desc) > max_char:
                desc = desc[:max_char - 1] + "…"

            draw_overlay.text((x + 25, y + 95), desc, font=font_desc, fill=(100, 100, 100, 255))

        # --- 5. 合并图层 ---
        final_image = Image.alpha_composite(image, overlay)
        return final_image

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def menu(self, event: AstrMessageEvent):
        # 获取配置的触发词
        trigger_cmd = self.config.get("menu_trigger", "菜单")

        if event.message_str == trigger_cmd:
            try:
                # 生成图片
                img = self._draw_menu()

                # 保存临时文件
                save_path = os.path.join(self.res_dir, "temp_menu_render.png")
                img.save(save_path)

                # 发送
                yield event.image(save_path)

            except Exception as e:
                yield event.plain(f"菜单生成失败: {e}")
                self.context.logger.error(f"菜单生成错误: {e}")