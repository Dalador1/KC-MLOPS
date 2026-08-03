import os

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


class SpamPredictor:
    def __init__(self) -> None:
        self.model_name = os.getenv("ML_MODEL_NAME", "RUSpam/spam_deberta_v4")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self.model.eval()

    def predict(self, texts: list[str]) -> list[tuple[str, float]]:
        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=256,
        )
        with torch.inference_mode():
            probabilities = torch.softmax(self.model(**inputs).logits, dim=1)

        class_ids = probabilities.argmax(dim=1)
        return [
            (
                "spam" if class_id.item() == 1 else "ham",
                probabilities[row, class_id].item(),
            )
            for row, class_id in enumerate(class_ids)
        ]
