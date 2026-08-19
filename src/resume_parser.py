import os
from pypdf import PdfReader

try:
    import docx
except ImportError:
    docx = None

def extract_resume_text(resume_path: str) -> str:
    """
    Extracts text content from either a .pdf or .docx resume file.
    """
    if not os.path.exists(resume_path):
        raise FileNotFoundError(f"Resume file not found at: {resume_path}")

    ext = os.path.splitext(resume_path)[1].lower()

    if ext == ".pdf":
        reader = PdfReader(resume_path)
        text = ""
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
        return text.strip()

    elif ext in [".docx", ".doc"]:
        if docx is None:
            # Fallback using python-docx if installed
            raise ImportError("python-docx package is required to read .docx files. Install with 'pip install python-docx'.")
        
        doc = docx.Document(resume_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    full_text.append(cell.text)
        return "\n".join(full_text).strip()

    else:
        raise ValueError(f"Unsupported file format '{ext}'. Please provide a .pdf or .docx file.")
