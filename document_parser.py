import os
import re
import requests
from typing import List, Dict, Any, Optional

class DocumentModel:
    """文档模型，负责解析输入文档"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.sections = []
        self.metadata = {}
        self.images = {}  # 存储图片信息

    def parse(self) -> None:
        """解析文档内容"""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"文档不存在: {self.file_path}")

        with open(self.file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        # 提取元数据
        metadata_match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
        if metadata_match:
            metadata_text = metadata_match.group(1)
            for line in metadata_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    self.metadata[key.strip()] = value.strip()
            content = content.replace(metadata_match.group(0), '').strip()

        # 解析章节和内容结构
        section_pattern = re.compile(r'^(#+)\s+(.*?)$', re.MULTILINE)
        current_section = None
        current_level = 0

        # 先处理所有标题，建立章节结构
        for match in section_pattern.finditer(content):
            level = len(match.group(1))
            title = match.group(2).strip()

            section = {
                'title': title,
                'level': level,
                'content': '',
                'subsections': []
            }

            if current_section is None:
                # 第一个章节
                self.sections.append(section)
            else:
                # 确定父章节
                parent = None
                if level > current_level:
                    # 当前章节的子章节
                    parent = current_section
                else:
                    # 查找合适的父章节
                    parent_candidate = self.sections[-1]
                    while parent_candidate['level'] >= level and parent_candidate.get('subsections'):
                        parent_candidate = parent_candidate['subsections'][-1]
                    parent = parent_candidate

                if parent and parent['level'] < level:
                    parent.setdefault('subsections', []).append(section)
                else:
                    self.sections.append(section)

            current_section = section
            current_level = level

        # 提取每个章节的内容
        section_positions = [(m.start(), m.end(), m.group(1), m.group(2))
                             for m in section_pattern.finditer(content)]

        for i, (start, end, header, title) in enumerate(section_positions):
            next_start = section_positions[i + 1][0] if i + 1 < len(section_positions) else len(content)
            section_content = content[end:next_start].strip()

            # 查找对应的章节对象
            def find_section(sections, title, level):
                for s in sections:
                    if s['title'] == title and s['level'] == level:
                        return s
                    sub_result = find_section(s.get('subsections', []), title, level)
                    if sub_result:
                        return sub_result
                return None

            section_obj = find_section(self.sections, title, len(header))
            if section_obj:
                section_obj['content'] = section_content

        # 提取图片信息
        self._extract_images(content)

    def _extract_images(self, content: str) -> None:
        """提取文档中的图片信息"""
        image_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')
        for match in image_pattern.finditer(content):
            alt_text = match.group(1)
            url = match.group(2)
            # 生成图片ID，用于后续处理
            image_id = f"image_{len(self.images) + 1}"
            self.images[image_id] = {
                'alt_text': alt_text,
                'url': url,
                'local_path': None  # 本地路径将在下载后设置
            }

    def download_images(self, temp_dir: str) -> None:
        """下载所有远程图片到临时目录"""
        for image_id, image_info in self.images.items():
            url = image_info['url']
            try:
                # 检查是本地文件还是远程URL
                if url.startswith(('http://', 'https://')):
                    # 下载远程图片
                    response = requests.get(url, stream=True)
                    response.raise_for_status()
                    
                    # 确定文件扩展名
                    ext = os.path.splitext(url)[1].lower()
                    if not ext:
                        ext = '.jpg'  # 默认使用JPG格式
                    
                    local_path = os.path.join(temp_dir, f"{image_id}{ext}")
                    
                    # 保存图片
                    with open(local_path, 'wb') as f:
                        for chunk in response.iter_content(8192):
                            f.write(chunk)
                    
                    image_info['local_path'] = local_path
                else:
                    # 本地文件，检查是否存在
                    if os.path.exists(url):
                        # 复制文件到临时目录
                        ext = os.path.splitext(url)[1].lower()
                        local_path = os.path.join(temp_dir, f"{image_id}{ext}")
                        shutil.copy2(url, local_path)
                        image_info['local_path'] = local_path
                    else:
                        print(f"警告: 本地图片文件不存在: {url}")
            except Exception as e:
                print(f"无法下载图片 {url}: {str(e)}")

    def get_title(self) -> Optional[str]:
        """获取文档标题"""
        return self.metadata.get('title') or (self.sections[0]['title'] if self.sections else None)

    def get_author(self) -> Optional[str]:
        """获取文档作者"""
        return self.metadata.get('author')    