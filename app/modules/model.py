import os
import pandas as pd
import dill
import faiss
import numpy as np
from mistralai import Mistral
from mistralai.models import UserMessage
from .embedder import CLIPHandler

class Model:
    def __init__(self, mistral_api_key):
        cur_path = os.path.dirname(os.path.abspath(__file__))
        chunks_file = os.path.join(cur_path, 'db/chunked_files.pkl')
        index_file = os.path.join(cur_path, 'db/faiss_index.index')
        self.chunks = self.load_chunks(chunks_file)
        self.index = self.load_index(index_file)
        self.embed_model = CLIPHandler()
        self.mistral_client = Mistral(api_key=mistral_api_key)

    def get_images_paths(self, metadata):
        cur_path = os.path.dirname(os.path.abspath(__file__))
        image_info_csv = os.path.join(cur_path, 'db/image_index.csv')
        images_dir = os.path.join(cur_path, 'db/images')
        image_df = pd.read_csv(image_info_csv)
    
        results = []
    
        for item in metadata:
            page = item['page']
            source = item['source']
        
            file_name = source.rsplit('.', 1)[0].strip()
        
            matching_images = image_df[(image_df['file_name'] == file_name) & 
                                       (image_df['page_number'] == page) & 
                                       (image_df['num_images'] > 0)]
        
            image_paths = []
            if not matching_images.empty:
                for _, row in matching_images.iterrows():
                    full_path = os.path.join(images_dir, file_name, row['image_name'])
                    image_paths.append(full_path)
        
            results.append(image_paths)
    
        return results # возвращает список из 3 (3 чанка) эллементов,каждый который может быть: пустой; путь к изображению
    
    def load_chunks(self, filename):
        with open(filename, 'rb') as inp:
            return dill.load(inp)

    def load_index(self, filename):
        return faiss.read_index(filename)

    def generate_mistral_response(self, user_message, model="open-mistral-nemo"):
        chat_response = self.mistral_client.chat.complete(
        model=model,
        messages=[UserMessage(content=user_message)],
    )
    
        return chat_response.choices[0].message.content

    def prompt_eng(retrieved_chunks, user_query):
        # Формирование промпта
        prompt = f"""
        You are an expert in technical documentation for the electric power industry.

        Your task is to answer users' questions in Russian only, confidently and politely, based solely on the provided contextual information.

        !!!!!Do not use any prior knowledge or assumptions.!!!!!

        **You are obliged to provide links to the material from the provided information from the metadata (<source_from_chunk>,<pages_from_chunks>) below in the format:**
        --------------------------------------------------------------
        Источник: <source_from_chunk>, Страницы: <pages_from_chunks>;
        --------------------------------------------------------------
        * Don't write information about chunk number*
        *If you have not found relevant information from the given context, do not write sources!*

        Context information is provided below.
        ---------------------
        {retrieved_chunks}
        ---------------------

        Given the context information above, answer the following question in as much detail as possible:
        Query: {user_query}

        Answer:
        """
        return prompt

    def process_user_query(self, user_query):
        # Embedding пользовательского запроса
        question_embeddings = np.array([self.embed_model.process_text(user_query)]).reshape(1, 512)

        # Поиск ближайших чанков
        D, I = self.index.search(question_embeddings, k=3)

        # Маппинг индексов
        index_mapping = []
        for file_index, file in enumerate(self.chunks):
            for chunk_index in range(len(file.docs)):
                index_mapping.append((file_index, chunk_index))

        # Получение релевантных чанков
        retrieved_chunks = []
        metadata = []
        for i in I.tolist()[0]:
            file_index, chunk_index = index_mapping[i]
            chunk = self.chunks[file_index].docs[chunk_index]
            retrieved_chunks.append(chunk)
            metadata.append(chunk.metadata)

        # Формирование промпта
        prompt = self.prompt_eng(retrieved_chunks, user_query)

        # Генерация ответа с помощью Mistral
        response = self.generate_mistral_response(prompt)

        return response, metadata


# Пример использования
# if __name__ == "__main__":
#    model = Model('')
#    user_query = "Какой трансформатор использовать"
#    response, metadata = model.process_user_query(user_query)
#    image_paths_list = get_images_paths(metadata, image_info_csv, images_dir)
#    print(response)
