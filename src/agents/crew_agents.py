# src/agents/crew_agents.py (DÜZELTME: CrewOutput object hatası giderildi)

from crewai import Agent, Task, Crew, Process, LLM
import json
from typing import Dict, Any, List
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Gerçek araçları tools klasöründen import ediyoruz.
from tools.tools import JSONValidatorToolForQuestion
from core.config import Config

class CrewAISystem:
    def __init__(self, api_key: str, websocket_callback=None):
        # CrewAI'nin kendi LLM wrapper'ını kullan - LiteLLM uyumlu
        self.llm = LLM(
            model="gemini/gemini-2.5-flash",  # Provider prefix'i ekledik
            api_key=api_key,
            temperature=0.7
        )
        self.tools = [JSONValidatorToolForQuestion()]
        self.agents = self._create_agents()
        self.websocket_callback = websocket_callback
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def send_workflow_message(self, agent_name: str, message: str, data: Dict = None):
        """WebSocket üzerinden workflow mesajları gönder"""
        if self.websocket_callback:
            workflow_message = {
                "type": "workflow_message",
                "agent": agent_name,
                "message": message,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.websocket_callback(json.dumps(workflow_message))
            print(f"📡 Workflow Message Sent: {agent_name} -> {message}")

    async def send_progress_update(self, message: str, step_data: Dict = None, agent_name: str = None):
        """İlerleme güncellemeleri gönder"""
        if self.websocket_callback:
            update_data = {
                "type": "crew_progress",
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "agent": agent_name or "CrewAI",
                "step_data": step_data or {}
            }
            await self.websocket_callback(json.dumps(update_data))

    def _create_agents(self) -> Dict[str, Agent]:
        """Farklı soru türleri için özel ajanlar oluşturur."""
        
        return {
            "multiple_choice": Agent(
                role="Çoktan Seçmeli Soru Uzmanı",
                goal="Verilen metin ve tercihlere göre yüksek kaliteli çoktan seçmeli sorular oluşturmak ve JSON formatını doğrulamak.",
                backstory="Sen çoktan seçmeli soru yazma konusunda uzman bir eğitimcisin. Her soru için istenen tüm alanları eksiksiz doldurursun ve JSONValidatorToolForQuestion kullanarak çıktının geçerliliğini kontrol edersin.",
                llm=self.llm, 
                tools=self.tools, 
                verbose=True
            ),
            "classic": Agent(
                role="Klasik Soru Uzmanı", 
                goal="Verilen metin ve tercihlere göre düşündürücü ve kapsamlı açık uçlu sorular oluşturmak ve JSON formatını doğrulamak.",
                backstory="Sen açık uçlu sorular konusunda uzman bir akademisyensin. Öğrencilerin analitik düşünme yeteneklerini test eden, derinlemesine sorular hazırlıyorsun ve JSONValidatorToolForQuestion ile çıktılarının doğruluğunu garanti edersin.",
                llm=self.llm, 
                tools=self.tools, 
                verbose=True
            ),
            "fill_blank": Agent(
                role="Boşluk Doldurma Uzmanı",
                goal="Verilen metne ve tercihlere göre etkili boşluk doldurma soruları oluşturmak ve JSON formatını doğrulamak.",
                backstory="Sen boşluk doldurma soruları konusunda uzman bir öğretmensin. Anahtar kelime ve kavramları vurgulayan sorular hazırlıyorsun ve JSONValidatorToolForQuestion ile format doğruluğunu sağlıyorsun.",
                llm=self.llm, 
                tools=self.tools, 
                verbose=True
            ),
            "validator": Agent(
                role="JSON Format Doğrulama Uzmanı",
                goal="Üretilen tüm soruların JSON formatını kontrol etmek ve düzeltmek.",
                backstory="Sen JSON format doğrulama konusunda uzman bir teknisyensin. Diğer ajanlardan gelen çıktıları JSONValidatorToolForQuestion kullanarak kontrol eder ve geçerli JSON formatına dönüştürürsün.",
                llm=self.llm,
                tools=self.tools,
                verbose=True
            ),
            "coordinator": Agent(
                role="Test Koordinatörü",
                goal="Tüm soru türlerini koordine etmek, kalite kontrolü yapmak ve tek bir final JSON çıktısı oluşturmak.",
                backstory="Sen deneyimli bir test geliştirme koordinatörüsün. Diğer ajanlardan gelen çıktıları birleştirir, JSONValidatorToolForQuestion ile son formatın doğruluğundan emin olursun.",
                llm=self.llm, 
                tools=self.tools, 
                verbose=True
            )
        }

    def _calculate_question_distribution(self, preferences: Dict[str, Any]) -> Dict[str, int]:
        """Soru türlerine göre soru sayısı dağılımını hesaplar."""
        total_questions = preferences.get("toplam_soru", 10)
        question_types = preferences.get("soru_turleri", ["coktan_secmeli"])
        if not question_types: 
            return {}
        
        base_count = total_questions // len(question_types)
        remainder = total_questions % len(question_types)
        distribution = {
            q_type: base_count + (1 if i < remainder else 0) 
            for i, q_type in enumerate(question_types)
        }
        return distribution

    def _create_tasks(self, document_content: str, preferences: Dict[str, Any]) -> List[Task]:
        """Kullanıcı tercihlerine göre her ajan için ayrı ve detaylı görevler oluşturur."""
        tasks = []
        individual_tasks = []
        question_distribution = self._calculate_question_distribution(preferences)

        # --- ÇOKTAN SEÇMELİ GÖREVİ ---
        if question_distribution.get("coktan_secmeli", 0) > 0:
            mc_task = Task(
                description=f"""
                Verilen dokümandan {question_distribution['coktan_secmeli']} adet çoktan seçmeli soru oluştur.
                        
                Döküman içeriği: {document_content[:2000]}...
                        
                Zorluk seviyesi: {preferences.get('zorluk_seviyesi', 'orta')}
                Öğrenci seviyesi: {preferences.get('ogrenci_seviyesi', 'lise')}
                Özel konular: {preferences.get('ozel_konular', [])}
                        
                Her soru için:
                - Açık ve anlaşılır soru metni
                - 4 seçenek (A, B, C, D)
                - Doğru cevap
                - Kısa açıklama
                - Zorluk seviyesi
                        
                **ÇOK ÖNEMLİ ÇIKTI FORMATI:**
                Sadece aşağıdaki formata birebir uyan bir JSON listesi döndür. Başka hiçbir metin ekleme.
                
                ADIM 1: Önce soruları oluştur
                ADIM 2: JSONValidatorToolForQuestion aracını kullanarak çıktını doğrula
                ADIM 3: Doğrulanmış JSON formatını döndür
                
                [
                  {{
                    "soru": "Soru metni buraya gelecek?",
                    "secenekler": {{"A": "Seçenek A", "B": "Seçenek B", "C": "Seçenek C", "D": "Seçenek D"}},
                    "dogru_cevap": "B",
                    "aciklama": "Bu cevabın neden doğru olduğuna dair kısa ve net bir açıklama.",
                    "zorluk": "Orta"
                  }}
                ]
                """,
                agent=self.agents["multiple_choice"],
                expected_output=f"JSON formatında çoktan seçmeli sorular - {question_distribution['coktan_secmeli']} adet"
            )
            tasks.append(mc_task)
            individual_tasks.append(mc_task)

        # --- KLASİK SORU GÖREVİ ---
        if question_distribution.get("klasik", 0) > 0:
            classic_task = Task(
                description=f"""
                Verilen dokümandan {question_distribution['klasik']} adet klasik (açık uçlu) soru oluştur.
                        
                Döküman içeriği: {document_content[:2000]}...
                        
                Zorluk seviyesi: {preferences.get('zorluk_seviyesi', 'orta')}
                Öğrenci seviyesi: {preferences.get('ogrenci_seviyesi', 'lise')}
                Özel konular: {preferences.get('ozel_konular', [])}
                        
                Her soru için:
                - Düşündürücü soru metni
                - Örnek cevap
                - Değerlendirme kriterleri
                - Zorluk seviyesi

                **ÇOK ÖNEMLİ ÇIKTI FORMATI:**
                Sadece aşağıdaki formata birebir uyan bir JSON listesi döndür.
                
                ADIM 1: Önce soruları oluştur
                ADIM 2: JSONValidatorToolForQuestion aracını kullanarak çıktını doğrula
                ADIM 3: Doğrulanmış JSON formatını döndür
                
                [
                  {{
                    "soru": "Analiz ve sentez gerektiren açık uçlu soru metni?",
                    "ornek_cevap": "Bu soruya verilebilecek detaylı ve kapsamlı bir örnek cevap.",
                    "degerlendirme_kriterleri": "Değerlendirme kriterleri burada",
                    "puan": 10,
                    "zorluk": "Zor"
                  }}
                ]
                """,
                agent=self.agents["classic"],
                expected_output=f"JSON formatında klasik sorular - {question_distribution['klasik']} adet"
            )
            tasks.append(classic_task)
            individual_tasks.append(classic_task)

        # --- BOŞLUK DOLDURMA GÖREVİ ---
        if question_distribution.get("bosluk_doldurma", 0) > 0:
            fill_task = Task(
                description=f"""
                Verilen dokümandan {question_distribution['bosluk_doldurma']} adet boşluk doldurma sorusu oluştur.
                        
                Döküman içeriği: {document_content[:2000]}...
                        
                Zorluk seviyesi: {preferences.get('zorluk_seviyesi', 'orta')}
                Öğrenci seviyesi: {preferences.get('ogrenci_seviyesi', 'lise')}
                Özel konular: {preferences.get('ozel_konular', [])}
                        
                Her soru için:
                - Boşluklu cümle
                - Doğru cevap
                - Alternatif kabul edilebilir cevaplar
                - Zorluk seviyesi

                **ÇOK ÖNEMLİ ÇIKTI FORMATI:**
                Sadece aşağıdaki formata birebir uyan bir JSON listesi döndür.
                
                ADIM 1: Önce soruları oluştur
                ADIM 2: JSONValidatorToolForQuestion aracını kullanarak çıktını doğrula
                ADIM 3: Doğrulanmış JSON formatını döndür
                
                [
                  {{
                    "soru": "Metindeki önemli bir kavramın geçtiği ve boşluk bırakılmış cümle. Örneğin: Yapay zeka, _____ bilimlerinin bir dalıdır.",
                    "dogru_cevap": "bilgisayar",
                    "alternatif_cevaplar": ["bilgisayar", "computer science"],
                    "zorluk": "Kolay"
                  }}
                ]
                """,
                agent=self.agents["fill_blank"],
                expected_output=f"JSON formatında boşluk doldurma soruları - {question_distribution['bosluk_doldurma']} adet"
            )
            tasks.append(fill_task)
            individual_tasks.append(fill_task)
        
        if not individual_tasks:
             raise ValueError("Üretilecek soru bulunamadı. Lütfen tercihleri kontrol edin.")

        # --- JSON DOĞRULAMA GÖREVİ ---
        validation_task = Task(
            description=f"""
            Diğer ajanlardan gelen tüm soru çıktılarını JSONValidatorToolForQuestion kullanarak doğrula ve düzelt.
            
            Görevlerin:
            1. Her bir soru türü için gelen JSON çıktılarını kontrol et
            2. JSONValidatorToolForQuestion aracını kullanarak format hatalarını düzelt
            3. Eksik alanları tamamla
            4. Geçerli JSON formatına dönüştür
            5. Doğrulanmış çıktıları bir sonraki aşamaya hazırla
            
            **Doğrulama Kriterleri:**
            - Tüm JSON'lar geçerli format olmalı
            - Zorunlu alanlar eksik olmamalı
            - Soru metinleri boş olmamalı
            - Seçenekler tam olmalı (çoktan seçmeli için)
            
            JSONValidatorToolForQuestion aracını kullanarak her çıktıyı kontrol et ve düzelt.
            """,
            agent=self.agents["validator"],
            context=individual_tasks,
            expected_output="Doğrulanmış ve düzeltilmiş JSON formatında sorular"
        )
        tasks.append(validation_task)

        # --- KOORDİNASYON GÖREVİ ---
        coordination_task = Task(
            description=f"""
            Doğrulanmış soruları koordine et ve tek bir final JSON formatında birleştir.
            
            Görevler:
            1. Doğrulanmış soruların kalitesini kontrol et
            2. Tekrar eden soruları filtrele
            3. Zorluk dağılımını dengele
            4. Final test dosyasını oluştur
            5. JSONValidatorToolForQuestion ile son kontrol yap
            
            Kullanıcı tercihleri:
            - Toplam soru: {preferences.get('toplam_soru', 10)}
            - Soru türleri: {preferences.get('soru_turleri', [])}
            - Zorluk seviyesi: {preferences.get('zorluk_seviyesi', 'orta')}
            - Öğrenci seviyesi: {preferences.get('ogrenci_seviyesi', 'lise')}
            
            **ADIM-ADIM SÜREÇ:**
            ADIM 1: Doğrulanmış soruları topla
            ADIM 2: Kalite kontrolü yap
            ADIM 3: Final JSON formatını oluştur
            ADIM 4: JSONValidatorToolForQuestion ile son doğrulama yap
            ADIM 5: Final çıktıyı döndür
            
            **Final JSON Çıktı Formatı:**
            {{
                "document_info": {{
                    "analysis_date": "{datetime.now().isoformat()}",
                    "question_count": {preferences.get('toplam_soru', 0)},
                    "question_types": {preferences.get('soru_turleri', [])},
                    "difficulty_distribution": {{"kolay": 0, "orta": 0, "zor": 0}},
                    "student_level": "{preferences.get('ogrenci_seviyesi', 'lise')}",
                    "special_topics": {preferences.get('ozel_konular', [])},
                    "validation_status": "completed"
                }},
                "questions": {{
                    "coktan_secmeli": [...],
                    "klasik": [...],
                    "bosluk_doldurma": [...]
                }}
            }}
            """,
            agent=self.agents["coordinator"],
            context=[validation_task],
            expected_output="Final JSON test dosyası"
        )
        tasks.append(coordination_task)
        return tasks

    def run_crew_sync(self, crew):
        """Senkron crew çalıştırma fonksiyonu"""
        try:
            result = crew.kickoff()
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def run_crew_async(self, crew):
        """Asenkron crew çalıştırma fonksiyonu"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self.executor, self.run_crew_sync, crew)
        return result

    def _extract_crew_output_content(self, crew_output):
        """CrewOutput objesinden string içeriği çıkarır"""
        try:
            # CrewOutput objesinin string representation'ını al
            if hasattr(crew_output, 'raw'):
                return crew_output.raw
            elif hasattr(crew_output, 'result'):
                return crew_output.result
            elif hasattr(crew_output, 'output'):
                return crew_output.output
            else:
                # Son çare olarak string'e çevir
                return str(crew_output)
        except Exception as e:
            print(f"❌ CrewOutput içerik çıkarma hatası: {e}")
            return str(crew_output)

    async def generate_questions(self, document_content: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Ana soru üretme fonksiyonu - CrewOutput hatası düzeltildi."""
        try:
            print("🔄 Crew AI (Detaylı Görev Yapısı) ile soru üretimi başlatılıyor...")
            await self.send_workflow_message("CrewAI-Manager", "🚀 Soru üretim sistemi başlatılıyor", {
                "preferences": preferences,
                "document_length": len(document_content)
            })
            
            tasks = self._create_tasks(document_content, preferences)
            crew = Crew(
                agents=list(self.agents.values()),
                tasks=tasks,
                verbose=True,  # Boolean değer
                process=Process.sequential
            )
            
            await self.send_progress_update("🔄 CrewAI ajanları çalışıyor...")
            result = await self.run_crew_async(crew)
            
            if not result["success"]:
                raise Exception(result["error"])
            
            await self.send_workflow_message("CrewAI-Manager", "✅ Soru üretimi tamamlandı!")
            print("✅ Crew AI soru üretimi tamamlandı!")
            
            # *** HATA DÜZELTMESİ: CrewOutput objesini düzgün işle ***
            crew_output = result["result"]
            
            # CrewOutput objesinden string içeriğini çıkar
            final_result_str = self._extract_crew_output_content(crew_output)
            
            print(f"🔍 CrewOutput türü: {type(crew_output)}")
            print(f"📝 Raw output (ilk 200 karakter): {final_result_str[:200]}...")
            
            # String içeriğini JSON'a çevir
            try:
                # JSON temizleme
                if '```json' in final_result_str:
                    final_result_str = final_result_str.split('```json')[1].split('```')[0]
                elif '```' in final_result_str:
                    # Başka markdown blokları varsa da temizle
                    parts = final_result_str.split('```')
                    for part in parts:
                        if part.strip().startswith('{') or part.strip().startswith('['):
                            final_result_str = part.strip()
                            break
                
                final_result_str = final_result_str.strip()
                
                # JSON parse et
                parsed_result = json.loads(final_result_str)
                
                # Basit format kontrolü
                if isinstance(parsed_result, dict) and "questions" in parsed_result:
                    return parsed_result
                else:
                    # Fallback: basit format oluştur
                    return {
                        "document_info": {
                            "analysis_date": datetime.now().isoformat(),
                            "question_count": preferences.get('toplam_soru', 0),
                            "question_types": preferences.get('soru_turleri', []),
                            "difficulty_distribution": {"kolay": 0, "orta": 0, "zor": 0},
                            "student_level": preferences.get('ogrenci_seviyesi', 'lise'),
                            "special_topics": preferences.get('ozel_konular', [])
                        },
                        "questions": parsed_result if isinstance(parsed_result, dict) else {"coktan_secmeli": []},
                        "raw_output": final_result_str
                    }
                    
            except (json.JSONDecodeError, IndexError) as e:
                print(f"❌ CrewAI çıktısı JSON formatında değil: {e}")
                print(f"🔍 Raw output: {final_result_str}")
                return {
                    "error": "Soru üretilemedi. JSON format hatası.",
                    "raw_output": final_result_str,
                    "parse_error": str(e)
                }
            
        except Exception as e:
            print(f"❌ Crew AI çalıştırılırken bir hata oluştu: {str(e)}")
            await self.send_workflow_message("CrewAI-Manager", f"❌ Hata: {str(e)}")
            return {"error": f"Soru üretimi sırasında bir hata oluştu: {e}"}


# AsyncCrewAIQuestionHandler sınıfı - WebSocket desteği ile
class AsyncCrewAIQuestionHandler:
    def __init__(self, websocket_callback=None):
        self.websocket_callback = websocket_callback
        self.crew_system = None

    async def send_workflow_message(self, agent_name: str, message: str, data: Dict = None):
        """WebSocket üzerinden workflow mesajları gönder"""
        if self.websocket_callback:
            workflow_message = {
                "type": "workflow_message",
                "agent": agent_name,
                "message": message,
                "data": data or {},
                "timestamp": datetime.utcnow().isoformat()
            }
            await self.websocket_callback(json.dumps(workflow_message))

    async def generate_questions_workflow(self, document_content: str, preferences: Dict[str, Any]) -> Dict:
        """Soru üretimi workflow'u"""
        await self.send_workflow_message("CrewAI-QuestionGenerator", "🚀 Multi-Agent soru üretim sistemi başlatılıyor", {
            "preferences": preferences,
            "agents": ["MultipleChoiceExpert", "ClassicQuestionExpert", "FillBlankExpert", "Coordinator"],
            "mode": "async"
        })

        # CrewAI sistemini başlat
        self.crew_system = CrewAISystem(
            api_key=Config.GOOGLE_API_KEY,
            websocket_callback=self.websocket_callback
        )

        # Soru üretimi işlemini başlat
        result = await self.crew_system.generate_questions(document_content, preferences)

        # Başarılı sonuç kontrolü
        if not result.get("error"):
            question_count = 0
            question_types = []
            
            if "document_info" in result:
                question_count = result["document_info"].get("question_count", 0)
                question_types = result["document_info"].get("question_types", [])
            
            await self.send_workflow_message("CrewAI-QuestionGenerator", "✅ Multi-Agent soru üretim workflow'u tamamlandı", {
                "questions_generated": question_count,
                "question_types": question_types
            })

        return result