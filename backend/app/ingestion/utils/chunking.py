from pydantic import BaseModel
from enum import Enum
import uuid
import hashlib
from collections import Counter
from typing import Any


from app.ingestion.utils.text_extracter import DocumentSchema,Page,Block,BlockType

from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import AutoTokenizer

BGE_M3_TOKENIZER = AutoTokenizer.from_pretrained("BAAI/bge-m3")


def _bge_m3_token_count(text:str)->int:

    return len(BGE_M3_TOKENIZER.encode(text,add_special_tokens=False))


class chunkingMethod(str,Enum):
    RCTS = "RecursiveCharacterTextSplitter"

class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    chunking_method: chunkingMethod
    text: str
    token_count: int
    doc_char_start: int
    doc_char_end: int
    page_start: int | None = None
    page_end: int | None = None
    bbox_union: list[float] | None = None
    section_path: list[str] = []
    block_types: list[BlockType] = []
    prev_chunk_id: str | None = None
    next_chunk_id: str | None = None
    content_hash: str

#helpers


def _get_page_at_offset(pages:list[Page],char_offset:int)->int:

    """
    Return page number that contains the given absolute char offset
    """

    page_number = pages[0].page_number
    for page in pages:
        if char_offset >= page.doc_char_offset:
            page_number = page.page_number
        else:
            break
    return page_number

def _build_block_index(
    pages:list[Page],
    full_text: str
)-> list[dict[str,Any]]:
    """
    Build a flat list of dicts, one per block, each containing:
      - block: the Block object
      - page_number: which page it's on
      - abs_start: absolute char start in full_text
      - abs_end:   absolute char end in full_text
    """

    index = []

    for page in pages:
        search_from = page.doc_char_offset
        for block in page.blocks:
            if not block.text:
                continue
            pos = full_text.find(block.text,search_from)

            if pos == -1:
                #fallback : try to find anywhere (if text was normalized)
                pos = full_text.find(block.text)

            if pos ==-1:
                #cannot map this block -> skip
                continue

            index.append(
                {
                    "block":block,
                    "page_number":page.page_number,
                    "abs_start":pos,
                    "abs_end":pos + len(block.text),
                }
            )
            search_from = pos + len(block.text)
        
    index.sort(key=lambda x: x["abs_start"])
    return index


def _bbox_unione(bboxes:list[list[float]])->list[float] | None:
    """

    compute the bouding box hat covers all the given bboex.
    
    """

    valid = [b for b in bboxes if b and len(b) == 4]
    if not valid:
        return None
    

    x0 = min(b[0] for b in valid)
    y0 = min(b[1] for b in valid)
    x1 = max(b[2] for b in valid)
    y1 = max(b[3] for b in valid)

    #normalize the size
    
    return [x0, y0, x1, y1]



def _build_section_path(
    block_index: list[dict],
    chunk_char_start:int
)->list[str]:
    """
        Return the heading hierarchy active just before this chunk starts

         e.g. ["Introduction", "Background"]
    """

    heading_stack:dict[int,str] = {} 

    for entry in block_index:
        if entry["abs_end"] >= chunk_char_start:
            break
        
        block = entry["block"]

        if block.type == BlockType.HEADING and block.text and block.level:
            heading_stack[block.level] =  block.text

            #remove deeper levels when a higher level heading appears

            for lvl in list(heading_stack.keys()):
                if lvl > block.level:
                    del heading_stack[lvl]

    #reutrn sorted by level

    return [heading_stack[lvl] for lvl in sorted(heading_stack.keys())]
    


#main function 
def chunk_document(
    document:DocumentSchema,
    document_id:str,
    method:chunkingMethod = chunkingMethod.RCTS,
    chunk_size: int = 512,
    chunk_overlap:int = 64,
)->list[Chunk]:

    pages = document.pages


    #build the full documenttext

    full_text = "\n\n".join(page.text for page in pages if page.text)
    if not full_text:
        return []
    
    #build block index (flat,sorted by postion)

    block_index = _build_block_index(pages,full_text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap = chunk_overlap,
        separators = [
            "\n\n",
            "\n",
            " ",
            ""
        ],
        length_function=_bge_m3_token_count
    )
    raw_chunks = splitter.split_text(full_text)

    #build chunk obkects

    chunks:list[Chunk]=[]

    search_start = 0

    for index,chunk_text in enumerate(raw_chunks):

        #absolute char positions
        char_start = full_text.find(chunk_text,search_start)
        char_end = char_start + len(chunk_text)
        search_start = char_start + 1

        #find all the blocks that overalap with this chunk's range

        overlapping = [
            e for e in block_index
            if e["abs_start"] < char_end
            and e["abs_end"] > char_start
        ]

        #page_start and page_end
        page_start = _get_page_at_offset(pages,char_start)
        page_end = _get_page_at_offset(pages,char_end)

        #bbox union 

        bboxes = [
            e["block"].bbox for e in overlapping if e["block"].bbox
        ]

        union = _bbox_unione(bboxes)

        #block_types(unique, as strings)

        block_types = list(
            {
                e["block"].type.value
                for e in overlapping
            }
        )
        #section path

        section_path = _build_section_path(block_index,char_start)

        #token_count 
        # token_count = len(chunk_text.split())
        token_count = _bge_m3_token_count(chunk_text)

        content_hash = hashlib.sha256(chunk_text.encode()).hexdigest()

        chunk_id = str(uuid.uuid4())

        chunks.append(
            Chunk(

                chunk_id=chunk_id,
                document_id = document_id,
                chunking_method=method,
                text=chunk_text,
                token_count = token_count,
                doc_char_start = char_start,
                doc_char_end = char_end,
                page_start = page_start,
                page_end = page_end,
                bbox_union = union,
                section_path = section_path,
                block_types = block_types,
                content_hash=content_hash,
            )
        )

        # put prev/next chunk ids


    for i,chunk in enumerate(chunks):
            chunk.prev_chunk_id = chunks[i-1].chunk_id if i>0 else None
            chunk.next_chunk_id = chunks[i+1].chunk_id if i < len(chunks) - 1 else None

    
    return chunks

        

        
        