# src/core/vector_store.py

import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import PyPDF2
from pathlib import Path
import json
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class VectorStore:
    def __init__(self, persist_directory: str = "chroma_db"):
        """ChromaDB tabanlı vektör deposu başlatır"""
        self.persist_directory = persist_directory
        
        # ChromaDB istemcisini başlat
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Sentence transformer modelini yükle
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        # Koleksiyonu al veya oluştur
        self.collection = self.client.get_or_create_collection(
            name="pdf_documents",
            metadata={"hnsw:space": "cosine"}
        )
        
        logger.info(f"✅ VectorStore başlatıldı. Koleksiyon: {self.collection.count()} doküman")

    def extract_text_from_pdf(self, pdf_file) -> str:
        """PDF dosyasından metin çıkarır"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    text += f"\n--- Sayfa {page_num + 1} ---\n{page_text}"
                except Exception as e:
                    logger.warning(f"Sayfa {page_num + 1} okunamadı: {e}")
                    continue
            
            return text.strip()
        except Exception as e:
            logger.error(f"❌ PDF okuma hatası: {e}")
            return ""

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Metni parçalara böler"""
        if not text:
            return []
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            
            # Kelime sınırında kes
            if end < text_length:
                last_space = text.rfind(' ', start, end)
                if last_space > start:
                    end = last_space
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
            if start <= 0:
                start = end
        
        return chunks

    def add_pdf_document(self, pdf_file, filename: str, metadata: Optional[Dict] = None) -> bool:
        """PDF dosyasını vektör deposuna ekler"""
        try:
            # PDF'den metin çıkar
            text = self.extract_text_from_pdf(pdf_file)
            if not text:
                logger.error(f"❌ PDF'den metin çıkarılamadı: {filename}")
                return False
            
            # Dosya hash'i oluştur (tekrar kontrol için)
            file_hash = hashlib.md5(text.encode()).hexdigest()
            
            # Aynı doküman daha önce eklenmiş mi kontrol et
            existing = self.collection.get(
                where={"file_hash": file_hash}
            )
            
            if existing['ids']:
                logger.info(f"📄 Doküman zaten mevcut: {filename}")
                return True
            
            # Metni parçalara böl
            chunks = self.chunk_text(text)
            if not chunks:
                logger.error(f"❌ Metin parçalanmadı: {filename}")
                return False
            
            # Metadata hazırla
            doc_metadata = {
                "filename": filename,
                "file_hash": file_hash,
                "upload_date": datetime.now().isoformat(),
                "chunk_count": len(chunks),
                **(metadata or {})
            }
            
            # Her parça için ID ve metadata oluştur
            ids = []
            metadatas = []
            documents = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{file_hash}_{i}"
                chunk_metadata = {
                    **doc_metadata,
                    "chunk_index": i,
                    "chunk_id": chunk_id
                }
                
                ids.append(chunk_id)
                metadatas.append(chunk_metadata)
                documents.append(chunk)
            
            # Vektör deposuna ekle
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
            logger.info(f"✅ PDF eklendi: {filename} ({len(chunks)} parça)")
            return True
            
        except Exception as e:
            logger.error(f"❌ PDF ekleme hatası: {e}")
            return False

    def search_similar(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Sorguya benzer dokümanları arar"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            if not results['documents'] or not results['documents'][0]:
                return []
            
            search_results = []
            for i in range(len(results['documents'][0])):
                result = {
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "similarity": 1 - results['distances'][0][i],  # Cosine distance'i similarity'ye çevir
                }
                search_results.append(result)
            
            logger.info(f"🔍 Arama tamamlandı: {len(search_results)} sonuç bulundu")
            return search_results
            
        except Exception as e:
            logger.error(f"❌ Arama hatası: {e}")
            return []

    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Tüm dokümanları listeler"""
        try:
            results = self.collection.get(
                include=["metadatas"]
            )
            
            # Dosya bazında grupla
            documents = {}
            for metadata in results['metadatas']:
                filename = metadata.get('filename', 'Unknown')
                if filename not in documents:
                    documents[filename] = {
                        "filename": filename,
                        "upload_date": metadata.get('upload_date'),
                        "chunk_count": metadata.get('chunk_count', 0),
                        "file_hash": metadata.get('file_hash')
                    }
            
            return list(documents.values())
            
        except Exception as e:
            logger.error(f"❌ Doküman listeleme hatası: {e}")
            return []

    def delete_document(self, file_hash: str) -> bool:
        """Dokümanı siler"""
        try:
            # Dokümanın parçalarını bul
            results = self.collection.get(
                where={"file_hash": file_hash}
            )
            
            if not results['ids']:
                logger.warning(f"⚠️ Silinecek doküman bulunamadı: {file_hash}")
                return False
            
            # Tüm parçaları sil
            self.collection.delete(ids=results['ids'])
            
            logger.info(f"🗑️ Doküman silindi: {file_hash}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Doküman silme hatası: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Vektör deposu istatistiklerini döner"""
        try:
            total_chunks = self.collection.count()
            documents = self.get_all_documents()
            
            return {
                "total_documents": len(documents),
                "total_chunks": total_chunks,
                "average_chunks_per_doc": total_chunks / len(documents) if documents else 0,
                "documents": documents
            }
            
        except Exception as e:
            logger.error(f"❌ İstatistik alma hatası: {e}")
            return {"error": str(e)}