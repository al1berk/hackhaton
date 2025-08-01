# src/core/database.py

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import uuid

class DatabaseManager:
    def __init__(self, db_path: str = "chat_system.db"):
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """Veritabanını başlat ve tabloları oluştur"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Kullanıcılar tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Sohbetler tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Mesajlar tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sender TEXT NOT NULL CHECK (sender IN ('user', 'ai', 'system')),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_type TEXT DEFAULT 'text',
                    metadata TEXT,
                    FOREIGN KEY (chat_id) REFERENCES chats (id)
                )
            ''')
            
            # Dökümanlar tablosu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    file_type TEXT,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT 0,
                    FOREIGN KEY (chat_id) REFERENCES chats (id)
                )
            ''')
            
            conn.commit()
            
    def get_or_create_user(self, username: str) -> int:
        """Kullanıcı getir veya oluştur"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            
            if user:
                return user[0]
            else:
                cursor.execute('INSERT INTO users (username) VALUES (?)', (username,))
                return cursor.lastrowid
                
    def create_chat(self, user_id: int, title: str = None) -> str:
        """Yeni sohbet oluştur"""
        chat_id = str(uuid.uuid4())
        if not title:
            title = f"Sohbet {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO chats (id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (chat_id, user_id, title, datetime.now(), datetime.now()))
            
        # Sohbet için döküman klasörü oluştur
        chat_folder = Path(f"uploads/chats/{chat_id}")
        chat_folder.mkdir(parents=True, exist_ok=True)
        
        return chat_id
        
    def get_user_chats(self, user_id: int) -> List[Dict]:
        """Kullanıcının sohbetlerini getir"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       (SELECT COUNT(*) FROM messages WHERE chat_id = c.id) as message_count,
                       (SELECT content FROM messages WHERE chat_id = c.id ORDER BY timestamp DESC LIMIT 1) as last_message
                FROM chats c
                WHERE c.user_id = ? AND c.is_active = 1
                ORDER BY c.updated_at DESC
            ''', (user_id,))
            
            chats = []
            for row in cursor.fetchall():
                chats.append({
                    'id': row[0],
                    'title': row[1],
                    'created_at': row[2],
                    'updated_at': row[3],
                    'message_count': row[4],
                    'last_message': row[5][:100] + '...' if row[5] and len(row[5]) > 100 else row[5]
                })
            return chats
            
    def get_chat_messages(self, chat_id: str) -> List[Dict]:
        """Sohbet mesajlarını getir"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT content, sender, timestamp, message_type, metadata
                FROM messages
                WHERE chat_id = ?
                ORDER BY timestamp ASC
            ''', (chat_id,))
            
            messages = []
            for row in cursor.fetchall():
                message = {
                    'content': row[0],
                    'sender': row[1],
                    'timestamp': row[2],
                    'message_type': row[3]
                }
                if row[4]:
                    try:
                        message['metadata'] = json.loads(row[4])
                    except:
                        pass
                messages.append(message)
            return messages
            
    def add_message(self, chat_id: str, content: str, sender: str, message_type: str = 'text', metadata: Dict = None):
        """Mesaj ekle"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            metadata_json = json.dumps(metadata) if metadata else None
            cursor.execute('''
                INSERT INTO messages (chat_id, content, sender, message_type, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (chat_id, content, sender, message_type, metadata_json))
            
            # Sohbet güncelleme tarihini güncelle
            cursor.execute('''
                UPDATE chats SET updated_at = ? WHERE id = ?
            ''', (datetime.now(), chat_id))
            
    def add_document(self, chat_id: str, filename: str, original_filename: str, file_path: str, file_size: int, file_type: str) -> int:
        """Döküman ekle"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO documents (chat_id, filename, original_filename, file_path, file_size, file_type)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (chat_id, filename, original_filename, file_path, file_size, file_type))
            return cursor.lastrowid
            
    def get_chat_documents(self, chat_id: str) -> List[Dict]:
        """Sohbet dökümanlarını getir"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, filename, original_filename, file_path, file_size, file_type, uploaded_at, processed
                FROM documents
                WHERE chat_id = ?
                ORDER BY uploaded_at DESC
            ''', (chat_id,))
            
            documents = []
            for row in cursor.fetchall():
                documents.append({
                    'id': row[0],
                    'filename': row[1],
                    'original_filename': row[2],
                    'file_path': row[3],
                    'file_size': row[4],
                    'file_type': row[5],
                    'uploaded_at': row[6],
                    'processed': bool(row[7])
                })
            return documents
            
    def update_chat_title(self, chat_id: str, title: str):
        """Sohbet başlığını güncelle"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE chats SET title = ?, updated_at = ? WHERE id = ?
            ''', (title, datetime.now(), chat_id))
            
    def delete_chat(self, chat_id: str):
        """Sohbeti sil (soft delete)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE chats SET is_active = 0 WHERE id = ?', (chat_id,))