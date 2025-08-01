# src/core/chat_manager.py

import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ChatManager:
    def __init__(self, base_data_dir: str = "chat_data"):
        """Sohbet yöneticisi - her sohbet için ayrı klasör oluşturur"""
        self.base_data_dir = Path(base_data_dir)
        self.base_data_dir.mkdir(exist_ok=True)
        
        # Chat metadata dosyası
        self.chats_metadata_file = self.base_data_dir / "chats_metadata.json"
        self.chats_metadata = self.load_chats_metadata()
    
    def load_chats_metadata(self) -> Dict[str, Any]:
        """Tüm sohbetlerin metadata'sını yükler"""
        if self.chats_metadata_file.exists():
            try:
                with open(self.chats_metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"❌ Chat metadata yükleme hatası: {e}")
                return {}
        return {}
    
    def save_chats_metadata(self):
        """Sohbet metadata'sını kaydet"""
        try:
            with open(self.chats_metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.chats_metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ Chat metadata kaydetme hatası: {e}")
    
    def create_new_chat(self, title: str = None) -> str:
        """Yeni sohbet oluşturur"""
        chat_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Sohbet klasörü oluştur
        chat_dir = self.base_data_dir / chat_id
        chat_dir.mkdir(exist_ok=True)
        
        # PDF'ler için alt klasör
        pdf_dir = chat_dir / "pdfs"
        pdf_dir.mkdir(exist_ok=True)
        
        # Vector store için alt klasör
        vector_dir = chat_dir / "vector_store"
        vector_dir.mkdir(exist_ok=True)
        
        # Sohbet metadata'sı
        chat_metadata = {
            "id": chat_id,
            "title": title or f"Sohbet {len(self.chats_metadata) + 1}",
            "created_at": timestamp,
            "updated_at": timestamp,
            "message_count": 0,
            "pdf_count": 0,
            "last_message": None
        }
        
        # Metadata'yı kaydet
        self.chats_metadata[chat_id] = chat_metadata
        self.save_chats_metadata()
        
        # Sohbet geçmişi dosyası oluştur
        chat_history_file = chat_dir / "messages.json"
        with open(chat_history_file, 'w', encoding='utf-8') as f:
            json.dump([], f)
        
        logger.info(f"✅ Yeni sohbet oluşturuldu: {chat_id}")
        return chat_id
    
    def get_all_chats(self) -> List[Dict[str, Any]]:
        """Tüm sohbetleri listeler (tarihe göre sıralı)"""
        chats = list(self.chats_metadata.values())
        chats.sort(key=lambda x: x['updated_at'], reverse=True)
        return chats
    
    def get_chat_info(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Belirli bir sohbetin bilgilerini getirir"""
        return self.chats_metadata.get(chat_id)
    
    def update_chat_title(self, chat_id: str, title: str):
        """Sohbet başlığını günceller"""
        if chat_id in self.chats_metadata:
            self.chats_metadata[chat_id]["title"] = title
            self.chats_metadata[chat_id]["updated_at"] = datetime.now().isoformat()
            self.save_chats_metadata()
    
    def delete_chat(self, chat_id: str) -> bool:
        """Sohbeti siler"""
        try:
            chat_dir = self.base_data_dir / chat_id
            if chat_dir.exists():
                import shutil
                shutil.rmtree(chat_dir)
            
            if chat_id in self.chats_metadata:
                del self.chats_metadata[chat_id]
                self.save_chats_metadata()
            
            logger.info(f"🗑️ Sohbet silindi: {chat_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Sohbet silme hatası: {e}")
            return False
    
    def get_chat_messages(self, chat_id: str) -> List[Dict[str, Any]]:
        """Sohbet mesajlarını getirir"""
        try:
            chat_dir = self.base_data_dir / chat_id
            messages_file = chat_dir / "messages.json"
            
            if messages_file.exists():
                with open(messages_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"❌ Mesaj yükleme hatası: {e}")
        return []
    
    def save_message(self, chat_id: str, message: Dict[str, Any]):
        """Sohbete mesaj ekler"""
        try:
            chat_dir = self.base_data_dir / chat_id
            messages_file = chat_dir / "messages.json"
            
            # Mevcut mesajları yükle
            messages = self.get_chat_messages(chat_id)
            
            # Yeni mesajı ekle
            message["timestamp"] = datetime.now().isoformat()
            messages.append(message)
            
            # Kaydet
            with open(messages_file, 'w', encoding='utf-8') as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
            
            # Metadata güncelle
            if chat_id in self.chats_metadata:
                self.chats_metadata[chat_id]["message_count"] = len(messages)
                self.chats_metadata[chat_id]["updated_at"] = datetime.now().isoformat()
                if message.get("type") == "user":
                    self.chats_metadata[chat_id]["last_message"] = message.get("content", "")[:100]
                self.save_chats_metadata()
                
        except Exception as e:
            logger.error(f"❌ Mesaj kaydetme hatası: {e}")
    
    def get_chat_directory(self, chat_id: str) -> Path:
        """Sohbet klasörünü döner"""
        return self.base_data_dir / chat_id
    
    def get_chat_pdf_directory(self, chat_id: str) -> Path:
        """Sohbet PDF klasörünü döner"""
        return self.base_data_dir / chat_id / "pdfs"
    
    def get_chat_vector_directory(self, chat_id: str) -> Path:
        """Sohbet vector store klasörünü döner"""
        return self.base_data_dir / chat_id / "vector_store"
    
    def update_pdf_count(self, chat_id: str, pdf_count: int):
        """PDF sayısını günceller"""
        if chat_id in self.chats_metadata:
            self.chats_metadata[chat_id]["pdf_count"] = pdf_count
            self.chats_metadata[chat_id]["updated_at"] = datetime.now().isoformat()
            self.save_chats_metadata()
    
    def auto_generate_title(self, chat_id: str, first_message: str) -> str:
        """İlk mesajdan otomatik başlık oluşturur"""
        # Basit başlık oluşturma - ilk 50 karakter
        title = first_message[:50].strip()
        if len(first_message) > 50:
            title += "..."
        
        # Özel karakterleri temizle
        title = "".join(c for c in title if c.isalnum() or c in " -_")
        title = title or f"Sohbet {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        self.update_chat_title(chat_id, title)
        return title