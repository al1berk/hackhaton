import os
from PIL import Image
import cv2
import numpy as np
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
import torch

class HandwritingOCR:
    def __init__(self):
        """TrOCR modelini başlat"""
        print("🔄 El yazısı OCR modeli yükleniyor...")
        
        # Handwritten text için özel eğitilmiş model
        self.processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
        self.model = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")
        
        # Printed text için de model (karışık metinler için)
        try:
            self.processor_printed = TrOCRProcessor.from_pretrained("microsoft/trocr-base-printed")
            self.model_printed = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-printed")
            self.has_printed_model = True
        except:
            self.has_printed_model = False
            
        print("✅ OCR modeli hazır!")
    
    def preprocess_image(self, image_path):
        """Görüntüyü OCR için optimize et"""
        # OpenCV ile görüntüyü oku
        image = cv2.imread(image_path)
        
        if image is None:
            raise ValueError(f"Görüntü okunamadı: {image_path}")
        
        # Gri tonlamaya çevir
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Kontrast artırma
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Gürültü azaltma
        denoised = cv2.medianBlur(enhanced, 3)
        
        # PIL formatına çevir
        pil_image = Image.fromarray(denoised).convert('RGB')
        
        return pil_image
    
    def extract_handwritten_text(self, image_path, confidence_threshold=0.8):
        """El yazısı metnini çıkar"""
        try:
            # Görüntüyü hazırla
            image = self.preprocess_image(image_path)
            
            # TrOCR ile işle
            pixel_values = self.processor(images=image, return_tensors="pt").pixel_values
            
            # Text generation
            generated_ids = self.model.generate(
                pixel_values,
                max_length=256,
                num_beams=4,
                early_stopping=True
            )
            
            # Decode et
            text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            return {
                'text': text.strip(),
                'confidence': 'high',  # TrOCR confidence score vermez, yaklaşık
                'method': 'trocr_handwritten'
            }
            
        except Exception as e:
            return {
                'text': '',
                'confidence': 'error',
                'error': str(e),
                'method': 'trocr_handwritten'
            }
    
    def extract_printed_text(self, image_path):
        """Basılı metni çıkar (karışık belgeler için)"""
        if not self.has_printed_model:
            return self.extract_handwritten_text(image_path)
            
        try:
            image = self.preprocess_image(image_path)
            
            pixel_values = self.processor_printed(images=image, return_tensors="pt").pixel_values
            generated_ids = self.model_printed.generate(pixel_values, max_length=256)
            text = self.processor_printed.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            return {
                'text': text.strip(),
                'confidence': 'high',
                'method': 'trocr_printed'
            }
            
        except Exception as e:
            return {
                'text': '',
                'confidence': 'error', 
                'error': str(e),
                'method': 'trocr_printed'
            }
    
    def extract_mixed_text(self, image_path):
        """Hem el yazısı hem basılı metin için hibrit yaklaşım"""
        handwritten_result = self.extract_handwritten_text(image_path)
        
        if self.has_printed_model:
            printed_result = self.extract_printed_text(image_path)
            
            # En uzun sonucu seç (genellikle daha doğru)
            if len(printed_result['text']) > len(handwritten_result['text']):
                return {
                    'text': printed_result['text'],
                    'confidence': 'mixed_analysis',
                    'method': 'trocr_hybrid',
                    'alternatives': {
                        'handwritten': handwritten_result['text'],
                        'printed': printed_result['text']
                    }
                }
        
        return {
            'text': handwritten_result['text'],
            'confidence': 'handwritten_only',
            'method': 'trocr_hybrid'
        }

def supported_image_formats():
    """Desteklenen görüntü formatları"""
    return ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif']

def is_image_file(file_path):
    """Dosyanın görüntü dosyası olup olmadığını kontrol et"""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in supported_image_formats()
