from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.all import *
import os
import aiohttp  # 需要安装: pip install aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageColor


@register("custom_menu", "YourName", "自定义底图菜单插件", "1.6.0")
class CustomMenu(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.res_dir = os.path.join(os.path.dirname(__file__), "resources")
        if not os.path.exists(self.res_dir):
            os.makedirs(self.res_dir)

        # 颜色映射表
        self.cn_color_map = {
            "白": "White", "白色": "White",
            "黑": "Black", "黑色": "Black",
            "红": "Red", "红色": "Red",
            "绿": "Green", "绿色": "Green",
            "蓝": "Blue", "蓝色": "Blue",
            "黄": "Yellow", "黄色": "Yellow",
            "青": "Cyan", "青色": "Cyan",
            "紫": "Purple", "紫色": "Purple",
            "粉": "Pink", "粉色": "Pink",
            "橙": "Orange", "橙色": "Orange",
            "灰": "Gray", "灰色": "Gray", "深灰": "DarkGray", "浅灰": "LightGray",
            "棕": "Brown", "棕色": "Brown",
            "透明": "#00000000",
            "半透明白": "#FFFFFFDC",
            "半透明黑": "#00000080",
        }

    # --- 辅助功能：获取图片URL ---
    def _get_image_url(self, event: AstrMessageEvent):
        """尝试从消息或回复中获取图片URL"""
        # 1. 检查当前消息是否包含图片
        for component in event.message_obj.components:
            if isinstance(component, Image) and component.url:
                return component.url

        # 2. 检查是否有回复消息 (Reply)
        if event.message_obj.reply:
            # 不同的适配器回复结构可能不同，尝试遍历 reply 的组件
            if hasattr(event.message_obj.reply, "components"):
                for component in event.message_obj.reply.components:
                    if isinstance(component, Image) and component.url:
                        return component.url

        return None

    # --- 辅助功能：下载图片 ---
    async def _download_image(self, url):
        """异步下载图片"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as resp:
                    if resp.status == 200:
                        return await resp.read()
        except Exception as e:
            self.context.logger.error(f"下载图片失败: {e}")
        return None

    def _load_font(self, size):
        config_font = self.config.get("font_filename", "font.ttf")
        font_path = os.path.join(self.res_dir, config_font)
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except:
                pass
        fallback = os.path.join(self.res_dir, "font.ttf")
        return ImageFont.truetype(fallback, size) if os.path.exists(fallback) else ImageFont.load_default()

    def _parse_smart_color(self, user_input, default_hex):
        if not user_input: user_input = default_hex
        user_input = str(user_input).strip()

        if "," in user_input:
            try:
                clean_str = user_input.lower().replace("rgb", "").replace("a", "").replace("(", "").replace(")", "")
                parts = [int(x.strip()) for x in clean_str.split(",")]
                if 3 <= len(parts) <= 4 and all(0 <= p <= 255 for p in parts):
                    return tuple(parts)
            except:
                pass

        if user_input.startswith("#"):
            try:
                return ImageColor.getrgb(user_input)
            except:
                pass

        if user_input in self.cn_color_map:
            mapped = self.cn_color_map[user_input]
            if mapped.startswith("#"): return ImageColor.getrgb(mapped)
            user_input = mapped

        prefix_map = {"深": "Dark", "浅": "Light", "亮": "Light", "暗": "Dark"}
        for cn_pre, en_pre in prefix_map.items():
            if user_input.startswith(cn_pre):
                suffix = user_input[len(cn_pre):]
                if suffix in self.cn_color_map:
                    user_input = en_pre + self.cn_color_map[suffix]
                    break

        try:
            return ImageColor.getrgb(user_input)
        except:
            return ImageColor.getrgb(default_hex)

    def _process_background(self, w, h):
        bg_name = self.config.get("background_filename", "bg.jpg")
        bg_path = os.path.join(self.res_dir, bg_name)
        if not os.path.exists(bg_path):
            return Image.new('RGBA', (w, h), (50, 50, 50, 255))
        try:
            img = Image.open(bg_path).convert('RGBA')
            iw, ih = img.size
            scale = max(w / iw, h / ih)
            nw, nh = int(iw * scale), int(ih * scale)
            img = img.resize((nw, nh), Image.Resampling.LANCZOS)
            return img.crop(((nw - w) // 2, (nh - h) // 2, (nw + w) // 2, (nh + h) // 2))
        except:
            return Image.new('RGBA', (w, h), (50, 50, 50, 255))

    def _draw_menu(self):
        title_text = self.config.get("menu_title", "功能菜单")
        raw_items = self.config.get("menu_items", [])

        parsed_items = []
        for item in raw_items:
            if isinstance(item, str):
                parts = item.split(':', 1)
                if len(parts) == 2:
                    parsed_items.append((parts[0], parts[1]))
                elif len(parts) == 1:
                    parsed_items.append((parts[0], ""))

        layout_mode = self.config.get("layout_mode", "vertical")
        W, H = (1920, 1080) if layout_mode == "horizontal" else (1080, 1920)
        cols = 4 if (layout_mode == "horizontal" and len(parsed_items) > 6) else (
            3 if layout_mode == "horizontal" else 2)

        image = self._process_background(W, H)
        draw = ImageDraw.Draw(image)

        t_size = int(W * 0.08)
        f_title = self._load_font(t_size)
        bbox = draw.textbbox((0, 0), title_text, font=f_title)
        tx, ty = (W - (bbox[2] - bbox[0])) / 2, int(H * 0.08)

        c_shadow = self._parse_smart_color(self.config.get("title_shadow_color"), "#00000080")
        c_title = self._parse_smart_color(self.config.get("title_color"), "#FFFFFF")

        draw.text((tx + 4, ty + 4), title_text, font=f_title, fill=c_shadow)
        draw.text((tx, ty), title_text, font=f_title, fill=c_title)

        overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
        d_over = ImageDraw.Draw(overlay)

        margin_x, gap = 60, 35
        card_w = (W - 2 * margin_x - (cols - 1) * gap) / cols
        card_h = 160
        start_y = ty + (bbox[3] - bbox[1]) + 80

        f_trig = self._load_font(45)
        f_desc = self._load_font(26)

        c_bg = self._parse_smart_color(self.config.get("card_bg_color"), "#FFFFFFDC")
        c_trig = self._parse_smart_color(self.config.get("trigger_text_color"), "#282828")
        c_desc = self._parse_smart_color(self.config.get("desc_text_color"), "#646464")

        for i, (trigger, desc) in enumerate(parsed_items):
            r, c = i // cols, i % cols
            x = margin_x + c * (card_w + gap)
            y = start_y + r * (card_h + gap)

            d_over.rounded_rectangle([x, y, x + card_w, y + card_h], radius=20, fill=c_bg)
            d_over.text((x + 20, y + 25), f"➤ {trigger}", font=f_trig, fill=c_trig)

            max_char = int((card_w - 40) / 26)
            if len(desc) > max_char: desc = desc[:max_char - 1] + "…"
            d_over.text((x + 25, y + 95), desc, font=f_desc, fill=c_desc)

        return Image.alpha_composite(image, overlay)

    # --- 核心功能：上传底图 ---
    @filter.command("上传底图")
    async def upload_bg_cmd(self, event: AstrMessageEvent):
        """指令：上传底图 (请引用图片或直接发送图片+指令)"""

        # 1. 获取图片链接
        img_url = self._get_image_url(event)
        if not img_url:
            yield event.plain("❌ 未检测到图片，请【引用】一张图片发送“上传底图”，或者发送包含图片的“上传底图”消息。")
            return

        yield event.plain("⏳ 正在下载并处理底图...")

        # 2. 下载图片
        img_data = await self._download_image(img_url)
        if not img_data:
            yield event.plain("❌ 图片下载失败，请重试。")
            return

        # 3. 确定保存路径
        # 获取配置中的文件名，默认为 bg.jpg
        bg_filename = self.config.get("background_filename", "bg.jpg")
        save_path = os.path.join(self.res_dir, bg_filename)

        # 4. 保存文件
        try:
            with open(save_path, "wb") as f:
                f.write(img_data)

            # 5. 验证图片是否有效 (可选，为了防止坏图)
            try:
                test_img = Image.open(save_path)
                test_img.verify()  # 校验文件完整性
                yield event.plain(f"✅ 底图上传成功！\n已保存为: {bg_filename}")
            except Exception as e:
                yield event.plain(f"⚠️ 文件保存成功，但似乎不是有效的图片格式。\n错误: {e}")

        except Exception as e:
            yield event.plain(f"❌ 保存文件时发生错误: {e}")

    # --- 原有的菜单触发功能 ---
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def menu(self, event: AstrMessageEvent):
        # 避免这里误触发上传底图指令
        if event.message_str.startswith("上传底图"):
            return

        if event.message_str == self.config.get("menu_trigger", "菜单"):
            try:
                img = self._draw_menu()
                path = os.path.join(self.res_dir, "temp_menu_render.png")
                img.save(path)
                yield event.image(path)
            except Exception as e:
                self.context.logger.error(f"菜单生成错误: {e}")
                yield event.plain(f"菜单生成失败: {e}")