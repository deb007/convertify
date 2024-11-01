# converter.py

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Type

import docx
from docx.document import Document
from docx.text.paragraph import Paragraph
from docx.text.run import Run


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
            '.docx': DocxReader
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
