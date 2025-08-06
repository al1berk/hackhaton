#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 AI-Powered Multi-Agent Research & Chat Platform
BTK Hackathon 2025 - Kolay Çalıştırma Scripti

Bu script ile projeyi tek komutla çalıştırabilirsiniz:
python run.py

Jüri için hazırlanmıştır.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

# Renk kodları
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_logo():
    """BTK Hackathon logosu yazdır"""
    logo = f"""
{Colors.BLUE}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                 🤖 AI RESEARCH & CHAT PLATFORM               ║
║                      BTK HACKATHON 2025                     ║
╚══════════════════════════════════════════════════════════════╝
{Colors.END}

{Colors.YELLOW}🚀 Yapay Zeka Destekli Araştırma ve Test Oluşturma Platformu{Colors.END}
{Colors.GREEN}✨ CrewAI Multi-Agent | LangGraph | RAG | FastAPI{Colors.END}
"""
    print(logo)

def check_python_version():
    """Python versiyonunu kontrol et"""
    print(f"{Colors.BLUE}📋 Python versiyonu kontrol ediliyor...{Colors.END}")
    
    if sys.version_info < (3, 8):
        print(f"{Colors.RED}❌ Python 3.8+ gerekli! Mevcut versiyon: {sys.version}{Colors.END}")
        sys.exit(1)
    
    print(f"{Colors.GREEN}✅ Python {sys.version.split()[0]} - Uygun{Colors.END}")

def check_virtual_env():
    """Virtual environment kontrolü"""
    venv_path = Path("btk_env")
    
    if not venv_path.exists():
        print(f"{Colors.YELLOW}⚠️  Virtual environment bulunamadı!{Colors.END}")
        create_env = input(f"{Colors.BLUE}Virtual environment oluşturulsun mu? (y/n): {Colors.END}")
        
        if create_env.lower() in ['y', 'yes', 'evet', 'e']:
            print(f"{Colors.BLUE}📦 Virtual environment oluşturuluyor...{Colors.END}")
            subprocess.run([sys.executable, "-m", "venv", "btk_env"])
            print(f"{Colors.GREEN}✅ Virtual environment oluşturuldu{Colors.END}")
        else:
            print(f"{Colors.RED}❌ Virtual environment gerekli!{Colors.END}")
            sys.exit(1)
    
    print(f"{Colors.GREEN}✅ Virtual environment mevcut{Colors.END}")
    return venv_path

def get_activate_command():
    """İşletim sistemine göre activate komutu"""
    system = platform.system().lower()
    
    if system == "windows":
        return "btk_env\\Scripts\\activate"
    else:
        return "source btk_env/bin/activate"

def check_requirements():
    """Requirements dosyasını kontrol et"""
    req_file = Path("requirements.txt")
    
    if not req_file.exists():
        print(f"{Colors.RED}❌ requirements.txt bulunamadı!{Colors.END}")
        sys.exit(1)
    
    print(f"{Colors.GREEN}✅ requirements.txt mevcut{Colors.END}")

def check_env_file():
    """Environment dosyasını kontrol et"""
    env_file = Path(".env")
    
    if not env_file.exists():
        print(f"{Colors.YELLOW}⚠️  .env dosyası bulunamadı!{Colors.END}")
        print(f"{Colors.BLUE}📝 Örnek .env dosyası oluşturuluyor...{Colors.END}")
        
        env_content = """# BTK HACKATHON 2025 - API ANAHTARLARI
# Bu dosyaya API anahtarlarınızı ekleyin

# ZORUNLU API ANAHTARLARI
GOOGLE_API_KEY=your_google_gemini_api_key_here
SERPER_API_KEY=your_serper_search_api_key_here

# OPSIYONEL API ANAHTARLARI (test için)
YOUTUBE_API_KEY=your_youtube_api_v3_key_here
BRAVE_API_KEY=your_brave_search_api_key_here

# API ANAHTARI ALMA REHBERİ:
# Google API: https://makersuite.google.com/app/apikey
# Serper API: https://serper.dev/
# YouTube API: https://console.cloud.google.com/
# Brave Search: https://brave.com/search/api/
"""
        
        with open(".env", "w", encoding="utf-8") as f:
            f.write(env_content)
        
        print(f"{Colors.GREEN}✅ .env dosyası oluşturuldu{Colors.END}")
        print(f"{Colors.RED}🔑 DİKKAT: .env dosyasına API anahtarlarınızı eklemeyi unutmayın!{Colors.END}")
        
        return False
    
    print(f"{Colors.GREEN}✅ .env dosyası mevcut{Colors.END}")
    return True

def install_requirements():
    """Requirements'ları yükle"""
    print(f"{Colors.BLUE}📦 Python paketleri yükleniyor...{Colors.END}")
    print(f"{Colors.YELLOW}⏳ Bu işlem birkaç dakika sürebilir...{Colors.END}")
    
    # Virtual environment'ı aktifleştirerek pip install çalıştır
    system = platform.system().lower()
    
    if system == "windows":
        pip_path = "btk_env\\Scripts\\pip"
    else:
        pip_path = "btk_env/bin/pip"
    
    try:
        # Pip'i güncelle
        subprocess.run([pip_path, "install", "--upgrade", "pip"], check=True)
        
        # Requirements'ları yükle
        result = subprocess.run([pip_path, "install", "-r", "requirements.txt"], 
                              check=True, capture_output=True, text=True)
        
        print(f"{Colors.GREEN}✅ Tüm paketler başarıyla yüklendi{Colors.END}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}❌ Paket yükleme hatası: {e}{Colors.END}")
        print(f"{Colors.YELLOW}🔧 Manuel kurulum için:{Colors.END}")
        print(f"{Colors.BLUE}   1. {get_activate_command()}{Colors.END}")
        print(f"{Colors.BLUE}   2. pip install -r requirements.txt{Colors.END}")
        return False

