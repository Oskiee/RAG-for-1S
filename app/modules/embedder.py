from transformers import CLIPProcessor, CLIPModel
import torch
import os
import errno

class CLIPHandler:
    def __init__(self, model_name="openai/clip-vit-base-patch32"):
        self.model_name = model_name
        self.model = CLIPModel.from_pretrained(model_name)
        self.processor = CLIPProcessor.from_pretrained(model_name)

    def process_text(self, text):
        inputs = self.processor(text=text, return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            outputs = self.model.get_text_features(**inputs)
        return outputs

    def process_image(self, image):
        inputs = self.processor(images=image, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model.get_image_features(**inputs)
        return outputs
   
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