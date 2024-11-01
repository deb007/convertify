# converter.py

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Type, List, Tuple

import docx
from docx.document import Document
from docx.text.paragraph import Paragraph
from docx.text.run import Run
import pdfplumber
import re
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class TextElement:
    """Represents a text element with its formatting properties"""
    text: str
    font_size: float = 0
    font_name: str = ""
    bold: bool = False
    italic: bool = False
    is_header: bool = False
    top: float = 0
    left: float = 0
    width: float = 0
    height: float = 0

class DocumentReader(ABC):
    """Abstract base class for document readers."""
    
    @abstractmethod
    def read(self, file_path: str) -> str:
        """Read the document and return its content in a standard format."""
        pass


class DocumentWriter(ABC):
    """Abstract base class for document writers."""
    
    @abstractmethod
    def write(self, content: str, output_path: str) -> None:
        """Write the content to the specified output format."""
        pass


class DocxReader(DocumentReader):
    """Reader for DOCX files."""
    
    def _process_run(self, run: Run) -> str:
        """Process a run and apply appropriate formatting."""
        text = run.text
        
        if run.bold:
            text = f"**{text}**"
        if run.italic:
            text = f"*{text}*"
        if run.underline:
            text = f"__{text}__"
        
        return text

    def _process_paragraph(self, paragraph: Paragraph) -> str:
        """Process a paragraph and apply appropriate formatting."""
        if not paragraph.text.strip():
            return "\n"
        
        # Handle different paragraph styles
        style = paragraph.style.name.lower()
        content = "".join(self._process_run(run) for run in paragraph.runs)
        
        if style.startswith('heading'):
            level = style[-1]
            if level.isdigit():
                return f"{'#' * int(level)} {content}\n\n"
        
        # Handle lists
        if paragraph.style.name.lower().startswith('list'):
            return f"* {content}\n"
        
        return f"{content}\n\n"

    def read(self, file_path: str) -> str:
        """Read DOCX file and convert to intermediate format (Markdown)."""
        try:
            doc: Document = docx.Document(file_path)
            content = ""
            
            for paragraph in doc.paragraphs:
                content += self._process_paragraph(paragraph)
            
            return content.strip()
        except Exception as e:
            raise Exception(f"Error reading DOCX file: {str(e)}")


class PdfReader(DocumentReader):
    """Reader for PDF files"""
    
    def __init__(self):
        self.font_sizes = []
        self.header_sizes = set()
    
    def _analyze_font_sizes(self, pages):
        """Analyze font sizes to determine header levels"""
        sizes = defaultdict(int)
        for page in pages:
            chars = page.chars
            for char in chars:
                if char['size'] is not None:
                    sizes[char['size']] += 1
        
        # Get sorted unique font sizes
        unique_sizes = sorted(sizes.keys(), reverse=True)
        
        # Consider the top 3 largest sizes as potential headers
        self.header_sizes = set(unique_sizes[:3])
        self.font_sizes = unique_sizes
    
    def _get_header_level(self, font_size: float) -> int:
        """Determine header level based on font size"""
        if font_size in self.header_sizes:
            return self.font_sizes.index(font_size) + 1
        return 0
    
    def _extract_text_elements(self, page) -> List[TextElement]:
        """Extract text elements with formatting from a page"""
        elements = []
        
        # First, get all text with position and formatting
        words = page.extract_words(
            keep_blank_chars=True,
            extra_attrs=['fontname', 'size', 'stroking_color', 'non_stroking_color']
        )
        
        current_line_y = None
        current_line_elements = []
        
        for word in words:
            # Create text element
            element = TextElement(
                text=word['text'],
                font_size=word['size'],
                font_name=word['fontname'],
                bold='Bold' in word['fontname'] or word.get('stroking_color') == (0, 0, 0),
                italic='Italic' in word['fontname'],
                top=word['top'],
                left=word['x0'],
                width=word['x1'] - word['x0'],
                height=word['bottom'] - word['top']
            )
            
            # Check if this is a header based on font size
            element.is_header = element.font_size in self.header_sizes
            
            # Handle line breaks
            if current_line_y is None:
                current_line_y = element.top
            
            # If vertical position difference is significant, treat as new line
            if abs(element.top - current_line_y) > element.height * 0.5:
                if current_line_elements:
                    elements.extend(current_line_elements)
                    elements.append(TextElement('\n', 0))
                current_line_elements = []
                current_line_y = element.top
            
            current_line_elements.append(element)
        
        # Add last line
        if current_line_elements:
            elements.extend(current_line_elements)
        
        return elements
    
    def _elements_to_markdown(self, elements: List[TextElement]) -> str:
        """Convert text elements to markdown"""
        markdown_lines = []
        current_line = []
        
        for element in elements:
            if element.text == '\n':
                if current_line:
                    line = ''.join(current_line)
                    if line.strip():
                        markdown_lines.append(line)
                    current_line = []
                continue
            
            text = element.text
            
            # Apply formatting
            if element.is_header:
                level = self._get_header_level(element.font_size)
                text = f"{'#' * level} {text}"
            else:
                if element.bold and element.italic:
                    text = f"***{text}***"
                elif element.bold:
                    text = f"**{text}**"
                elif element.italic:
                    text = f"*{text}*"
            
            current_line.append(text)
        
        # Add any remaining line
        if current_line:
            line = ''.join(current_line)
            if line.strip():
                markdown_lines.append(line)
        
        return '\n\n'.join(markdown_lines)
    
    def read(self, file_path: str) -> str:
        with pdfplumber.open(file_path) as pdf:
            # First pass: analyze font sizes
            self._analyze_font_sizes(pdf.pages)
            
            # Second pass: extract and format text
            all_elements = []
            for page in pdf.pages:
                elements = self._extract_text_elements(page)
                all_elements.extend(elements)
                # Add page break if not last page
                if page.page_number < len(pdf.pages):
                    all_elements.append(TextElement('\n', 0))
            
            return self._elements_to_markdown(all_elements)


class MarkdownWriter(DocumentWriter):
    """Writer for Markdown files."""
    
    def write(self, content: str, output_path: str) -> None:
        """Write content to a Markdown file."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            raise Exception(f"Error writing Markdown file: {str(e)}")


class DocumentConverter:
    """Main converter class that orchestrates the conversion process."""
    
    def __init__(self):
        self.readers: Dict[str, Type[DocumentReader]] = {
            '.docx': DocxReader,
            '.pdf': PdfReader
        }
        self.writers: Dict[str, Type[DocumentWriter]] = {
            '.md': MarkdownWriter
        }
    
    def register_reader(self, extension: str, reader: Type[DocumentReader]) -> None:
        """Register a new document reader."""
        self.readers[extension] = reader
    
    def register_writer(self, extension: str, writer: Type[DocumentWriter]) -> None:
        """Register a new document writer."""
        self.writers[extension] = writer
    
    def convert(self, input_path: str, output_path: str) -> None:
        """Convert a document from one format to another."""
        input_ext = Path(input_path).suffix.lower()
        output_ext = Path(output_path).suffix.lower()
        
        # Validate input format
        if input_ext not in self.readers:
            raise ValueError(f"Unsupported input format: {input_ext}")
        
        # Validate output format
        if output_ext not in self.writers:
            raise ValueError(f"Unsupported output format: {output_ext}")
        
        # Create reader and writer instances
        reader = self.readers[input_ext]()
        writer = self.writers[output_ext]()
        
        # Perform conversion
        content = reader.read(input_path)
        writer.write(content, output_path)