def check_src_directory():
    """src klasörünü kontrol et"""
    src_path = Path("src")
    
    if not src_path.exists():
        print(f"{Colors.RED}❌ src klasörü bulunamadı!{Colors.END}")
        sys.exit(1)
    
    server_file = src_path / "api" / "server.py"
    if not server_file.exists():
        print(f"{Colors.RED}❌ src/api/server.py bulunamadı!{Colors.END}")
        sys.exit(1)
    
    print(f"{Colors.GREEN}✅ Proje dosyaları mevcut{Colors.END}")

def start_server():
    """Sunucuyu başlat"""
    print(f"\n{Colors.GREEN}{Colors.BOLD}🚀 SUNUCU BAŞLATILIYOR...{Colors.END}")
    print(f"{Colors.BLUE}📡 http://localhost:8000 adresinde çalışacak{Colors.END}")
    print(f"{Colors.YELLOW}🛑 Durdurmak için Ctrl+C tuşlayın{Colors.END}\n")
    
    # Virtual environment'daki Python'u kullan
    system = platform.system().lower()
    
    if system == "windows":
        python_path = "btk_env\\Scripts\\python"
    else:
        python_path = "btk_env/bin/python"
    
    try:
        # uvicorn ile sunucuyu başlat
        cmd = [
            python_path, "-m", "uvicorn",
            "api.server:app",
            "--reload",
            "--app-dir", "src",
            "--host", "0.0.0.0",
            "--port", "8000"
        ]
        
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}🛑 Sunucu durduruldu{Colors.END}")
        print(f"{Colors.GREEN}✅ Güvenli şekilde kapatıldı{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}❌ Sunucu başlatma hatası: {e}{Colors.END}")
        print(f"\n{Colors.YELLOW}🔧 Manuel başlatma için:{Colors.END}")
        print(f"{Colors.BLUE}   {get_activate_command()}{Colors.END}")
        print(f"{Colors.BLUE}   cd src{Colors.END}")
        print(f"{Colors.BLUE}   uvicorn api.server:app --reload --app-dir src{Colors.END}")

def show_instructions():
    """Kullanım talimatlarını göster"""
    instructions = f"""
{Colors.GREEN}{Colors.BOLD}🎯 KULLANIM TALİMATLARI:{Colors.END}

{Colors.BLUE}1. 🌐 Tarayıcıda http://localhost:8000 adresine gidin{Colors.END}

{Colors.BLUE}2. 🔍 Web Araştırması:{Colors.END}
   • "yapay zeka trendlerini araştır"
   • "blockchain teknolojisi hakkında bilgi ver"

{Colors.BLUE}3. 📚 PDF Analizi:{Colors.END}
   • Sol üstteki "PDF Yükle" butonuna tıklayın
   • PDF dosyanızı seçin
   • "Bu doküman hakkında özet çıkar" yazın

{Colors.BLUE}4. 🎓 Test Oluşturma:{Colors.END}
   • "test oluştur" yazın
   • Parametre seçimi yapın
   • Test çözün ve değerlendirme alın

{Colors.YELLOW}⚠️  NOT: API anahtarlarınızı .env dosyasına eklemeyi unutmayın!{Colors.END}
"""
    print(instructions)

def main():
    """Ana fonksiyon"""
    try:
        print_logo()
        
        # Sistem kontrolleri
        check_python_version()
        check_virtual_env()
        check_requirements()
        check_src_directory()
        
        # Environment dosyası kontrolü
        env_exists = check_env_file()
        
        if not env_exists:
            print(f"\n{Colors.RED}🔑 .env dosyasına API anahtarlarınızı ekledikten sonra tekrar çalıştırın!{Colors.END}")
            sys.exit(1)
        
        # Paket kurulumu kontrolü
        try:
            import fastapi
            import uvicorn
            print(f"{Colors.GREEN}✅ Ana paketler yüklü{Colors.END}")
        except ImportError:
            print(f"{Colors.YELLOW}📦 Paketler yüklenecek...{Colors.END}")
            if not install_requirements():
                sys.exit(1)
        
        # Kullanım talimatlarını göster
        show_instructions()
        
        # Kullanıcı onayı al
        start = input(f"\n{Colors.BLUE}🚀 Sunucuyu başlatmak için Enter tuşuna basın (q=çıkış): {Colors.END}")
        
        if start.lower() in ['q', 'quit', 'çıkış', 'exit']:
            print(f"{Colors.YELLOW}👋 Çıkış yapılıyor...{Colors.END}")
            sys.exit(0)
        
        # Sunucuyu başlat
        start_server()
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}👋 Program sonlandırıldı{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}❌ Beklenmeyen hata: {e}{Colors.END}")
        sys.exit(1)

if __name__ == "__main__":
    main()