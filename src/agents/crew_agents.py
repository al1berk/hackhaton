# src/agents/crew_agents.py (DÜZELTME: Test oluşturma sorunları giderildi)

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
            "true_false": Agent(
                role="Doğru-Yanlış Soru Uzmanı",
                goal="Verilen metne ve tercihlere göre etkili doğru-yanlış soruları oluşturmak ve JSON formatını doğrulamak.",
                backstory="Sen doğru-yanlış soruları konusunda uzman bir öğretmensin. Net ve kesin yargılar içeren, yanıltıcı olmayan sorular hazırlıyorsun ve JSONValidatorToolForQuestion ile format doğruluğunu sağlıyorsun.",
                llm=self.llm, 
                tools=self.tools, 
                verbose=True
            ),
            "validator": Agent(
                role="JSON Format Doğrulama Uzmanı",
                goal="Üretilen tüm soruların JSON formatını kontrol etmek ve düzeltmek.",
                backstory="Sen JSON format doğrulama konusunda uzman bir teknisyensin. Diğer ajanlardan gelen çıktıları JSONValidatorToolForQuestion kullanarak kontrol eder ve geçerli JSON formatına dönüştürsün.",
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
        # Eğer soru_turleri dict ise doğrudan onu döndür
        question_types = preferences.get("soru_turleri", {})
        if isinstance(question_types, dict):
            return question_types
        # Eski davranış (liste ise)
        total_questions = preferences.get("toplam_soru", 10)
        if not question_types:
            return {}
        base_count = total_questions // len(question_types)
        remainder = total_questions % len(question_types)
        distribution = {
            q_type: base_count + (1 if i < remainder else 0)
            for i, q_type in enumerate(question_types)
        }
        return distribution

    def _preprocess_document(self, document_content: str, max_chars: int = 15000) -> str:
        """Dokümanı CrewAI için uygun boyuta getirir"""
        if len(document_content) <= max_chars:
            return document_content
        
        print(f"📝 Doküman çok büyük ({len(document_content)} karakter), {max_chars} karaktere kısaltılıyor...")
        
        # İlk kısmı al ve mantıklı bir yerde kes
        truncated = document_content[:max_chars]
        
        # Son nokta veya paragraf sonunda kes
        last_period = truncated.rfind('.')
        last_newline = truncated.rfind('\n\n')
        
        if last_period > max_chars * 0.8:  # %80'inden sonraki son nokta
            truncated = truncated[:last_period + 1]
        elif last_newline > max_chars * 0.7:  # %70'inden sonraki son paragraf
            truncated = truncated[:last_newline]
        
        print(f"✂️ Doküman {len(truncated)} karaktere kısaltıldı")
        return truncated

    def _create_tasks(self, document_content: str, preferences: Dict[str, Any]) -> List[Task]:
        """Kullanıcı tercihlerine göre her ajan için ayrı ve detaylı görevler oluşturur."""
        tasks = []
        individual_tasks = []
        question_distribution = self._calculate_question_distribution(preferences)

        # Dokümanı preprocessing'den geçir
        processed_content = self._preprocess_document(document_content)

        # --- ÇOKTAN SEÇMELİ GÖREVİ ---
        if question_distribution.get("coktan_secmeli", 0) > 0:
            mc_task = Task(
                description=f"""
                Verilen dokümandan {question_distribution['coktan_secmeli']} adet çoktan seçmeli soru oluştur.
                        
                Döküman içeriği: {processed_content[:3000]}...
                        
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
                        
                Döküman içeriği: {processed_content[:3000]}...
                        
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
                        
                Döküman içeriği: {processed_content[:3000]}...
                        
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
        
        # --- DOĞRU-YANLIŞ GÖREVİ ---
        if question_distribution.get("dogru_yanlis", 0) > 0:
            true_false_task = Task(
                description=f"""
                Verilen dokümandan {question_distribution['dogru_yanlis']} adet doğru-yanlış sorusu oluştur.
                        
                Döküman içeriği: {processed_content[:3000]}...
                        
                Zorluk seviyesi: {preferences.get('zorluk_seviyesi', 'orta')}
                Öğrenci seviyesi: {preferences.get('ogrenci_seviyesi', 'lise')}
                Özel konular: {preferences.get('ozel_konular', [])}
                        
                Her soru için:
                - Net ve kesin bir yargı içeren soru metni
                - Doğru/yanlış cevap (true/false)
                - Kısa açıklama
                - Zorluk seviyesi

                **ÇOK ÖNEMLİ ÇIKTI FORMATI:**
                Sadece aşağıdaki formata birebir uyan bir JSON listesi döndür.
                
                ADIM 1: Önce soruları oluştur
                ADIM 2: JSONValidatorToolForQuestion aracını kullanarak çıktını doğrula
                ADIM 3: Doğrulanmış JSON formatını döndür
                
                [
                  {{
                    "soru": "Net bir yargı içeren ifade. Örneğin: Yapay zeka sadece matematik problemlerini çözmek için kullanılır.",
                    "dogru_cevap": "false",
                    "aciklama": "Bu cevabın neden doğru veya yanlış olduğuna dair kısa açıklama.",
                    "zorluk": "Orta"
                  }}
                ]
                """,
                agent=self.agents["true_false"],
                expected_output=f"JSON formatında doğru-yanlış soruları - {question_distribution['dogru_yanlis']} adet"
            )
            tasks.append(true_false_task)
            individual_tasks.append(true_false_task)
        
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
        """Ana soru üretme fonksiyonu - Geliştirilmiş hata yönetimi ve timeout kontrolü."""
        try:
            print("🔄 Crew AI (Detaylı Görev Yapısı) ile soru üretimi başlatılıyor...")
            await self.send_workflow_message("CrewAI-Manager", "🚀 Soru üretim sistemi başlatılıyor", {
                "preferences": preferences,
                "document_length": len(document_content)
            })
            
            # Geliştirilmiş timeout ve retry ayarları
            max_retries = 2  # Retry sayısını azalt
            timeout_seconds = 480  # 8 dakika (çok daha uzun)
            
            # Doküman boyutu kontrol ve optimizasyon
            doc_length = len(document_content)
            if doc_length > 20000:
                await self.send_progress_update(f"📄 Büyük doküman tespit edildi ({doc_length:,} karakter), optimizasyon yapılıyor...")
                document_content = self._preprocess_document(document_content, 15000)
                await self.send_progress_update(f"✂️ Doküman {len(document_content):,} karaktere optimize edildi")
            
            for attempt in range(max_retries):
                try:
                    await self.send_progress_update(f"🔄 Deneme {attempt + 1}/{max_retries} - CrewAI test üretim ajanları başlatılıyor...")
                    
                    # Task oluşturma zamanını ölç
                    start_time = datetime.now()
                    tasks = self._create_tasks(document_content, preferences)
                    task_creation_time = (datetime.now() - start_time).total_seconds()
                    print(f"⏱️ Task oluşturma süresi: {task_creation_time:.2f} saniye")
                    
                    crew = Crew(
                        agents=list(self.agents.values()),
                        tasks=tasks,
                        verbose=True,
                        process=Process.sequential
                    )
                    
                    await self.send_progress_update(f"🤖 {len(tasks)} adet ajan görevi tanımlandı, çalıştırılıyor... (Tahmini süre: 5-8 dakika)")
                    
                    # Timeout ile crew çalıştır
                    try:
                        crew_start_time = datetime.now()
                        result = await asyncio.wait_for(
                            self.run_crew_async(crew), 
                            timeout=timeout_seconds
                        )
                        crew_duration = (datetime.now() - crew_start_time).total_seconds()
                        print(f"⏱️ CrewAI çalışma süresi: {crew_duration:.2f} saniye")
                        
                    except asyncio.TimeoutError:
                        if attempt < max_retries - 1:
                            await self.send_progress_update(f"⏰ Timeout ({timeout_seconds}s) - {attempt + 1}. deneme başarısız, kısaltılmış dokümanla tekrar deneniyor...")
                            # Bir sonraki denemede daha kısa doküman kullan
                            document_content = self._preprocess_document(document_content, 8000)
                            continue
                        else:
                            raise Exception(f"CrewAI işlemi {timeout_seconds//60} dakika timeout'a uğradı. Doküman çok büyük veya karmaşık olabilir.")
                    
                    if not result["success"]:
                        if attempt < max_retries - 1:
                            await self.send_progress_update(f"❌ CrewAI hatası, {attempt + 2}. deneme yapılıyor...")
                            continue
                        else:
                            raise Exception(f"CrewAI hatası: {result.get('error', 'Bilinmeyen hata')}")
                    
                    # Başarılı sonuç işleme
                    crew_output = result["result"]
                    final_result_str = self._extract_crew_output_content(crew_output)
                    
                    await self.send_progress_update("🔧 Test sonuçları işleniyor ve JSON formatı kontrol ediliyor...")
                    
                    # JSON temizleme ve parse etme
                    cleaned_json = self._clean_and_parse_json(final_result_str)
                    
                    if cleaned_json.get("error"):
                        if attempt < max_retries - 1:
                            await self.send_progress_update(f"🔧 JSON parse hatası, tekrar deneniyor...")
                            continue
                        else:
                            raise Exception(f"JSON parse hatası: {cleaned_json['error']}")
                    
                    # Başarılı sonuç
                    await self.send_workflow_message("CrewAI-Manager", "✅ Soru üretimi başarıyla tamamlandı!")
                    await self.send_progress_update("🎉 Test soruları hazır! Şimdi sunuluyor...")
                    return cleaned_json
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        await self.send_progress_update(f"❌ Hata: {str(e)[:100]}... - Tekrar deneniyor...")
                        await asyncio.sleep(3)  # Biraz daha uzun bekleme
                        continue
                    else:
                        raise e
            
        except Exception as e:
            error_msg = f"Soru üretimi sırasında hata: {str(e)}"
            print(f"❌ {error_msg}")
            await self.send_workflow_message("CrewAI-Manager", f"❌ Hata: {error_msg}")
            return {"error": error_msg}

    def _clean_and_parse_json(self, raw_output: str) -> Dict[str, Any]:
        """JSON temizleme ve parse etme - geliştirilmiş versiyon"""
        try:
            # Markdown blokları temizle
            cleaned = raw_output
            if '```json' in cleaned:
                cleaned = cleaned.split('```json')[1].split('```')[0]
            elif '```' in cleaned:
                parts = cleaned.split('```')
                for part in parts:
                    part = part.strip()
                    if part.startswith('{') or part.startswith('['):
                        cleaned = part
                        break
            
            cleaned = cleaned.strip()
            
            # JSON validator tool kullan
            validator = JSONValidatorToolForQuestion()
            validated_json = validator._run(cleaned)
            
            # Validator'dan gelen sonucu parse et
            parsed_result = json.loads(validated_json)
            
            # Eğer error alanı varsa hatayı döndür
            if isinstance(parsed_result, dict) and "error" in parsed_result:
                return {"error": f"JSON validation hatası: {parsed_result['error']}"}
            
            # Format kontrolü ve düzenleme
            if isinstance(parsed_result, dict) and "questions" in parsed_result:
                return parsed_result
            elif isinstance(parsed_result, list):
                # Liste formatında geldi, düzgün formata çevir
                return {
                    "document_info": {
                        "analysis_date": datetime.now().isoformat(),
                        "question_count": len(parsed_result),
                        "question_types": {"coktan_secmeli": len(parsed_result)},
                        "validation_status": "completed"
                    },
                    "questions": {"coktan_secmeli": parsed_result}
                }
            else:
                # Beklenmedik format
                return {
                    "document_info": {
                        "analysis_date": datetime.now().isoformat(),
                        "question_count": 0,
                        "question_types": {},
                        "validation_status": "format_error"
                    },
                    "questions": {},
                    "raw_output": cleaned,
                    "note": "Beklenmedik JSON formatı"
                }
                
        except Exception as e:
            return {"error": f"JSON işleme hatası: {str(e)}", "raw_content": raw_output[:500]}