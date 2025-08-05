"""
CrewAI için özel araçlar
"""
from typing import Dict, Any, List
import json
import re
from crewai.tools import BaseTool

class JSONValidatorToolForQuestion(BaseTool):
    name: str = "JSON Validator"
    description: str = "JSON formatının geçerliliğini kontrol eder ve düzeltir"
    
    def _run(self, json_string: str) -> str:
        """JSON string'ini kontrol et ve geçerli hale getir"""
        try:
            # JSON'u parse etmeye çalış
            parsed = json.loads(json_string)
            # Başarılıysa, düzgün formatlanmış şekilde döndür
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except json.JSONDecodeError as e:
            # Hata varsa, basit düzeltmeler yap
            return self._fix_common_json_errors(json_string)
    
    def _fix_common_json_errors(self, json_string: str) -> str:
        """Yaygın JSON hatalarını düzelt"""
        fixed = json_string
        
        # Türkçe karakterler için özel escape işlemleri
        fixed = fixed.replace('\\"', '"')  # Çift escape'leri düzelt
        fixed = fixed.replace('\n', '\\n')  # Yeni satırları escape et
        fixed = fixed.replace('\r', '\\r')  # Carriage return'leri escape et
        fixed = fixed.replace('\t', '\\t')  # Tab'ları escape et
        
        # Eksik tırnak işaretlerini ekle
        fixed = re.sub(r'(\w+):', r'"\1":', fixed)
        
        # Son virgülü kaldır
        fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
        
        # Tek tırnak'ları çift tırnak yap
        fixed = fixed.replace("'", '"')
        
        # Geçersiz escape karakterlerini temizle
        fixed = re.sub(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', fixed)
        
        # Tırnak içindeki tırnak işaretlerini escape et
        def escape_quotes_in_strings(match):
            content = match.group(1)
            escaped = content.replace('"', '\\"')
            return f'"{escaped}"'
        
        # String değerlerindeki tırnak işaretlerini düzelt
        fixed = re.sub(r'"([^"]*(?:[^\\]"[^"]*)*)"', escape_quotes_in_strings, fixed)
        
        try:
            parsed = json.loads(fixed)
            return json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception as e:
            # Son çare: Minimal geçerli JSON döndür
            print(f"JSON düzeltme hatası: {e}")
            return json.dumps({
                "error": "JSON format hatası - düzeltilemedi", 
                "original_error": str(e),
                "partial_content": fixed[:200] + "..." if len(fixed) > 200 else fixed
            }, ensure_ascii=False, indent=2)

class QuestionCounterTool(BaseTool):
    name: str = "Question Counter"
    description: str = "Oluşturulan soru sayısını sayar ve kontrol eder"
    
    def _run(self, questions_data: str) -> str:
        """Soru sayısını kontrol et"""
        try:
            if isinstance(questions_data, str):
                data = json.loads(questions_data)
            else:
                data = questions_data
            
            counts = {}
            total = 0
            
            if "questions" in data:
                for q_type, questions in data["questions"].items():
                    if isinstance(questions, list):
                        counts[q_type] = len(questions)
                        total += len(questions)
            
            result = {
                "total_questions": total,
                "by_type": counts,
                "status": "counted"
            }
            
            return json.dumps(result, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({"error": str(e), "status": "error"})

class QuestionDeduplicatorTool(BaseTool):
    name: str = "Question Deduplicator"
    description: str = "Tekrar eden soruları tespit eder ve kaldırır"
    
    def _run(self, questions_data: str) -> str:
        """Tekrar eden soruları temizle"""
        try:
            if isinstance(questions_data, str):
                data = json.loads(questions_data)
            else:
                data = questions_data
            
            if "questions" not in data:
                return questions_data
            
            cleaned_data = data.copy()
            duplicates_removed = 0
            
            for q_type, questions in data["questions"].items():
                if isinstance(questions, list):
                    unique_questions = []
                    seen_questions = set()
                    
                    for question in questions:
                        # Soru metnini normalize et
                        q_text = str(question.get("soru", "")).lower().strip()
                        
                        if q_text and q_text not in seen_questions:
                            unique_questions.append(question)
                            seen_questions.add(q_text)
                        else:
                            duplicates_removed += 1
                    
                    cleaned_data["questions"][q_type] = unique_questions
            
            # Temizlik bilgisini ekle
            if "document_info" in cleaned_data:
                cleaned_data["document_info"]["duplicates_removed"] = duplicates_removed
            
            return json.dumps(cleaned_data, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e), "status": "error"})

class QuestionQualityTool(BaseTool):
    name: str = "Question Quality Checker"
    description: str = "Soruların kalitesini değerlendirir"
    
    def _run(self, questions_data: str) -> str:
        """Soru kalitesini değerlendir"""
        try:
            if isinstance(questions_data, str):
                data = json.loads(questions_data)
            else:
                data = questions_data
            
            quality_report = {
                "overall_score": 0,
                "issues": [],
                "suggestions": []
            }
            
            if "questions" in data:
                total_score = 0
                total_questions = 0
                
                for q_type, questions in data["questions"].items():
                    if isinstance(questions, list):
                        for question in questions:
                            score = self._evaluate_question(question, q_type)
                            total_score += score
                            total_questions += 1
                
                if total_questions > 0:
                    quality_report["overall_score"] = total_score / total_questions
            
            return json.dumps(quality_report, ensure_ascii=False, indent=2)
            
        except Exception as e:
            return json.dumps({"error": str(e), "status": "error"})
    
    def _evaluate_question(self, question: Dict[str, Any], q_type: str) -> float:
        """Tek bir soruyu değerlendir"""
        score = 0.0
        
        # Soru metni kontrolü
        if "soru" in question and len(question["soru"]) > 10:
            score += 0.3
        
        # Tip-spesifik kontroller
        if q_type == "coktan_secmeli":
            if "secenekler" in question and len(question["secenekler"]) == 4:
                score += 0.3
            if "dogru_cevap" in question:
                score += 0.2
        elif q_type == "klasik":
            if "ornek_cevap" in question or "cevap" in question:
                score += 0.3
        elif q_type == "bosluk_doldurma":
            if "___" in question.get("soru", "") or "_" in question.get("soru", ""):
                score += 0.3
        
        # Zorluk seviyesi kontrolü
        if "zorluk" in question:
            score += 0.2
        
        return min(score, 1.0)  # Maksimum 1.0
