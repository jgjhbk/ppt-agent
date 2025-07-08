import re  # 新增：导入正则模块
from typing import List, Dict, Any, Optional
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from document_parser import DocumentModel  # 导入DocumentModel类

class PPTGenerator:
    """PPT生成器，负责将文档内容转换为PPT"""

    def __init__(self, template_path: Optional[str] = None):
        self.template_path = template_path
        self.prs = Presentation(template_path)
        self.slide_height = self.prs.slide_height

    def generate(self, doc_model: DocumentModel, output_path: str) -> None:
        """生成PPT文件"""
        # 创建标题页
        title_slide_layout = self.prs.slide_layouts[0]
        slide = self.prs.slides.add_slide(title_slide_layout)

        title = slide.shapes.title
        subtitle = slide.placeholders[1]

        title.text = doc_model.get_title() or "演示文稿"
        for paragraph in title.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.name = "宋体"
                run.font.size = Pt(40)  
                run.font.bold = True
            paragraph.alignment = PP_ALIGN.CENTER
            paragraph.line_spacing = 1.5

        subtitle.text = f"作者: {doc_model.get_author() or '未知'}\n日期: {doc_model.metadata.get('date', '')}"
        for paragraph in subtitle.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.name = "宋体"
                run.font.bold = True
                run.font.size = Pt(20)  
            paragraph.line_spacing = 1.5

        # 创建内容页（核心修复：处理一级标题的正文）
        self._process_sections(doc_model.sections, doc_model.images)

        self.prs.save(output_path)

    def _process_sections(self, sections: List[Dict], images: Dict[str, Any], parent_level: int = 0) -> None:
        """递归处理章节，生成对应的幻灯片"""
        for section in sections:
            # 修复：一级标题不仅显示标题，还要显示其正文内容
            if section['level'] == 1:  
                # 1. 生成一级标题幻灯片
                self._add_title_only_slide(section['title'])
                
                # 2. 如果一级标题有正文，生成内容幻灯片（核心修复点）
                if section['content'].strip():
                    self._add_content_slide(section['content'], images)

                # 3. 处理子章节
                if section.get('subsections'):
                    self._process_sections(section['subsections'], images, section['level'])
            
            elif section['level'] == 2:  # 二级标题
                self._add_bullet_slide(section['title'], section['content'], images)
                if section.get('subsections'):
                    self._process_sections(section['subsections'], images, section['level'])
            
            elif section['level'] == 3:  # 三级标题
                self._add_sub_bullet_slide(section['title'], section['content'], images)

    # 以下方法保持不变，但确保内容能正确传递
    def _add_title_only_slide(self, title: str) -> None:
        """添加仅包含标题的幻灯片"""
        slide_layout = self.prs.slide_layouts[5]
        slide = self.prs.slides.add_slide(slide_layout)

        left = Inches(1.0)
        top = Inches(3.0)
        width = Inches(8.0)
        height = Inches(2.0)

        txBox = slide.shapes.add_textbox(left, top, width, height)
        tf = txBox.text_frame
        tf.word_wrap = True

        p = tf.add_paragraph()
        p.text = title
        p.alignment = PP_ALIGN.CENTER

        for run in p.runs:
            run.font.name = "宋体"
            run.font.size = Pt(32)
            run.font.bold = True

    def _add_content_slide(self, content: str, images: Dict[str, Any]) -> None:
        """添加仅包含内容的幻灯片（用于一级标题的正文）"""
        slide_layout = self.prs.slide_layouts[1]
        slide = self.prs.slides.add_slide(slide_layout)

        # 清除标题占位符的默认文本
        title_shape = slide.shapes.title
        title_shape.text = ""
        
        body_shape = slide.placeholders[1]
        self._populate_content(body_shape, content, images)

    def _add_bullet_slide(self, title: str, content: str, images: Dict[str, Any]) -> None:
        """添加带要点的幻灯片"""
        slide_layout = self.prs.slide_layouts[1]
        slide = self.prs.slides.add_slide(slide_layout)

        title_shape = slide.shapes.title
        title_shape.text = title
        for paragraph in title_shape.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.name = "宋体"
                run.font.size = Pt(28)
            paragraph.alignment = PP_ALIGN.LEFT
            paragraph.line_spacing = 1.5

        body_shape = slide.placeholders[1]
        self._populate_content(body_shape, content, images)

    def _add_sub_bullet_slide(self, title: str, content: str, images: Dict[str, Any]) -> None:
        """添加子要点幻灯片"""
        slide_layout = self.prs.slide_layouts[1]
        slide = self.prs.slides.add_slide(slide_layout)

        title_shape = slide.shapes.title
        title_shape.text = f"• {title}"
        for paragraph in title_shape.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.name = "宋体"
                run.font.size = Pt(22)
            paragraph.alignment = PP_ALIGN.LEFT
            paragraph.line_spacing = 1.5

        body_shape = slide.placeholders[1]
        self._populate_content(body_shape, content, images)

    def _populate_content(self, body_shape, content: str, images: Dict[str, Any]) -> None:
        """处理内容，支持列表、图片和代码块"""
        tf = body_shape.text_frame
        tf.text = ""

        if not content:
            p = tf.add_paragraph()
            p.text = " "
            self._set_font_and_spacing(p)
            return

        image_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')
        code_block_pattern = re.compile(r'```([\s\S]*?)```')
        
        code_blocks = list(code_block_pattern.finditer(content))
        last_end = 0
        
        for code_match in code_blocks:
            pre_code_text = content[last_end:code_match.start()].strip()
            if pre_code_text:
                self._process_regular_content(tf, pre_code_text, images)

            code_content = code_match.group(1).strip()
            self._add_code_block(code_content)
            last_end = code_match.end()

        remaining_text = content[last_end:].strip()
        if remaining_text:
            self._process_regular_content(tf, remaining_text, images)

    def _process_regular_content(self, text_frame, content: str, images: Dict[str, Any]) -> None:
        """处理常规内容"""
        paragraphs = re.split(r'(\n\n)', content)
        paragraphs = [p for p in paragraphs if p.strip()]
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
                
            image_match = re.search(r'!\[(.*?)\]\((.*?)\)', paragraph)
            if image_match:
                alt_text = image_match.group(1)
                url = image_match.group(2)
                
                image_id = None
                for img_id, img_info in images.items():
                    if img_info['url'] == url:
                        image_id = img_id
                        break
                
                if image_id and images[image_id]['local_path']:
                    self._add_image_slide(alt_text, images[image_id]['local_path'])
                else:
                    p = text_frame.add_paragraph()
                    p.text = f"[图片: {alt_text} - 无法加载]"
                    p.level = 0
                    p.alignment = PP_ALIGN.LEFT
                    p.font.size = Pt(18)
                    self._set_font_and_spacing(p)
            else:
                lines = paragraph.strip().split('\n')
                if not lines:
                    continue

                if lines[0].startswith('- '):
                    self._add_list(text_frame, lines)
                else:
                    p = text_frame.add_paragraph()
                    p.text = paragraph
                    p.level = 0
                    p.alignment = PP_ALIGN.LEFT
                    p.font.size = Pt(18)
                    self._set_font_and_spacing(p)

    def _add_list(self, text_frame, lines: List[str]) -> None:
        """添加列表内容"""
        for line in lines:
            line = line.rstrip()
            if not line:
                continue

            level = 0
            while line.startswith('  '):
                level += 1
                line = line[2:].lstrip()

            if line.startswith('- '):
                p = text_frame.add_paragraph()
                p.text = line[2:].strip()
                p.level = min(level, 4)
                p.alignment = PP_ALIGN.LEFT
                p.font.size = Pt(18 - level * 2)
                self._set_font_and_spacing(p)
            else:
                p = text_frame.add_paragraph()
                p.text = line
                p.level = 0
                p.alignment = PP_ALIGN.LEFT
                p.font.size = Pt(18)
                self._set_font_and_spacing(p)

    def _set_font_and_spacing(self, paragraph) -> None:
        """设置字体和行距"""
        for run in paragraph.runs:
            run.font.name = "宋体"
        paragraph.line_spacing = 1.5

    def _add_code_block(self, code_content: str) -> None:
        """添加代码块幻灯片"""
        code_slide_layout = self.prs.slide_layouts[5]
        code_slide = self.prs.slides.add_slide(code_slide_layout)

        title = code_slide.shapes.title
        title.text = "代码示例"
        for paragraph in title.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.name = "宋体"
                run.font.size = Pt(35)
            paragraph.line_spacing = 1.5

        left = Inches(0.5)
        top = Inches(1.0)
        width = Inches(9.0)
        height = Inches(6.0)

        txBox = code_slide.shapes.add_textbox(left, top, width, height)
        tf = txBox.text_frame

        p = tf.add_paragraph()
        p.text = code_content
        p.font.name = "Consolas"
        p.font.size = Pt(10)

    def _add_image_slide(self, alt_text: str, image_path: str) -> None:
        """添加图片幻灯片"""
        image_slide_layout = self.prs.slide_layouts[5]
        image_slide = self.prs.slides.add_slide(image_slide_layout)

        title = image_slide.shapes.title
        title.text = alt_text
        for paragraph in title.text_frame.paragraphs:
            for run in paragraph.runs:
                run.font.name = "宋体"
                run.font.size = Pt(28)
            paragraph.line_spacing = 1.5

        try:
            # 尝试获取图片尺寸
            from PIL import Image
            img = Image.open(image_path)
            width, height = img.size
            
            # 计算图片在幻灯片中的最佳尺寸
            slide_width = self.prs.slide_width
            slide_height = self.prs.slide_height - Inches(1.5)  # 留出标题空间
            
            # 保持图片比例
            img_ratio = width / height
            slide_ratio = slide_width / slide_height
            
            if img_ratio > slide_ratio:
                # 图片更宽，以宽度为基准
                img_width = slide_width - Inches(1.0)
                img_height = img_width / img_ratio
            else:
                # 图片更高，以高度为基准
                img_height = slide_height - Inches(1.0)
                img_width = img_height * img_ratio
            
            # 居中放置图片
            left = (slide_width - img_width) / 2
            top = Inches(1.5)  # 标题下方的位置
            
            image_slide.shapes.add_picture(image_path, left, top, width=img_width, height=img_height)
        except Exception as e:
            # 如果出现错误，添加文本说明
            print(f"无法添加图片 {image_path}: {str(e)}")
            body_shape = image_slide.placeholders[1]
            tf = body_shape.text_frame
            p = tf.add_paragraph()
            p.text = f"无法加载图片: {alt_text}"
            p.font.name = "宋体"
            p.font.size = Pt(18)    