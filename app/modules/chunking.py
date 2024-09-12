from pdf2image import convert_from_path
import os
from os import listdir
from os.path import isfile, join
from llama_index.core import SimpleDirectoryReader
from abc import abstractmethod, ABC
from langchain.docstore.document import Document
from typing import List, Any, Optional
from langchain.text_splitter import RecursiveCharacterTextSplitter
import openai
import pickle
from io import BytesIO
from hashlib import md5
from copy import deepcopy
from llama_index.multi_modal_llms.openai import OpenAIMultiModal

with open("../openai_api_key.txt", "r") as f:
    OPENAI_API_TOKEN = f.read().strip()
openai.api_key = OPENAI_API_TOKEN

openai_mm_llm = OpenAIMultiModal(
    model="gpt-4o", api_key=OPENAI_API_TOKEN, max_new_tokens=2500
)

class File(ABC):

    def __init__(
        self,
        name: str,
        id: str,
        metadata: Optional[dict[str, Any]] = None,
        docs: Optional[List[Document]] = None,
    ):
        self.name = name
        self.id = id
        self.metadata = metadata or {}
        self.docs = docs or []

    @classmethod
    @abstractmethod
    def from_bytes(cls, file: BytesIO, file_path: str) -> "File":
        """Creates a File from a BytesIO object"""

    def __repr__(self) -> str:
        return (
            f"File(name={self.name}, id={self.id},"
            f" metadata={self.metadata}, docs={self.docs})"
        )

    def __str__(self) -> str:
        return f"File(name={self.name}, id={self.id}, metadata={self.metadata})"

    def copy(self) -> "File":
        return self.__class__(
            name=self.name,
            id=self.id,
            metadata=deepcopy(self.metadata),
            docs=deepcopy(self.docs),
        )

class PdfFile(File):
    def pdf2img(self, pdf_path):
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_dir = f"{pdf_name}_images"
        os.makedirs(output_dir, exist_ok=True)

        images = convert_from_path(pdf_path)
        saved_image_paths = []
        for i, img in enumerate(images):
            image_path = os.path.join(output_dir, f'page{i}.png')
            img.save(image_path, 'PNG')
            saved_image_paths.append(image_path)

        return saved_image_paths

    @classmethod
    def from_bytes(cls, file: BytesIO, file_path: str) -> "PdfFile":
        saved_paths = cls.pdf2img(file_path)
        docs = []
        for k, pg in enumerate(saved_paths):
          page = SimpleDirectoryReader(input_files=[pg]).load_data()
          response = openai_mm_llm.complete(
            prompt="""Please extract the content of the page while preserving the information as closely to the original as possible. Follow these specific instructions:
            Provide a complete and accurate retelling of the text presented. You should stay as close to the original text as possible.
            If the page contains tables, describe them in a tabulated format. Ensure that all information from the original tables is included and place this description where the original table appeared in the text.
            For any schemas, graphs, charts, or similar visuals present on the page, describe their content in maximum detail. Make sure to convey all useful information contained in these images and place your description where the original image appeared in the text.
            If you encounter an image that does not contribute any additional information to the document, please disregard it and do not include it in your response. Also you should not include footers.
            By following these guidelines, write a comprehensive response in russian. Do not include any of your extra comments.""",
            image_documents=page,
          )
          # with open(f"{os.path.basename(pdf_path)}.txt", "a") as f: # debug
          #   print(response, file=f)
          response = str(response)
          doc = Document(page_content=response.strip())
          doc.metadata["page"] = k + 1
          doc.metadata["source"] = f"p-{k+1}"
          docs.append(doc)
        file.seek(0)
        return cls(name=file.name, id=md5(file.read()).hexdigest(), docs=docs)

def get_chunked_files(path: str, chunk_size: int, to_save: bool, chunk_overlap: int = 0, model_name="gpt-3.5-turbo") -> List[File]:
    all_files = [join(path, f) for f in listdir(path) if isfile(join(path, f)) and not f.startswith('.')]
    files = []
    for pdf_path in all_files:
        files.append(PdfFile.from_bytes(open(pdf_path, "rb"), pdf_path))

    chunked_files = []
    for fil in files:
        chunked_files.append(chunk_file(fil, chunk_size, chunk_overlap, model_name))

    if to_save:
        save_object(chunked_files, 'chunked_files.pkl')

    return chunked_files

def chunk_file(file: File, chunk_size: int, chunk_overlap: int = 0, model_name="gpt-3.5-turbo") -> File:
    chunked_docs = []
    for doc in file.docs:
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name=model_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        chunks = text_splitter.split_text(doc.page_content)

        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={
                    "page": doc.metadata.get("page", 1),
                    "chunk": i + 1,
                    "source": f"{doc.metadata.get('page', 1)}-{i + 1}",
                },
            )
            chunked_docs.append(doc)

    chunked_file = file.copy()
    chunked_file.docs = chunked_docs
    return chunked_file

def save_object(obj, filename):
    with open(filename, 'wb') as outp:
        pickle.dump(obj, outp, pickle.HIGHEST_PROTOCOL)