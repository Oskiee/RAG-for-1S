import os
import pandas as pd
import numpy as np
from mistralai import Mistral
from mistralai.models import UserMessage
from embedder import MultilingualE5

class Model:
    def __init__(self, mistral_api_key):
        self.embed_model = MultilingualE5()
        self.mistral_client = Mistral(api_key=mistral_api_key)

    def generate_mistral_response(self, user_message, model="open-mistral-nemo"):
        chat_response = self.mistral_client.chat.complete(
        model=model,
        messages=[UserMessage(content=user_message)],
    )
    
        return chat_response.choices[0].message.content

    def reranking(self, retreived_chunks, user_query):
        scores = []
        for chunk in retreived_chunks:
            prompt = f"""On a scale of 1-10, rate the relevance of the following document to the query. Consider the specific context and intent of the query, not just keyword matches.
            Query: {user_query}
            Document: {chunk}
            Relevance Score:"""
            scores.append({'File': chunk, 'Score': self.generate_mistral_response(prompt)})

        return scores

    def prompt_eng(self, retrieved_chunks, user_query):
        # Формирование промпта
        prompt = f"""
        You are an expert in technical documentation for the Russian software developer company.

        Your task is to answer users' questions in Russian only, confidently and politely, based solely on the provided contextual information.

        !!!!!Do not use any prior knowledge or assumptions.!!!!!

        **You are obliged to provide links to the material from the provided information from the metadata (<File>) below in the format:**
        --------------------------------------------------------------
        Источник: <File>
        --------------------------------------------------------------
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
        top_docs = self.embed_model.get_top_k(user_query)

        # Формирование промпта
        prompt = self.prompt_eng(top_docs, user_query)

        # Генерация ответа с помощью Mistral
        response = self.generate_mistral_response(prompt)

        return response


# Пример использования
if __name__ == "__main__":
   model = Model('K4zGEUUJAQbeC8E2j0SDd4mRAVTwe5OT')
   user_query = 'Что такое значение "NULL"?'
   response = model.process_user_query(user_query)
   print(response)
