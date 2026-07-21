import fitz
from enum import Enum
from pydantic import BaseModel,Field
from typing import Any
from markdown_it import MarkdownIt


class DocumentType(str, Enum):
    PDF = "application/pdf"
    MD = "text/markdown"
    TXT = "text/plain"


class BlockType(str, Enum):
    TEXT="text"
    HEADING="heading"
    LIST_ITEM="list_item"
    IMAGE="image"
    TABLE="table"
    



class BoundingBox(BaseModel):
    x0:float
    y0:float
    x1:float
    y1:float

class Block(BaseModel):
    type:BlockType
    bbox:list[float] | None = Field(default=None)
    text:str | None = None
    font_size:float | None = None
    is_bold:bool | None = None
    level:int|None = None



class Page(BaseModel):
    page_number:int
    width:float | None = None
    height:float | None  = None 
    rotation:int | None = None
    text:str
    blocks:list[Block]
    doc_char_offset:int = 0 #computed at ingestion , cumulative

class DocumentSchema(BaseModel):
    document_type: DocumentType
    metadata:dict[str,Any] | None = None
    page_count:int = Field(...,gt=0)
    pages:list[Page]


# 0: Text Block (Contains paragraphs, headings, etc.)
# 1: Image Block (Contains the binary image data

# Schema.Page.Block.model_json_schema()



#computer char offsets

def compute_char_offsets(pages: list[Page]) -> list[Page]:
    offset = 0

    for page in pages:
        page.doc_char_offset = offset
        offset += len(page.text)
    return pages

def extract_text_blocks(page:fitz.Page)->list[Block]:
    """ 
    extract all the text blocks from a page
    """

    page_dict = page.get_text("dict")
    blocks: list[Block] = []

    for block in page_dict["blocks"]:
        if block["type"] != 0:
            continue
        
        text_parts = []

        for line in block["lines"]:
            for span in line["spans"]:
                text_parts.append(span["text"])

        text = "".join(text_parts).strip()

        if not text:
            continue

        #normalizing bounding box
        bbox = list(block["bbox"])
        bbox[2] -= bbox[0]
        bbox[3] -= bbox[1]
        
        blocks.append(
            Block(
                type=BlockType.TEXT,
                bbox=bbox,
                text=text
            )
        )
    return blocks

#extract images blocks

def extract_image_blocks(page:fitz.Page) -> list[Block]:
    """
    Extract all the images with their page positions.
    """

    blocks: list[Block] = []

    images = page.get_images(full=True)

    for image in images:

        xref = image[0]

        rects = page.get_image_rects(xref)

        for rect in rects:

            blocks.append(
                Block(
                    type=BlockType.IMAGE,
                    bbox=[rect.x0,rect.y0,rect.x1,rect.y1],
                    text=None
                )
            )
    return blocks


def build_pages(page: fitz.Page)->Page:

    text_blocks = extract_text_blocks(page)
    image_blocks = extract_image_blocks(page)

    blocks = text_blocks + image_blocks

    # Y-coordinate : bbox[1]  vertical position
    # X-coordinate : bbox[0]  horizontal position
    blocks.sort(key=lambda block: (block.bbox[1] if block.bbox else 0,block.bbox[0] if block.bbox else 0)) 


    page_text = "\n".join(
        block.text
        for block in blocks
        if block.type == BlockType.TEXT and block.text
    )

    return Page(
        page_number= page.number + 1,
        width = page.rect.width,
        height = page.rect.height,
        rotation = page.rotation,
        text = page_text,
        blocks = blocks,
    )

def extract_pdf(file_content:bytes) -> DocumentSchema:

    """
    Extract a normalized representation of a PDF.

    Returns a Schema object that can later be passed to
    cleaning, chunking, embedding and indexing stages.
    
    """

    doc = fitz.open(

        stream = file_content,
        filetype = "pdf"
    )

    # data = {
    #     "page_count":doc.page_count,
    #     "metadata":doc.metadata,
    #     "pages":[]
    # }

    try:
        pages = [
            build_pages(page)
            for page in doc
        ] 


        pages = compute_char_offsets(pages)   
        return DocumentSchema(
            document_type=DocumentType.PDF,
            metadata=doc.metadata,
            page_count=doc.page_count,
            pages=pages
        )
    finally:
        doc.close()



def extract_txt(file_content:bytes)-> DocumentSchema:
    """
    Extract a normalized representation of a MD or TXT file.

    Returns a Schema object that can later be passed to
    cleaning, chunking, embedding and indexing stages.
    
    """
    #read and decode
    content = file_content.decode("utf-8")

    #normalize line endings
    content = content.replace("\r\n","\n").replace("\r","\n")

    #split into paragraphs

    raw_paragraphs = content.split("\n\n")

    #strip and filter empty paragraphs

    paragraphs = [p.strip() for p in raw_paragraphs if p.strip()]

    #create TEXT blocks

    blocks = []

    for paragraph in paragraphs:

        blocks.append(

            Block(
                type=BlockType.TEXT,
                bbox=None,
                text=paragraph
            )
        )
    #build the page text
    page_text = "\n".join(
        block.text
        for block in blocks
        if block.type == BlockType.TEXT and block.text
    )

    page = Page(
        page_number = 1,
        text = page_text,
        blocks=blocks
    )

    page = compute_char_offsets([page])

   

    return DocumentSchema(
        document_type=DocumentType.TXT,
        metadata={},
        page_count = 1,
        pages=[page]
    )

def extract_md(file_content:bytes) -> DocumentSchema:

    content = file_content.decode("utf-8")

    md = MarkdownIt()
    tokens = md.parse(content)

    blocks = []

    for token in tokens:
        text_content = ""

        #extract text from standard text elements(headings, paragraphs, lists)

        if token.type == "inline":
            text_content = token.content.strip()

        #extract text from code blocks
        elif token.type in ("fence","code_block"):
            text_content = token.content.strip()
        
        #if text found, create a block fast
        if text_content:
            blocks.append(
                Block(
                    type=BlockType.TEXT,
                    bbox=None,
                    text=text_content
                )
            )
            
    #build the page
    page_text = "\n\n".join(
        block.text
        for block in blocks
        if block.type == BlockType.TEXT and block.text
    )
    page = Page(
        page_number =1,
        text=page_text,
        blocks=blocks
    )

    page = compute_char_offsets([page])
    
    return DocumentSchema(
        document_type=DocumentType.MD,
        metadata={},
        page_count=1,
        pages=page
    )
    


