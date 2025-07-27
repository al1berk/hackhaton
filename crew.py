import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool

# .env dosyasını yükle
load_dotenv()

# --- Güncel CrewAI LLM Konfigürasyonu ---
# CrewAI'ın LLM sınıfını kullanarak Gemini'yi yapılandır
try:
    gemini_llm = LLM(
        model="gemini/gemini-1.5-flash",  # Provider/model formatı
        api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.5
    )
except Exception as e:
    raise ValueError(f"GOOGLE_API_KEY bulunamadı veya geçersiz. .env dosyanızı kontrol edin. Hata: {e}")

# Araçları oluştur
search_tool = SerperDevTool()

# Agent oluşturma - güncel yapı
researcher = Agent(
    role='Kıdemli Araştırma Analisti',
    goal='Verilen konu hakkında güncel ve kapsamlı bilgi toplamak',
    backstory=(
        "Teknoloji ve yapay zeka alanındaki gelişmeleri yakından takip eden, "
        "doğru ve güvenilir bilgiyi hızla bulma konusunda uzman bir araştırmacı."
    ),
    verbose=True,
    allow_delegation=False,
    tools=[search_tool],
    llm=gemini_llm
)

# Task oluşturma
research_task = Task(
    description=(
        "'Yapay Zekanın eğitimdeki son trendleri' üzerine detaylı bir araştırma yap. "
        "Özellikle kişiselleştirilmiş öğrenme ve otomatize edilmiş değerlendirme "
        "konularına odaklan."
    ),
    expected_output=(
        'Konuyla ilgili 3 ana trendi özetleyen, her trend için birer paragraf '
        'açıklama içeren tam bir rapor.'
    ),
    agent=researcher
)

# Crew oluşturma ve çalıştırma
crew = Crew(
    agents=[researcher],
    tasks=[research_task],
    process=Process.sequential,
    verbose=True
)

if __name__ == "__main__":
    try:
        print(crew.kickoff())
        # Görevi başlat
        result = crew.kickoff()
        
        # Sonucu ekrana yazdır
        print("\n" + "="*50)
        print("ARAŞTIRMA SONUCU")
        print("="*50 + "\n")
        print(result)
        
    except Exception as e:
        print(f"Hata oluştu: {e}")
        print("\n--- Muhtemel Çözümler ---")
        print("1. .env dosyasında GOOGLE_API_KEY ve SERPER_API_KEY'in doğru tanımlandığından emin olun")
        print("2. pip install --upgrade crewai crewai-tools python-dotenv komutunu çalıştırın")
        print("3. API key'lerinizin geçerli ve aktif olduğunu kontrol edin")