"""Bounded, in-memory attachment decoding for local use."""
import base64
import binascii
import csv
import io
import json
import re
import zipfile
from pathlib import PurePath

MAX_FILE = 3 * 1024 * 1024
MAX_TEXT = 120_000
MAX_TOTAL = 8 * 1024 * 1024
IMAGE_SIGNATURES = {'image/png': b'\x89PNG\r\n\x1a\n', 'image/jpeg': b'\xff\xd8\xff', 'image/gif': b'GIF8', 'image/webp': b'RIFF'}


def decode_files(items):
    if not isinstance(items, list) or len(items) > 4:
        raise ValueError('每次最多上传 4 个文件。')
    texts, images, sandbox_files = [], [], []
    total = 0
    for item in items:
        if not isinstance(item, dict): raise ValueError('文件格式不正确。')
        original = item.get('name', '')
        encoded = item.get('data', '')
        if not isinstance(original, str) or not isinstance(encoded, str) or len(encoded) > MAX_FILE * 2:
            raise ValueError('文件信息不正确或文件过大。')
        name = original.replace('\\', '/').split('/')[-1]
        if name in ('', '.', '..') or len(name) > 150 or any(ord(c)<32 for c in name): raise ValueError('文件名不合法。')
        suffix = PurePath(name).suffix.lower()
        try: raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error): raise ValueError('无法读取上传文件。')
        total += len(raw)
        if not raw or len(raw) > MAX_FILE or total > MAX_TOTAL: raise ValueError('文件为空或超过上传大小限制。')
        mime = {'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.webp':'image/webp'}.get(suffix)
        if mime:
            if not raw.startswith(IMAGE_SIGNATURES[mime]) or (mime=='image/webp' and raw[8:12]!=b'WEBP'):
                raise ValueError('图片内容与扩展名不匹配。')
            images.append({'name':name, 'url':'data:'+mime+';base64,'+encoded})
        elif suffix in ('.txt','.md','.csv','.json'):
            try: text=raw.decode('utf-8-sig')
            except UnicodeDecodeError:
                try: text=raw.decode('gb18030')
                except UnicodeDecodeError: raise ValueError('文本文件无法识别编码，请使用 UTF-8。')
            if len(text)>MAX_TEXT: raise ValueError('文本文件内容过长，请分批上传。')
            texts.append((name,text))
            if suffix in ('.csv','.json','.txt'):
                sandbox_files.append({'name': safe_filename(name), 'data': encoded})
        elif suffix=='.pdf':
            from pypdf import PdfReader
            try:
                pdf=PdfReader(io.BytesIO(raw),strict=False)
                if pdf.is_encrypted: raise ValueError('加密 PDF 请先解密。')
                if len(pdf.pages)>30: raise ValueError('PDF 超过 30 页，请拆分上传。')
                text='\n'.join(page.extract_text(extraction_mode='plain') or '' for page in pdf.pages)
            except ValueError: raise
            except Exception: raise ValueError('无法解析 PDF，请检查文件格式。')
            if not text.strip(): raise ValueError('PDF 没有可提取的文字；扫描件请上传页面图片。')
            if len(text)>MAX_TEXT: raise ValueError('PDF 文字过长，请拆分上传。')
            texts.append((name,text))
        elif suffix=='.xlsx':
            from openpyxl import load_workbook
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    if sum(x.file_size for x in z.infolist())>25_000_000 or len(z.infolist())>1000: raise ValueError('Excel 文件解压后过大。')
                book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True,keep_links=False)
                blocks=[]
                if len(book.worksheets)>10: raise ValueError('Excel 工作表过多。')
                for sheet in book.worksheets:
                    rows=[]
                    if sheet.max_row and sheet.max_row>1000: raise ValueError('Excel 单表超过 1000 行，请精简后上传。')
                    if sheet.max_column and sheet.max_column>100: raise ValueError('Excel 单表超过 100 列。')
                    for row in sheet.iter_rows(max_row=1000,max_col=100,values_only=True):
                        values=[str(v) if v is not None else '' for v in row]
                        while values and not values[-1]: values.pop()
                        if values: rows.append('\t'.join(values))
                    blocks.append('工作表 '+sheet.title+'\n'+'\n'.join(rows))
                book.close(); text='\n\n'.join(blocks)
            except ValueError: raise
            except Exception: raise ValueError('无法解析 Excel 文件。')
            if len(text)>MAX_TEXT: raise ValueError('Excel 内容过长，请精简后上传。')
            texts.append((name,text));sandbox_files.append({'name':safe_filename(name),'data':encoded})
        else: raise ValueError('仅支持 TXT、MD、CSV、JSON、XLSX、PDF 和常见图片。')
    names=[x['name'] for x in sandbox_files]
    if len(names)!=len(set(names)): raise ValueError('可计算的数据文件重名，请重命名后上传。')
    return texts, images, sandbox_files


def safe_filename(name):
    name=re.sub(r'[^\w.\-]', '_', name, flags=re.UNICODE).strip('.')
    return name[:140] or 'data.txt'
