from sentence_transformers import SentenceTransformer
from langchain.docstore.document import Document
import numpy as np
import dill
import os
import errno

def get_detailed_instruct(task_description: str, query: str) -> str:
    return f'Instruct: {task_description}\nQuery: {query}'


def load_pkl(filename):
    with open(filename, 'rb') as inp:
        return dill.load(inp)


class MultilingualE5:
    def __init__(self, model_name="intfloat/multilingual-e5-large-instruct"):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        cur_path = os.path.dirname(os.path.abspath(__file__))
        chunks_file = os.path.join(cur_path, 'db/chunked_files_1S_multi.pkl')
        embeddings_file = os.path.join(cur_path, 'db/embeddings_multi.pkl')
        self.chunks = np.array(load_pkl(chunks_file))
        self.doc_embeddings = load_pkl(embeddings_file)

    def get_indexing(self, top_k):
        documents = self.chunks[top_k]
        index = []
        for doc in documents:
            temp = {"File": doc.metadata["source"], "Content": doc.page_content, "Num": doc.metadata["chunk"]}
            index.append(temp)
        return index

    def process_text(self, text):
        task = 'Given a web search query, retrieve relevant passages that answer the query'

        queries = [get_detailed_instruct(task, text)]
        embedding = self.model.encode(queries, convert_to_tensor=True, normalize_embeddings=True)
        return embedding

    def get_top_k(self, query, k=5):
        query_emb = self.process_text(query)
        similarities = (query_emb.cpu() @ self.doc_embeddings.T) * 100
        scores = np.array(similarities[0].tolist())
        top_k = np.argpartition(scores, -k)[-k:]
        top_k = np.flip(top_k[np.argsort(scores[top_k])]).tolist()
        docs = self.get_indexing(top_k)
        return docs
   
    def save_models(self, path):
        path = os.path.join(path, '')

        try:
            os.makedirs(path, exist_ok=True)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        if not os.access(path, os.W_OK):
            raise PermissionError(f"Directory {path} is not writable")

        embedding_path = os.path.join(path, "embedding")
        processor_path = os.path.join(path, "processor")

        try:
            self.model.save_pretrained(embedding_path)
            self.processor.save_pretrained(processor_path)
            print(f"Models saved successfully in {path}")
        except Exception as e:
            print(f"Error saving models: {str(e)}")
            raise