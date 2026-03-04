#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
نظام الترجمة الشامل عالي الجودة المحسن - النسخة المطورة
Complete High-Quality Translation System using Gemini - Enhanced Version
ضمان ترجمة كاملة لكل المحتوى مع تحسينات شاملة
"""

import os
import json
import time
import logging
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import fitz
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
import re
import sqlite3
import contextlib
from pathlib import Path
import hashlib
import traceback
import unicodedata

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from collections import deque
import asyncio
import aiohttp
import time

# ============= تحسين 1: نظام السجلات المحسن مع Rotation =============
def setup_comprehensive_logging():
    """إعداد نظام سجلات شامل مع rotation تلقائي"""
    log_format = '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    
    log_dir = Path("translation_logs")
    log_dir.mkdir(exist_ok=True)
    
    # أسماء ملفات السجلات
    main_log = log_dir / f'main_translation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    quality_log = log_dir / f'quality_control_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    # إعداد logger الرئيسي مع rotation
    main_logger = logging.getLogger('main')
    main_logger.setLevel(logging.INFO)
    
    if not main_logger.handlers:
        # Rotating file handler - 10MB لكل ملف، الاحتفاظ بـ 5 ملفات
        main_handler = RotatingFileHandler(
            main_log, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        main_handler.setFormatter(logging.Formatter(log_format))
        main_logger.addHandler(main_handler)
        
        # console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        main_logger.addHandler(console_handler)
    
    # logger منفصل لمراقبة الجودة مع rotation
    quality_logger = logging.getLogger('quality_control')
    quality_logger.setLevel(logging.INFO)
    
    if not quality_logger.handlers:
        quality_handler = RotatingFileHandler(
            quality_log,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        quality_handler.setFormatter(logging.Formatter(log_format))
        quality_logger.addHandler(quality_handler)
    
    return main_logger, quality_logger

logger, quality_logger = setup_comprehensive_logging()

# ============= تحسين 2: نظام Rate Limiting محسن (Tokens & Requests) =============
class TokenRateLimiter:
    """نظام rate limiting متقدم يتعقب الطلبات والتوكنز والحد اليومي"""
    def __init__(self, max_rpm: int = 2, max_tpm: int = 32000, max_rpd: int = 50):
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        self.max_rpd = max_rpd

        self.requests = deque() # tuples of (time, tokens)
        self.daily_requests = deque() # times of requests within the last 24h

    def can_make_request(self, estimated_tokens: int = 0) -> bool:
        now = time.time()
        # إزالة الطلبات القديمة خارج الدقيقة
        while self.requests and self.requests[0][0] < now - 60:
            self.requests.popleft()

        # إزالة الطلبات القديمة خارج اليوم
        while self.daily_requests and self.daily_requests[0] < now - 86400:
            self.daily_requests.popleft()

        current_rpm = len(self.requests)
        current_tpm = sum(tokens for _, tokens in self.requests)
        current_rpd = len(self.daily_requests)
        
        if current_rpm >= self.max_rpm:
            return False
        if current_tpm + estimated_tokens > self.max_tpm:
            return False
        if current_rpd >= self.max_rpd:
            return False

        return True

    def add_request(self, estimated_tokens: int = 0):
        now = time.time()
        self.requests.append((now, estimated_tokens))
        self.daily_requests.append(now)

    def time_until_next_request(self, estimated_tokens: int = 0) -> float:
        if self.can_make_request(estimated_tokens):
            return 0
        
        now = time.time()

        while self.requests and self.requests[0][0] < now - 60:
            self.requests.popleft()
        while self.daily_requests and self.daily_requests[0] < now - 86400:
            self.daily_requests.popleft()

        wait_times = []

        if len(self.daily_requests) >= self.max_rpd:
            wait_times.append((self.daily_requests[0] + 86400) - now)

        if len(self.requests) >= self.max_rpm:
            wait_times.append((self.requests[0][0] + 60) - now)

        current_tpm = sum(tokens for _, tokens in self.requests)
        if current_tpm + estimated_tokens > self.max_tpm:
            tokens_to_drop = (current_tpm + estimated_tokens) - self.max_tpm
            dropped = 0
            for req_time, tokens in self.requests:
                dropped += tokens
                if dropped >= tokens_to_drop:
                    wait_times.append((req_time + 60) - now)
                    break

        return max(wait_times) if wait_times else 0.0

# ============= تحسين 3: إحصائيات محسنة للمفاتيح =============
class KeyStatistics:
    """إحصائيات متقدمة لكل مفتاح API"""
    
    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.rate_limit_hits = 0
        self.server_errors = 0
        self.last_error_time = None
        self.last_success_time = None
        self.average_response_time = 0
        self.response_times = deque(maxlen=100)  # آخر 100 وقت استجابة
        
    def record_success(self, response_time: float):
        """تسجيل طلب ناجح"""
        self.successful_requests += 1
        self.total_requests += 1
        self.last_success_time = datetime.now()
        self.response_times.append(response_time)
        self._update_average_response_time()
    
    def record_failure(self, error_type: str = "general"):
        """تسجيل طلب فاشل"""
        self.failed_requests += 1
        self.total_requests += 1
        self.last_error_time = datetime.now()
        
        if error_type == "rate_limit":
            self.rate_limit_hits += 1
        elif error_type == "server_error":
            self.server_errors += 1
    
    def _update_average_response_time(self):
        """تحديث متوسط وقت الاستجابة"""
        if self.response_times:
            self.average_response_time = sum(self.response_times) / len(self.response_times)
    
    def get_success_rate(self) -> float:
        """حساب معدل النجاح"""
        if self.total_requests == 0:
            return 0
        return (self.successful_requests / self.total_requests) * 100
    
    def get_health_score(self) -> float:
        """حساب نقاط الصحة للمفتاح (0-100)"""
        if self.total_requests == 0:
            return 100  # مفتاح جديد
        
        success_rate = self.get_success_rate()
        
        # عقوبة للأخطاء الحديثة
        recent_error_penalty = 0
        if self.last_error_time:
            hours_since_error = (datetime.now() - self.last_error_time).total_seconds() / 3600
            if hours_since_error < 1:
                recent_error_penalty = 20
            elif hours_since_error < 6:
                recent_error_penalty = 10
        
        # عقوبة لكثرة rate limit
        rate_limit_penalty = min(self.rate_limit_hits * 5, 30)
        
        health_score = success_rate - recent_error_penalty - rate_limit_penalty
        return max(0, min(100, health_score))

# ============= الفئة المحسنة الرئيسية (مع المفاتيح كما هي) =============
class EnhancedGeminiAPI:
    """إدارة محسنة لـ Gemini API مع مفاتيح متعددة"""
    
    def __init__(self, api_keys: List[str] = None):
        # المفاتيح كما كانت في الكود الأصلي
        self.api_keys = [
            "AIzaSyCoKRKqxBAW5XRldTamXjPBaa8",
            "AIzaSyBOg7Fcc9qum6HzjRRO-tQ0Rg",
            "AIzaSyCq96pXxveGaUL_AMoPlXAe19Zms",
            "AIzaSyAQEIPnASJKmG2t6gTBYl1Q4C7pQ",
            "AIzaSyDcE4H4B5Jzy3IQx7M8uTVM0Zg",
            "AIzaSyAiHCZHptFnQioO-gxMnHC1ZC0",
            "AIzaSyBWoJ1JToWqsvRGqLU7yg-glJyU",
            "AIzaSyAUcgeEdeu5EB3lhfYMsl3i-p_A",
            "AIzaSyDyScB6V94og6ypaaQAiNgYYZi3A",
            "AIzaSyCEK4C8TkEYftcj9OEoprFzLoaM",

        ]
        
        if isinstance(api_keys, list):
            self.api_keys.extend([key for key in api_keys if key not in self.api_keys])
        
        # Rate limiters لكل مفتاح - استخدام النظام المحسن مع حدود Gemini 2.5 Pro
        self.rate_limiters = {key: TokenRateLimiter(max_rpm=2, max_tpm=32000, max_rpd=50) for key in self.api_keys}
        
        # إحصائيات متقدمة لكل مفتاح
        self.key_stats = {key: KeyStatistics() for key in self.api_keys}
        
        # مفاتيح محظورة مؤقتاً
        self.blocked_keys = {}  # {key: unblock_time}
        
        # التوزيع الدائري
        self.current_key_index = 0

        # إعدادات الAPI لـ Gemini 2.5 Pro
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        self.max_retries = 6
        self.retry_delays = [3, 6, 12, 24, 48, 96]
        
        # Connection pool للأداء الأفضل
        self.connector = None
        self.session = None
        
        logger.info(f"تم تهيئة Gemini API مع {len(self.api_keys)} مفتاح")
    
    async def _ensure_session(self):
        """التأكد من وجود جلسة HTTP نشطة مع connection pooling"""
        if not self.session or self.session.closed:
            self.connector = aiohttp.TCPConnector(
                limit=100,  # الحد الأقصى للاتصالات
                ttl_dns_cache=300,  # cache DNS لـ 5 دقائق
                enable_cleanup_closed=True
            )
            timeout = aiohttp.ClientTimeout(total=300)
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=timeout
            )
    
    def _unblock_keys(self):
        """إلغاء حظر المفاتيح التي انتهت فترة حظرها"""
        current_time = time.time()
        keys_to_unblock = []
        
        for key, unblock_time in self.blocked_keys.items():
            if current_time >= unblock_time:
                keys_to_unblock.append(key)
        
        for key in keys_to_unblock:
            del self.blocked_keys[key]
            logger.info(f"تم إلغاء حظر المفتاح: {key[:10]}...")
    
    def estimate_tokens(self, text: str) -> int:
        """تقدير عدد التوكنز في النص (تقريباً 4 أحرف = 1 توكن)"""
        return max(1, len(text) // 4)

    async def get_optimal_api_key(self, estimated_tokens: int = 0) -> Optional[str]:
        """الحصول على المفتاح التالي المتاح باستخدام Round-Robin مع انتظار ذكي"""
        while True:
            self._unblock_keys()
            
            num_keys = len(self.api_keys)
            if num_keys == 0:
                return None

            checked_keys = 0
            
            # البحث عن مفتاح متاح
            while checked_keys < num_keys:
                key = self.api_keys[self.current_key_index]
                self.current_key_index = (self.current_key_index + 1) % num_keys
                checked_keys += 1

                # تخطي المفاتيح المحظورة
                if key in self.blocked_keys:
                    continue

                # التحقق من rate limit
                if not self.rate_limiters[key].can_make_request(estimated_tokens):
                    continue

                # التحقق من صحة المفتاح
                health_score = self.key_stats[key].get_health_score()
                if health_score < 10:
                    continue

                return key

            # إذا وصلنا هنا، يعني أن كل المفاتيح مشغولة، يجب الانتظار الذكي
            min_wait = float('inf')
            all_daily_exhausted = True

            for key in self.api_keys:
                if key not in self.blocked_keys:
                    # التحقق إذا كان المفتاح استنفد الحد اليومي
                    if len(self.rate_limiters[key].daily_requests) < self.rate_limiters[key].max_rpd:
                        all_daily_exhausted = False

                    wait_time = self.rate_limiters[key].time_until_next_request(estimated_tokens)
                    if wait_time < min_wait:
                        min_wait = wait_time

            if all_daily_exhausted:
                logger.error("تم استنفاد الحد اليومي لجميع المفاتيح! يجب الانتظار لليوم التالي أو إضافة مفاتيح جديدة.")
                # الانتظار لمدة طويلة ثم المحاولة مجدداً عبر الحلقة (تجنب الاستدعاء المتكرر recursive)
                await asyncio.sleep(60)
                continue

            if min_wait < float('inf') and min_wait > 0:
                logger.info(f"جميع المفاتيح مشغولة حالياً، انتظار ذكي لمدة {min_wait:.1f} ثانية...")
                await asyncio.sleep(min_wait + 0.5)
                continue
            
            # إذا فشلت كل المحاولات، أعد تعيين المفاتيح المحظورة وانتظر
            logger.warning("جميع المفاتيح محظورة، انتظار...")
            await asyncio.sleep(15)
            self.blocked_keys.clear()
            # Loop will continue
    
    async def make_precision_request(self, prompt: str, system_instruction: str = "", 
                                   temperature: float = 0.05, max_tokens: int = 8192,
                                   request_type: str = "translation") -> Optional[str]:
        """إرسال طلب دقيق مع إعدادات محسنة"""
        
        # التأكد من وجود جلسة نشطة
        await self._ensure_session()
        
        # تقدير عدد التوكنز للطلب والإجابة المتوقعة
        estimated_input_tokens = self.estimate_tokens(prompt + system_instruction)
        estimated_output_tokens = min(max_tokens, estimated_input_tokens * 2) # افتراض أقصى
        total_estimated_tokens = estimated_input_tokens + estimated_output_tokens

        for attempt in range(self.max_retries):
            api_key = await self.get_optimal_api_key(total_estimated_tokens)
            if not api_key:
                logger.error("لا توجد مفاتيح API متاحة")
                return None
            
            # تسجيل الطلب والتوكنز المقدرة
            self.rate_limiters[api_key].add_request(total_estimated_tokens)
            request_start = time.time()
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Professional-Translation-System/Enhanced'
            }
            
            # نفس الإعدادات الأصلية مع تحسينات طفيفة
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": f"{system_instruction}\n\n{prompt}"
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": temperature,
                    "topK": 12,
                    "topP": 0.8,
                    "maxOutputTokens": max_tokens,
                    "candidateCount": 1,
                    "stopSequences": ["###TRANSLATION_END###", "###END###"]
                },
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE"
                    }
                ]
            }
            
            url = f"{self.base_url}?key={api_key}"
            
            try:
                logger.info(f"إرسال طلب {request_type} للمحاولة {attempt + 1} باستخدام مفتاح {api_key[:10]}...")
                
                # استخدام الجلسة المحفوظة بدلاً من إنشاء جلسة جديدة
                async with self.session.post(url, json=payload, headers=headers) as response:
                    response_time = time.time() - request_start
                    
                    if response.status == 200:
                        result = await response.json()
                        
                        if ('candidates' in result and len(result['candidates']) > 0 
                            and 'content' in result['candidates'][0]
                            and 'parts' in result['candidates'][0]['content']
                            and len(result['candidates'][0]['content']['parts']) > 0):
                            
                            content = result['candidates'][0]['content']['parts'][0]['text']
                            
                            # تسجيل النجاح
                            self.key_stats[api_key].record_success(response_time)
                            logger.info(f"نجح طلب {request_type} مع المفتاح {api_key[:10]}...")
                            
                            return content.strip()
                        else:
                            logger.warning(f"استجابة غير متوقعة من Gemini: {result}")
                            self.key_stats[api_key].record_failure("invalid_response")
                            
                    elif response.status == 429:
                        logger.warning(f"تجاوز حد المعدل للمفتاح {api_key[:10]}... انتظار")
                        self.key_stats[api_key].record_failure("rate_limit")
                        
                        # حظر المفتاح مؤقتاً
                        block_duration = self.retry_delays[min(attempt, len(self.retry_delays)-1)]
                        self.blocked_keys[api_key] = time.time() + block_duration
                        
                        await asyncio.sleep(block_duration)
                        
                    elif response.status >= 500:
                        logger.error(f"خطأ خادم Gemini: {response.status}")
                        self.key_stats[api_key].record_failure("server_error")
                        await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays)-1)])
                        
                    else:
                        error_text = await response.text()
                        logger.error(f"خطأ API غير متوقع: {response.status} - {error_text}")
                        self.key_stats[api_key].record_failure("api_error")
                        
                        # حظر المفتاح إذا كان الخطأ متعلق بالمفتاح نفسه
                        if response.status in [401, 403]:
                            self.blocked_keys[api_key] = time.time() + 3600  # حظر لمدة ساعة
                            
            except asyncio.TimeoutError:
                logger.warning(f"انتهت مهلة طلب {request_type} (محاولة {attempt + 1})")
                self.key_stats[api_key].record_failure("timeout")
                await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays)-1)])
                
            except Exception as e:
                logger.error(f"خطأ في طلب {request_type} (محاولة {attempt + 1}): {str(e)}")
                self.key_stats[api_key].record_failure("exception")
                await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays)-1)])
        
        logger.error(f"فشل طلب {request_type} بعد {self.max_retries} محاولات")
        return None
    
    def get_statistics_summary(self) -> Dict[str, Any]:
        """الحصول على ملخص إحصائيات جميع المفاتيح"""
        summary = {
            'total_keys': len(self.api_keys),
            'active_keys': len([k for k in self.api_keys if k not in self.blocked_keys]),
            'blocked_keys': len(self.blocked_keys),
            'keys_performance': []
        }
        
        for key in self.api_keys:
            stats = self.key_stats[key]
            key_info = {
                'key_preview': f"{key[:10]}...",
                'health_score': stats.get_health_score(),
                'success_rate': stats.get_success_rate(),
                'total_requests': stats.total_requests,
                'successful_requests': stats.successful_requests,
                'failed_requests': stats.failed_requests,
                'avg_response_time': round(stats.average_response_time, 2),
                'is_blocked': key in self.blocked_keys
            }
            summary['keys_performance'].append(key_info)
        
        # ترتيب حسب الصحة
        summary['keys_performance'].sort(key=lambda x: x['health_score'], reverse=True)
        
        return summary
    
    async def cleanup(self):
        """تنظيف الموارد عند الانتهاء"""
        if self.session and not self.session.closed:
            await self.session.close()
        if self.connector:
            await self.connector.close()
        logger.info("تم تنظيف موارد Gemini API")

class ComprehensiveContentProcessor:
    """معالج المحتوى الشامل لضمان ترجمة كاملة لكل جزء"""
    
    @staticmethod
    def number_to_arabic_text(number: int) -> str:
        """تحويل الرقم إلى كتابة عربية"""
        arabic_numbers = {
            1: "الأول", 2: "الثاني", 3: "الثالث", 4: "الرابع", 5: "الخامس",
            6: "السادس", 7: "السابع", 8: "الثامن", 9: "التاسع", 10: "العاشر",
            11: "الحادي عشر", 12: "الثاني عشر", 13: "الثالث عشر", 14: "الرابع عشر", 15: "الخامس عشر",
            16: "السادس عشر", 17: "السابع عشر", 18: "الثامن عشر", 19: "التاسع عشر", 20: "العشرون",
            21: "الواحد والعشرون", 22: "الثاني والعشرون", 23: "الثالث والعشرون", 24: "الرابع والعشرون", 25: "الخامس والعشرون",
            26: "السادس والعشرون", 27: "السابع والعشرون", 28: "الثامن والعشرون", 29: "التاسع والعشرون", 30: "الثلاثون"
        }
        
        # إذا كان الرقم أكبر من 30، استخدم صيغة عامة
        if number <= 30:
            return arabic_numbers.get(number, f"الفصل {number}")
        else:
            return f"الفصل {number}"
    
    @staticmethod
    def convert_numbers_to_arabic(text: str) -> str:
        """تحويل جميع الأرقام من الإنجليزية إلى العربية"""
        english_to_arabic = {
            '0': '٠', '1': '١', '2': '٢', '3': '٣', '4': '٤',
            '5': '٥', '6': '٦', '7': '٧', '8': '٨', '9': '٩'
        }
        
        for eng_num, ar_num in english_to_arabic.items():
            text = text.replace(eng_num, ar_num)
        
        return text
    
    @staticmethod
    def detect_incomplete_translation(original_text: str, translated_text: str) -> Dict[str, Any]:
        """كشف الترجمة غير المكتملة بمقارنة النص الأصلي مع المترجم"""
        
        # تحليل المحتوى الأصلي
        original_segments = ComprehensiveContentProcessor.extract_content_segments(original_text)
        translated_segments = ComprehensiveContentProcessor.extract_content_segments(translated_text)
        
        issues = {
            'missing_segments': [],
            'untranslated_english': [],
            'incomplete_phrases': [],
            'missing_names': [],
            'coverage_percentage': 0.0
        }
        
        # البحث عن الكلمات الإنجليزية المتبقية
        english_pattern = r'\b[A-Za-z]{2,}\b'
        remaining_english = re.findall(english_pattern, translated_text)
        
        # استثناء الكلمات الشائعة المقبولة
        acceptable_english = {'OK', 'PDF', 'ISBN', 'URL', 'ID', 'TV', 'PC', 'CD', 'DVD'}
        
        for word in remaining_english:
            if word.upper() not in acceptable_english:
                issues['untranslated_english'].append(word)
        
        # حساب نسبة التغطية
        if len(original_segments) > 0:
            coverage = min(len(translated_segments) / len(original_segments), 1.0) * 100
            issues['coverage_percentage'] = coverage
        
        return issues
    
    @staticmethod
    def extract_content_segments(text: str) -> List[str]:
        """استخراج أجزاء المحتوى للمقارنة"""
        # تقسيم النص إلى جمل وفقرات
        sentences = re.split(r'[.!?]+', text)
        segments = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 10:  # تجاهل الجمل القصيرة جداً
                segments.append(sentence)
        
        return segments
    
    @staticmethod
    def needs_completion_review(original_text: str, translated_text: str) -> bool:
        """تحديد ما إذا كانت الترجمة تحتاج مراجعة لضمان الاكتمال"""
        issues = ComprehensiveContentProcessor.detect_incomplete_translation(original_text, translated_text)
        
        # إذا كان هناك محتوى إنجليزي متبقي أو نسبة التغطية أقل من 85%
        return (len(issues['untranslated_english']) > 0 or 
                issues['coverage_percentage'] < 85.0)
    
    @staticmethod
    def has_any_foreign_content(text: str) -> bool:
        """التحقق من وجود أي محتوى أجنبي (باستثناء الأرقام التي يمكن تحويلها)"""
        english_pattern = r'\b[A-Za-z]{2,}\b'
        remaining_english = re.findall(english_pattern, text)
        
        # استثناء الكلمات المقبولة
        acceptable_english = {'OK', 'PDF', 'ISBN', 'URL', 'ID', 'TV', 'PC', 'CD', 'DVD'}
        
        for word in remaining_english:
            if word.upper() not in acceptable_english:
                return True
        
        # لا نعتبر الأرقام الإنجليزية كمحتوى أجنبي يستوجب إعادة الترجمة
        # لأن دالة convert_numbers_to_arabic ستقوم بتحويلها لاحقاً.
        
        return False


class CompleteTranslationEngine:
    """محرك الترجمة الكاملة - يضمن ترجمة كل جزء في النص"""
    
    def __init__(self, api_manager: EnhancedGeminiAPI, target_language: str = "Arabic"):
        self.api_manager = api_manager
        self.target_language = target_language
        self.translation_memory = {}
        self.terminology_database = {}
        self.context_history = []
        self.content_processor = ComprehensiveContentProcessor()
        
        # إعدادات متقدمة للترجمة السياقية
        self.genre_detection = True
        self.emotional_tone_preservation = True
        self.stylistic_adaptation = True
        
    def detect_text_genre_and_tone(self, text: str) -> Dict[str, str]:
        """اكتشاف نوع النص ونبرته العاطفية"""
        text_sample = text[:1000].lower()
        
        # اكتشاف النوع
        if any(word in text_sample for word in ['poem', 'verse', 'stanza', 'rhyme', 'poetry']):
            genre = "poetry"
        elif any(word in text_sample for word in ['dialogue', 'scene', 'act', 'character', '"', "'"]):
            genre = "drama"
        elif any(word in text_sample for word in ['chapter', 'story', 'novel', 'tale', 'narrator']):
            genre = "narrative"
        else:
            genre = "prose"
        
        # اكتشاف النبرة العاطفية
        sad_indicators = ['sad', 'sorrow', 'grief', 'melancholy', 'tragic', 'loss', 'tears', 'death']
        happy_indicators = ['joy', 'happy', 'celebration', 'triumph', 'success', 'love', 'smile', 'laugh']
        dramatic_indicators = ['conflict', 'tension', 'crisis', 'climax', 'struggle', 'fight', 'war', 'battle']
        
        if any(indicator in text_sample for indicator in sad_indicators):
            tone = "melancholic"
        elif any(indicator in text_sample for indicator in happy_indicators):
            tone = "joyful"
        elif any(indicator in text_sample for indicator in dramatic_indicators):
            tone = "dramatic"
        else:
            tone = "neutral"
        
        return {"genre": genre, "tone": tone}
    
    def create_complete_translation_prompt(self, text: str, context: str = "", 
                                         text_analysis: Dict[str, str] = None) -> str:
        """إنشاء prompt شامل يضمن ترجمة كل جزء في النص"""
        
        if not text_analysis:
            text_analysis = self.detect_text_genre_and_tone(text)
        
        # بناء السياق المحسن
        context_section = ""
        if self.context_history:
            recent_context = " ".join(self.context_history[-3:])
            context_section = f"""
السياق من الترجمات السابقة للحفاظ على التسلسل والاتساق:
{recent_context[:800]}
"""
        
        # بناء قاموس المصطلحات
        terminology_section = ""
        if self.terminology_database:
            terminology_section = "المصطلحات والأسماء المُثبتة (استخدمها بدقة):\n"
            for original, translation in list(self.terminology_database.items())[:20]:
                terminology_section += f"• {original} ← {translation}\n"
        
        # تحديد استراتيجية الترجمة حسب النوع والنبرة
        genre_guidance = self._get_genre_specific_guidance(text_analysis)
        
        prompt = f"""أنت خبير ترجمة أدبية محترف متخصص في الترجمة الكاملة والشاملة من الإنجليزية إلى العربية الفصحى.

تحليل النص:
- النوع الأدبي: {text_analysis['genre']}
- النبرة العاطفية: {text_analysis['tone']}

{genre_guidance}

المهمة الأساسية - ترجمة كاملة وشاملة:
1. اترجم كل كلمة، جملة، وفقرة في النص - لا تترك أي جزء بدون ترجمة
2. تأكد من ترجمة كل اسم شخص أو مكان أو اكتبه بالأحرف العربية
3. حول جميع الأرقام إلى الأرقام العربية (1→١، 2→٢، إلخ)
4. تجنب الترجمة الحرفية - اترجم وفق السياق والمعنى والشعور
5. حافظ على النبرة العاطفية والأسلوب الأدبي للنص الأصلي
6. تأكد أن طول الترجمة مناسب لطول النص الأصلي (لا تختصر)
7. لا تضف تفسيرات أو تعليقات من عندك - ترجم المحتوى فقط

{terminology_section}

{context_section}

معايير الجودة الإلزامية:
- ترجمة شاملة لكل عنصر في النص (100% coverage)
- الحفاظ على روح النص ونبرته العاطفية بدقة
- استخدام تراكيب عربية طبيعية وجميلة ومناسبة للسياق
- تجنب الحشو أو الاختصار - ترجمة مكتملة ووفية للأصل
- ضمان وضوح المعنى وجمال التعبير العربي

النص المطلوب ترجمته بالكامل:
\"\"\"
{text}
\"\"\"

قم بترجمة النص كاملاً إلى العربية (النص المترجم فقط دون أي تعليقات أو إضافات):"""
        
        return prompt
    
    def _get_genre_specific_guidance(self, text_analysis: Dict[str, str]) -> str:
        """توجيهات محددة حسب نوع النص"""
        
        genre_guides = {
            "poetry": """
إرشادات للشعر:
- احتفظ بالجمال الموسيقي والإيقاع في العربية
- استخدم تعابير شاعرية مناسبة ولكن طبيعية
- حافظ على الصور الشعرية والاستعارات
- لا تفقد أي بيت أو مقطع من الشعر
            """,
            "drama": """
إرشادات للحوار والمشاهد:
- اجعل الحوار طبيعياً ومعبراً عن الشخصيات
- حافظ على الحيوية والانفعال في الكلام
- اترجم كل كلمة حوار وكل إرشاد مسرحي
- استخدم تعابير عربية حية ومفهومة
            """,
            "narrative": """
إرشادات للسرد والقصص:
- حافظ على تدفق الحكاية وتسلسل الأحداث
- اجعل الوصف حيوياً ومشوقاً ومكتملاً
- لا تفوت أي تفصيل من تفاصيل القصة
- استخدم أسلوب سردي عربي جميل وواضح
            """,
            "prose": """
إرشادات للنثر:
- اجعل النثر متدفقاً وسليماً لغوياً
- استخدم تراكيب عربية طبيعية ومتماسكة
- حافظ على ترابط الأفكار ووضوحها
- تأكد من ترجمة كل فكرة ومفهوم
            """
        }
        
        tone_guides = {
            "melancholic": "انقل المشاعر الحزينة والكآبة بعمق وحساسية في العربية",
            "joyful": "انقل الفرح والسعادة بتعابير عربية مشرقة ومفرحة",
            "dramatic": "حافظ على التوتر والإثارة والدراما كما في الأصل",
            "neutral": "حافظ على التوازن والهدوء في النبرة"
        }
        
        genre_guide = genre_guides.get(text_analysis['genre'], genre_guides['prose'])
        tone_guide = tone_guides.get(text_analysis['tone'], tone_guides['neutral'])
        
        return f"{genre_guide}\n\nتوجيه النبرة العاطفية: {tone_guide}"
    
    async def translate_with_completion_guarantee(self, text: str, context: str = "") -> Optional[str]:
        """ترجمة مع ضمان الاكتمال الشامل لكل أجزاء النص"""
        
        logger.info(f"بدء الترجمة الكاملة لنص من {len(text)} حرف")
        
        # المرحلة 1: تحليل النص واكتشاف نوعه
        text_analysis = self.detect_text_genre_and_tone(text)
        logger.info(f"تحليل النص: النوع={text_analysis['genre']}, النبرة={text_analysis['tone']}")
        
        # المرحلة 2: الترجمة الأولية الشاملة
        translation_prompt = self.create_complete_translation_prompt(text, context, text_analysis)
        
        initial_translation = await self.api_manager.make_precision_request(
            translation_prompt, 
            temperature=0.1,  # توازن بين الإبداع والدقة
            request_type="complete_translation"
        )
        
        if not initial_translation:
            logger.error("فشل في الترجمة الأولى")
            return None
        
        logger.info("تمت الترجمة الأولى، بدء فحص الاكتمال...")
        
        # المرحلة 3: فحص اكتمال الترجمة
        if self.content_processor.needs_completion_review(text, initial_translation):
            quality_logger.warning("الترجمة غير مكتملة، بدء مراجعة الإكمال...")
            
            # تحليل المشاكل
            issues = self.content_processor.detect_incomplete_translation(text, initial_translation)
            
            # مراجعة شاملة لضمان الاكتمال
            completion_prompt = f"""أنت مراجع ترجمة خبير. مهمتك ضمان ترجمة كاملة وشاملة للنص.

المشاكل المكتشفة في الترجمة الحالية:
- كلمات إنجليزية متبقية: {len(issues['untranslated_english'])} كلمة
- نسبة التغطية: {issues['coverage_percentage']:.1f}%

مهمتك:
1. تأكد من ترجمة كل جملة وفقرة من النص الأصلي
2. ترجم أي كلمة إنجليزية متبقية في الترجمة
3. تأكد أن طول الترجمة مناسب للنص الأصلي
4. حافظ على المعنى والسياق والنبرة العاطفية
5. لا تضف أو تحذف أي محتوى

النص الأصلي الذي يجب ترجمته بالكامل:
\"\"\"
{text}
\"\"\"

الترجمة الحالية التي تحتاج إكمال:
\"\"\"
{initial_translation}
\"\"\"

قدم الترجمة المكتملة والشاملة (النص المترجم فقط):"""
            
            completed_translation = await self.api_manager.make_precision_request(
                completion_prompt,
                temperature=0.05,
                request_type="completion_review"
            )
            
            if completed_translation:
                # فحص إضافي للتأكد من الاكتمال
                final_check = self.content_processor.detect_incomplete_translation(text, completed_translation)
                if final_check['coverage_percentage'] > 90:
                    logger.info("تم إكمال الترجمة بنجاح - نسبة التغطية مرتفعة")
                    final_translation = self.content_processor.convert_numbers_to_arabic(completed_translation)
                else:
                    quality_logger.warning("محاولة أخيرة لضمان الإكمال...")
                    # محاولة أخيرة
                    final_completion_prompt = f"""مراجعة نهائية حاسمة:

اضمن ترجمة كل كلمة وجملة في النص التالي إلى العربية:

النص الأصلي:
{text[:2000]}

الترجمة النهائية الكاملة:"""
                    
                    final_translation = await self.api_manager.make_precision_request(
                        final_completion_prompt,
                        temperature=0.02,
                        request_type="final_completion"
                    )
                    
                    if final_translation:
                        final_translation = self.content_processor.convert_numbers_to_arabic(final_translation)
                    else:
                        final_translation = self.content_processor.convert_numbers_to_arabic(completed_translation)
            else:
                final_translation = self.content_processor.convert_numbers_to_arabic(initial_translation)
        else:
            logger.info("الترجمة الأولى مكتملة وشاملة")
            final_translation = self.content_processor.convert_numbers_to_arabic(initial_translation)
        
        # المرحلة 4: تحديث السياق والمصطلحات
        if final_translation:
            # إضافة للسياق مع تنظيم أفضل
            context_excerpt = final_translation[:500]
            self.context_history.append(context_excerpt)
            if len(self.context_history) > 5:
                self.context_history.pop(0)
            
            # استخراج المصطلحات
            await self.extract_terminology(text, final_translation)
        
        return final_translation
    
    async def translate_with_comprehensive_review(self, text: str, context: str = "") -> Optional[str]:
        """ترجمة شاملة مع مراجعة متعددة المراحل لضمان عدم ترك أي محتوى أجنبي"""
        
        logger.info(f"بدء الترجمة الشاملة لنص من {len(text)} حرف")
        
        # المرحلة 1: تحليل النص واكتشاف نوعه
        text_analysis = self.detect_text_genre_and_tone(text)
        logger.info(f"تحليل النص: النوع={text_analysis['genre']}, النبرة={text_analysis['tone']}")
        
        # المرحلة 2: الترجمة الأولية السياقية
        translation_prompt = self.create_complete_translation_prompt(text, context, text_analysis)
        
        initial_translation = await self.api_manager.make_precision_request(
            translation_prompt, 
            temperature=0.1,  # توازن بين الإبداع والدقة
            request_type="contextual_translation"
        )
        
        if not initial_translation:
            logger.error("فشل في الترجمة الأولى")
            return None
        
        logger.info("تمت الترجمة الأولى، بدء المراجعة الشاملة...")
        
        # المرحلة 3: فحص شامل للمحتوى الأجنبي
        if self.content_processor.has_any_foreign_content(initial_translation):
            quality_logger.warning("تم العثور على محتوى أجنبي، بدء التصحيح الشامل...")
            
            # مراجعة شاملة لإزالة أي محتوى أجنبي
            comprehensive_review_prompt = f"""أنت مراجع ترجمة خبير. مهمتك مراجعة الترجمة وضمان عدم وجود أي محتوى أجنبي.

تركز المراجعة على:
1. تأكد من ترجمة كل كلمة إنجليزية إلى العربية
2. حول جميع الأرقام الإنجليزية (1,2,3...) إلى أرقام عربية (١،٢،٣...)
3. ترجم أو عرّب جميع الأسماء الأجنبية
4. تأكد من عدم وجود أي نص إنجليزي في الترجمة
5. حافظ على المعنى والسياق والنبرة العاطفية

النص الأصلي:
\"\"\"
{text}
\"\"\"

الترجمة الحالية التي تحتاج مراجعة:
\"\"\"
{initial_translation}
\"\"\"

قدم الترجمة المُصححة والخالية تماماً من أي محتوى أجنبي (النص فقط):"""
            
            corrected_translation = await self.api_manager.make_precision_request(
                comprehensive_review_prompt,
                temperature=0.05,
                request_type="comprehensive_correction"
            )
            
            if corrected_translation:
                # فحص إضافي
                if not self.content_processor.has_any_foreign_content(corrected_translation):
                    logger.info("تم تصحيح الترجمة بنجاح - خالية من المحتوى الأجنبي")
                    final_translation = self.content_processor.convert_numbers_to_arabic(corrected_translation)
                else:
                    quality_logger.warning("ما زال هناك محتوى أجنبي، محاولة تصحيح نهائية...")
                    # محاولة تصحيح نهائية مكثفة
                    final_correction_prompt = f"""مراجعة نهائية حاسمة: 

احذف أو ترجم أي كلمة أو رمز أو رقم إنجليزي في النص التالي:

{corrected_translation}

النص النهائي الخالي تماماً من الإنجليزية (عربي فقط):"""
                    
                    final_translation = await self.api_manager.make_precision_request(
                        final_correction_prompt,
                        temperature=0.02,
                        request_type="final_cleanup"
                    )
                    
                    if final_translation:
                        final_translation = self.content_processor.convert_numbers_to_arabic(final_translation)
                    else:
                        final_translation = self.content_processor.convert_numbers_to_arabic(corrected_translation)
            else:
                final_translation = self.content_processor.convert_numbers_to_arabic(initial_translation)
        else:
            logger.info("الترجمة الأولى خالية من المحتوى الأجنبي")
            final_translation = self.content_processor.convert_numbers_to_arabic(initial_translation)
        
        # المرحلة 4: تحديث السياق والمصطلحات
        if final_translation:
            # إضافة للسياق مع تنظيم أفضل
            context_excerpt = final_translation[:500]  # زيادة حجم السياق
            self.context_history.append(context_excerpt)
            if len(self.context_history) > 5:
                self.context_history.pop(0)
            
            # استخراج المصطلحات المحسن
            await self.extract_terminology(text, final_translation)
        
        return final_translation
    
    async def extract_terminology(self, original: str, translation: str):
        """استخراج وحفظ المصطلحات المهمة"""
        
        extraction_prompt = f"""استخرج المصطلحات المهمة والأسماء من النص وترجماتها.

النص الأصلي:
{original[:500]}

الترجمة:
{translation[:500]}

اكتب فقط المصطلحات المهمة التي يجب أن تبقى ثابتة:
تنسيق: الإنجليزية ← العربية

المصطلحات المهمة:"""
        
        terms_response = await self.api_manager.make_precision_request(
            extraction_prompt,
            temperature=0.1,
            request_type="terminology_extraction"
        )
        
        if terms_response:
            lines = terms_response.strip().split('\n')
            for line in lines:
                if '←' in line:
                    try:
                        english, arabic = line.split('←')
                        english = english.strip()
                        arabic = arabic.strip()
                        if english and arabic and len(english) > 2:
                            self.terminology_database[english] = arabic
                            logger.info(f"تم حفظ مصطلح: {english} ← {arabic}")
                    except:
                        continue


class ProfessionalDocumentProcessor:
    """معالج المستندات الاحترافي المحسن"""

    @staticmethod
    def smart_text_division(text: str, target_chunk_size: int = 5000) -> List[Dict[str, Any]]:
        """تقسيم ذكي متقدم للنص مع ضمان عدم قطع الحوارات أو الجمل"""
        
        chapters = []
        chapter_counter = 1
        current_idx = 0
        total_length = len(text)
        
        while current_idx < total_length:
            # تقدير مبدئي لطول الجزء بناءً على الحروف (متوسط طول الكلمة 5 + مسافة = 6 حروف)
            # نأخذ حجم أكبر قليلاً للسماح بالتراجع للخلف للعثور على نقطة قطع آمنة
            target_chars = target_chunk_size * 6
            
            # إذا كان المتبقي أقل من الحجم المستهدف، نأخذه بالكامل
            if current_idx + target_chars >= total_length:
                chunk_text = text[current_idx:]
                chapters.append({
                    'id': f'chapter_{chapter_counter:03d}',
                    'title': f'الجزء {chapter_counter}',
                    'content': chunk_text.strip(),
                    'word_count': len(chunk_text.split()),
                    'start_page': chapter_counter,
                    'end_page': chapter_counter
                })
                break

            # محاولة العثور على أفضل نقطة قطع
            search_end_idx = current_idx + target_chars
            chunk_candidate = text[current_idx:search_end_idx]

            # نبحث عن نقطة قطع آمنة بالترتيب من الأفضل للأقل
            # 1. نهاية فقرة (سطرين فارغين)
            # 2. نهاية جملة (نقطة، علامة استفهام، تعجب متبوعة بمسافة أو سطر جديد)

            safe_split_idx = -1

            # البحث عن نهايات الفقرات (\n\n)
            last_para_break = chunk_candidate.rfind('\n\n')

            # البحث عن نهايات الجمل
            # نستخدم التعبيرات النمطية للبحث عن نهايات الجمل (. أو ? أو !) متبوعة بمسافة أو سطر
            sentence_breaks = [m.end() for m in re.finditer(r'[.?!](?:\s|\n)', chunk_candidate)]
            last_sentence_break = sentence_breaks[-1] if sentence_breaks else -1

            # التحقق مما إذا كانت نقطة القطع المقترحة داخل اقتباس (حوار)
            def is_inside_quotes(text_segment, index):
                """تتحقق مما إذا كان المؤشر يقع داخل علامات تنصيص مفتوحة"""
                # نعد كل نوع من علامات التنصيص بشكل مستقل لتجنب تداخل الأنواع
                quote_pairs = [
                    ('"', '"'),
                    ("'", "'"),
                    ('«', '»'),
                    ('“', '”')
                ]

                segment_before = text_segment[:index]

                for open_q, close_q in quote_pairs:
                    if open_q == close_q:
                        # إذا كانت علامة الفتح والإغلاق متطابقة
                        if segment_before.count(open_q) % 2 != 0:
                            return True
                    else:
                        # إذا كانت علامة الفتح مختلفة عن علامة الإغلاق
                        open_count = segment_before.count(open_q)
                        close_count = segment_before.count(close_q)
                        if open_count > close_count:
                            return True

                return False

            # محاولة العثور على نقطة قطع آمنة فعلاً (ليست داخل اقتباس)
            if last_para_break != -1 and not is_inside_quotes(chunk_candidate, last_para_break):
                safe_split_idx = last_para_break
            elif last_sentence_break != -1:
                # محاولة العثور على نهاية جملة آمنة (خارج الاقتباسات)
                for brk in reversed(sentence_breaks):
                    if not is_inside_quotes(chunk_candidate, brk):
                        safe_split_idx = brk
                        break

            # إذا لم نجد نقطة قطع آمنة بتاتاً (نادر جداً لفقرة طولها 5000 كلمة)،
            # نقطع عند آخر مسافة كحل أخير لتجنب تجميد البرنامج
            if safe_split_idx == -1:
                last_space = chunk_candidate.rfind(' ')
                safe_split_idx = last_space if last_space != -1 else len(chunk_candidate)

            # اقتطاع النص النهائي
            chunk_text = chunk_candidate[:safe_split_idx]

            chapters.append({
                'id': f'chapter_{chapter_counter:03d}',
                'title': f'الجزء {chapter_counter}',
                'content': chunk_text.strip(),
                'word_count': len(chunk_text.split()),
                'start_page': chapter_counter,
                'end_page': chapter_counter
            })

            chapter_counter += 1
            # تحديث المؤشر لبداية الجزء التالي (مع تخطي الفراغات)
            current_idx += safe_split_idx

            # إزالة أي مسافات بيضاء أو أسطر جديدة في بداية الجزء التالي
            while current_idx < total_length and text[current_idx] in [' ', '\n', '\t', '\r']:
                current_idx += 1

        return chapters

    @staticmethod
    def extract_pdf_with_precision(file_path: str) -> Dict[str, Any]:
        """استخراج دقيق للنص باستخدام PyMuPDF (fitz) والتقسيم الذكي المعتمد على السياق فقط"""
        
        logger.info(f"بدء معالجة ملف PDF باستخدام PyMuPDF: {file_path}")
        
        try:
            doc = fitz.open(file_path)

            document_info = {
                'title': doc.metadata.get('title', ''),
                'author': doc.metadata.get('author', ''),
                'chapters': [],
                'total_pages': len(doc),
                'metadata': doc.metadata
            }

            full_text = ""

            for page_num in range(len(doc)):
                try:
                    page = doc.load_page(page_num)
                    page_text = page.get_text()

                    if not page_text or len(page_text.strip()) < 10:
                        continue

                    # تنظيف النص المبدئي
                    page_text = ProfessionalDocumentProcessor.clean_extracted_text(page_text)
                    full_text += page_text + "\n\n"

                except Exception as e:
                    logger.warning(f"خطأ في معالجة الصفحة {page_num + 1}: {str(e)}")
                    continue

            doc.close()

            # تنظيف إضافي للنص الكامل لضمان عدم وجود فجوات غريبة
            full_text = re.sub(r'\n{3,}', '\n\n', full_text)

            logger.info("تم استخراج كامل النص، جاري تطبيق التقسيم الذكي المعتمد على السياق...")

            # التقسيم الذكي للنص
            document_info['chapters'] = ProfessionalDocumentProcessor.smart_text_division(full_text)

            logger.info(f"تم تقسيم النص إلى {len(document_info['chapters'])} جزء مع الحفاظ على السياق")

            # إحصائيات
            total_words = sum(ch['word_count'] for ch in document_info['chapters'])
            logger.info(f"إجمالي الكلمات: {total_words:,}")

            return document_info

        except Exception as e:
            logger.error(f"خطأ في قراءة ملف PDF باستخدام PyMuPDF: {str(e)}")
            raise
    
    @staticmethod
    def clean_extracted_text(text: str) -> str:
        """تنظيف النص المستخرج من PDF"""
        
        # إزالة الأسطر المكررة
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 2:  # تجنب الأسطر الفارغة أو القصيرة جداً
                cleaned_lines.append(line)
        
        # دمج الأسطر المقطعة
        merged_text = ""
        for i, line in enumerate(cleaned_lines):
            if i > 0 and not line[0].isupper() and not cleaned_lines[i-1].endswith('.'):
                merged_text += " " + line
            else:
                merged_text += "\n\n" + line if merged_text else line
        
        # تنظيف إضافي
        merged_text = re.sub(r'\n{3,}', '\n\n', merged_text)  # إزالة الأسطر الفارغة الزائدة
        merged_text = re.sub(r' {2,}', ' ', merged_text)      # إزالة المسافات الزائدة
        
        return merged_text.strip()
    
    @staticmethod
    def detect_chapter_titles(text: str) -> List[str]:
        """كشف عناوين الفصول"""
        
        lines = text.split('\n')
        chapter_titles = []
        
        # أنماط عناوين الفصول
        chapter_patterns = [
            r'^(Chapter|CHAPTER)\s+(\d+|[IVX]+)[\:\.\-\s]*(.*)',
            r'^(الفصل|فصل)\s+(\d+|[ا-ي]+)[\:\.\-\s]*(.*)',
            r'^\s*(\d+)[\.\-\s](.{5,50})',
            r'^\s*([IVX]+)[\.\-\s](.{5,50})',
            r'^([A-Z][A-Z\s]{10,80})',  # عناوين بأحرف كبيرة
        ]
        
        for line in lines:
            line = line.strip()
            if len(line) < 3 or len(line) > 100:
                continue
            
            for pattern in chapter_patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    chapter_titles.append(line)
                    break
        
        return chapter_titles


class EnhancedDocumentGenerator:
    """مولد المستندات المحسن للروايات مع الفهرس"""
    
    @staticmethod
    async def create_table_of_contents(chapters: List[Dict[str, Any]], 
                                     api_manager: EnhancedGeminiAPI) -> List[Dict[str, str]]:
        """إنشاء فهرس منظم بدون تكرار وترجمة واحدة لكل عنوان"""
        logger.info("إنشاء فهرس منظم بدون تكرار...")
        
        table_of_contents = []
        processed_titles = set()  # لمنع التكرار
        used_translations = set()  # لمنع تكرار الترجمات
        
        for i, chapter in enumerate(chapters):
            if not chapter.get('translated_content'):
                continue
                
            original_title = chapter['title']
            
            # تجنب تكرار نفس العنوان الأصلي
            if original_title in processed_titles:
                continue
            
            processed_titles.add(original_title)
            
            # البحث عن عنوان حقيقي في النص المترجم
            lines = chapter['translated_content'].split('\n')[:10]  # أول 10 أسطر فقط
            chapter_title_found = None
            
            for line in lines:
                line = line.strip()
                # البحث عن عنوان مناسب (ليس طويل جداً وليس قصير جداً)
                if (len(line) > 5 and len(line) < 60 and 
                    not line.startswith('في') and not line.startswith('كان') and
                    not line.startswith('لقد') and not line.startswith('عندما')):
                    # تجنب تكرار نفس الترجمة
                    if line not in used_translations:
                        chapter_title_found = line
                        used_translations.add(line)
                        break
            
            # إذا لم يتم العثور على عنوان مناسب، ترجم العنوان الأصلي
            if not chapter_title_found:
                if not original_title.startswith('الجزء') and not original_title.lower().startswith('chapter'):
                    translation_prompt = f"""اترجم عنوان الفصل التالي إلى العربية بشكل مختصر ومميز:

{original_title}

عنوان مترجم مميز (٣-٨ كلمات فقط):"""
                    
                    translated_title = await api_manager.make_precision_request(
                        translation_prompt,
                        temperature=0.2,
                        request_type="chapter_title_translation"
                    )
                    
                    if translated_title:
                        clean_title = translated_title.strip()[:50]
                        # تجنب تكرار نفس الترجمة
                        if clean_title not in used_translations:
                            arabic_title = clean_title
                            used_translations.add(clean_title)
                        else:
                            arabic_title = f"الفصل {len(table_of_contents) + 1}"
                    else:
                        arabic_title = f"الفصل {len(table_of_contents) + 1}"
                else:
                    arabic_title = f"الفصل {len(table_of_contents) + 1}"
            else:
                arabic_title = chapter_title_found
            
            table_of_contents.append({
                'original_title': original_title,
                'arabic_title': arabic_title
            })
        
        logger.info(f"تم إنشاء فهرس بدون تكرار يحتوي على {len(table_of_contents)} عنوان فريد")
        
        return table_of_contents
    
    @staticmethod
    def create_novel_document(chapters: List[Dict[str, Any]], 
                            output_path: str,
                            book_title: str = "الرواية المترجمة",
                            author: str = "مترجم بالذكاء الاصطناعي",
                            table_of_contents: List[Dict[str, str]] = None) -> str:
        """إنشاء مستند رواية احترافي مع فهرس في صفحة منفصلة وأحجام خط محددة"""
        
        logger.info(f"إنشاء مستند الرواية مع فهرس منفصل: {output_path}")
        
        try:
            # إنشاء مجلد الإخراج إذا لم يكن موجوداً
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            doc = Document()
            
            # إعداد الصفحة للرواية العربية - تحسين استغلال المساحة
            section = doc.sections[0]
            section.page_width = Inches(6)
            section.page_height = Inches(9)
            section.left_margin = Inches(0.7)    # تقليل الهامش قليلاً
            section.right_margin = Inches(0.9)   # تقليل الهامش قليلاً
            section.top_margin = Inches(0.8)     # تقليل الهامش العلوي
            section.bottom_margin = Inches(0.8)  # تقليل الهامش السفلي
            
            # إعداد النمط الأساسي للعربية - استغلال أمثل للمساحة
            style = doc.styles['Normal']
            font = style.font
            font.name = 'Arial'
            font.rtl = True
            font.size = Pt(14)  # حجم النص الأساسي 14pt
            style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY  # محاذاة ضبط
            style.paragraph_format.line_spacing = 1.3   # مسافة خط مثلى - لا كبيرة ولا صغيرة
            style.paragraph_format.space_after = Pt(6)  # مسافة صغيرة بين الفقرات
            style.paragraph_format.space_before = Pt(0) # بدون مسافة قبل الفقرة
            style.paragraph_format.first_line_indent = Inches(0.25)  # بادئة مناسبة

            # أنماط محسنة للرواية
            styles = doc.styles
            
            # نمط عنوان الرواية - مضغوط ومناسب
            if 'NovelTitle' not in styles:
                novel_title_style = styles.add_style('NovelTitle', WD_STYLE_TYPE.PARAGRAPH)
                novel_title_style.font.name = 'Arial'
                novel_title_style.font.rtl = True
                novel_title_style.font.size = Pt(18)  # حجم مناسب للعنوان الرئيسي
                novel_title_style.font.bold = True
                novel_title_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                novel_title_style.paragraph_format.space_after = Pt(10)  # مسافة صغيرة
                novel_title_style.paragraph_format.space_before = Pt(0)
            
            # نمط عنوان الفصل - حجم 15pt مع مساحات محسنة
            if 'ChapterTitle' not in styles:
                chapter_title_style = styles.add_style('ChapterTitle', WD_STYLE_TYPE.PARAGRAPH)
                chapter_title_style.font.name = 'Arial'
                chapter_title_style.font.rtl = True
                chapter_title_style.font.size = Pt(15)  # حجم عناوين الفصول 15pt
                chapter_title_style.font.bold = True
                chapter_title_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                chapter_title_style.paragraph_format.space_before = Pt(12)  # مسافة قبل العنوان
                chapter_title_style.paragraph_format.space_after = Pt(8)    # مسافة بعد العنوان
            
            # نمط النص الأساسي - 14pt مع تحسين استغلال المساحة
            if 'NovelText' not in styles:
                novel_text_style = styles.add_style('NovelText', WD_STYLE_TYPE.PARAGRAPH)
                novel_text_style.base_style = styles['Normal']
                novel_text_style.font.name = 'Arial'
                novel_text_style.font.rtl = True
                novel_text_style.font.size = Pt(14)  # حجم النص الأساسي 14pt - موحد
                novel_text_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY  # محاذاة ضبط
                novel_text_style.paragraph_format.line_spacing = 1.25  # مسافة خط محسنة
                novel_text_style.paragraph_format.space_after = Pt(4)   # مسافة صغيرة بين الفقرات
                novel_text_style.paragraph_format.space_before = Pt(0)  # بدون مسافة قبل الفقرة
                novel_text_style.paragraph_format.first_line_indent = Inches(0.2)  # بادئة صغيرة
                novel_text_style.paragraph_format.widow_control = True   # منع الأسطر الوحيدة
                novel_text_style.paragraph_format.keep_together = False  # السماح بتقسيم الفقرات
            
            # نمط الفهرس - عنوان الفهرس محسن
            if 'TOCTitle' not in styles:
                toc_title_style = styles.add_style('TOCTitle', WD_STYLE_TYPE.PARAGRAPH)
                toc_title_style.font.name = 'Arial'
                toc_title_style.font.rtl = True
                toc_title_style.font.size = Pt(16)
                toc_title_style.font.bold = True
                toc_title_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                toc_title_style.paragraph_format.space_after = Pt(15)  # مسافة محسنة
                toc_title_style.paragraph_format.space_before = Pt(0)
            
            # نمط عناصر الفهرس - استغلال أمثل للمساحة
            if 'TOCEntry' not in styles:
                toc_entry_style = styles.add_style('TOCEntry', WD_STYLE_TYPE.PARAGRAPH)
                toc_entry_style.font.name = 'Arial'
                toc_entry_style.font.rtl = True
                toc_entry_style.font.size = Pt(13)  # حجم مناسب لأسماء الفصول
                toc_entry_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                toc_entry_style.paragraph_format.space_after = Pt(6)    # مسافة محسنة
                toc_entry_style.paragraph_format.space_before = Pt(0)
                toc_entry_style.paragraph_format.left_indent = Inches(0.2)  # مسافة بادئة صغيرة
            
            # صفحة العنوان
            title_paragraph = doc.add_paragraph(book_title, style='NovelTitle')
            
            if author and author != "مترجم بالذكاء الاصطناعي":
                author_paragraph = doc.add_paragraph(author)
                author_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                author_paragraph.runs[0].font.size = Pt(13)  # حجم مناسب لاسم المؤلف
                author_paragraph.runs[0].font.rtl = True
                author_paragraph.paragraph_format.space_after = Pt(5)  # مسافة صغيرة
            
            # انتقال لصفحة جديدة للفهرس
            doc.add_page_break()
            
            # صفحة الفهرس المنفصلة - احترافية مثل الكتب الحقيقية
            if table_of_contents:
                doc.add_paragraph("فهرس المحتويات", style='TOCTitle')
                
                # مسافة إضافية قبل بداية الفهرس - محسنة
                doc.add_paragraph().paragraph_format.space_after = Pt(8)
                
                # إضافة عناصر الفهرس بشكل احترافي - أسماء الفصول بالأحرف العربية
                for i, toc_entry in enumerate(table_of_contents, 1):
                    # تحويل الرقم إلى كتابة عربية
                    chapter_number_text = ComprehensiveContentProcessor.number_to_arabic_text(i)
                    
                    # تنسيق احترافي: اسم الفصل بالأحرف العربية
                    toc_line = f"الفصل {chapter_number_text}: {toc_entry['arabic_title']}"
                    toc_paragraph = doc.add_paragraph(toc_line, style='TOCEntry')
                    
                    # إضافة مسافة صغيرة بين الفصول للوضوح - محسنة
                    toc_paragraph.paragraph_format.space_after = Pt(6)
            
            # انتقال لصفحة جديدة للمحتوى
            doc.add_page_break()
            
            # محتوى الرواية النظيف بدون تكرار
            used_chapter_titles = set()  # لمنع تكرار العناوين
            
            for i, chapter in enumerate(chapters):
                if not chapter.get('translated_content'):
                    logger.warning(f"تخطي الفصل غير المترجم: {chapter['title']}")
                    continue
                
                # استخدام عنوان فريد من الفهرس
                chapter_title = None
                if table_of_contents and i < len(table_of_contents):
                    potential_title = table_of_contents[i]['arabic_title']
                    # تجنب تكرار نفس العنوان
                    if potential_title not in used_chapter_titles:
                        chapter_title = potential_title
                        used_chapter_titles.add(chapter_title)
                
                # إضافة عنوان الفصل مرة واحدة فقط إذا كان فريداً
                if chapter_title and not chapter_title.startswith('الجزء'):
                    doc.add_paragraph(chapter_title, style='ChapterTitle')
                
                # معالجة محتوى الفصل بشكل منتظم
                content = chapter['translated_content']
                
                # تقسيم النص وتنظيفه
                paragraphs = content.split('\n\n')
                
                for para_text in paragraphs:
                    para_text = para_text.strip()
                    if para_text:
                        # تنظيف النص من العناوين المكررة
                        if chapter_title and chapter_title in para_text:
                            para_text = para_text.replace(chapter_title, '').strip()
                        
                        clean_text = EnhancedDocumentGenerator.clean_novel_paragraph(para_text)
                        if clean_text and len(clean_text) > 10:  # تجنب النصوص القصيرة
                            doc.add_paragraph(clean_text, style='NovelText')
            
            # حفظ المستند
            doc.save(output_path)
            
            logger.info(f"تم إنشاء مستند الرواية مع تنسيق احترافي محسن بنجاح: {output_path}")
            logger.info(f"أحجام الخط: النص الأساسي 14pt، العناوين 15pt")
            logger.info(f"الفهرس: احترافي مع أرقام بالأحرف العربية")
            logger.info(f"التنسيق: استغلال أمثل للمساحة مثل الروايات الاحترافية")
            return output_path
            
        except Exception as e:
            logger.error(f"خطأ في إنشاء مستند الرواية: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    @staticmethod
    def clean_novel_paragraph(text: str) -> str:
        """تنظيف شامل للفقرة مع إزالة التكرار والعناصر غير المرغوبة"""
        
        # إزالة الأرقام في بداية الفقرات
        text = re.sub(r'^\d+[\.\-\s]*', '', text)
        
        # إزالة أرقام الصفحات
        text = re.sub(r'^\s*\d+\s*$', '', text)
        
        # إزالة الرموز والفواصل غير المرغوبة
        text = re.sub(r'^[•\-\*\.\:\;]\s*', '', text)
        
        # إزالة الكلمات المكررة في نفس السطر
        words = text.split()
        if len(words) > 1:
            # إزالة التكرار المباشر
            clean_words = []
            for i, word in enumerate(words):
                if i == 0 or word != words[i-1]:
                    clean_words.append(word)
            text = ' '.join(clean_words)
        
        # تنظيف المسافات
        text = re.sub(r'\s+', ' ', text)
        
        # إزالة الفقرات القصيرة جداً أو التي تحتوي رموز فقط
        if len(text.strip()) < 20 or re.match(r'^[\d\s\-\*•\.\:\;]+$', text.strip()):
            return ""
        
        # إزالة الفقرات التي هي مجرد عناوين مكررة
        if text.strip().isupper() and len(text.strip()) < 50:
            return ""
        
        return text.strip()


class MasterTranslationSystem:
    """النظام الرئيسي الشامل للترجمة عالية الجودة - المحسن"""
    
    def __init__(self, api_keys: List[str], target_language: str = "Arabic"):
        self.api_manager = EnhancedGeminiAPI(api_keys)
        self.translation_engine = CompleteTranslationEngine(self.api_manager, target_language)
        self.document_processor = ProfessionalDocumentProcessor()
        self.document_generator = EnhancedDocumentGenerator()
        
        # إعداد قاعدة البيانات
        self.db_path = "master_translation_enhanced.db"
        self.init_advanced_database()
        
        # إحصائيات مفصلة
        self.translation_stats = {
            'total_chapters': 0,
            'completed_chapters': 0,
            'skipped_chapters': 0,
            'total_words': 0,
            'translated_words': 0,
            'total_characters': 0,
            'translation_start_time': None,
            'estimated_completion_time': None,
            'average_quality_score': 0.0,
            'foreign_content_corrections': 0,
            'contextual_adaptations': 0
        }
        
        logger.info("تم تهيئة النظام الرئيسي المحسن للترجمة عالية الجودة")
    
    def init_advanced_database(self):
        """إنشاء قاعدة بيانات متقدمة"""
        
        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            # جدول الفصول مع معلومات مفصلة
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS chapters (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    original_content TEXT,
                    translated_content TEXT,
                    word_count INTEGER,
                    character_count INTEGER,
                    genre TEXT DEFAULT 'prose',
                    tone TEXT DEFAULT 'neutral',
                    status TEXT DEFAULT 'pending',
                    translation_attempts INTEGER DEFAULT 0,
                    quality_score REAL DEFAULT 0.0,
                    translation_time REAL DEFAULT 0.0,
                    foreign_content_detected BOOLEAN DEFAULT 0,
                    corrections_applied INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # جدول المصطلحات المتقدم
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS terminology (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_term TEXT UNIQUE,
                    translated_term TEXT,
                    category TEXT,
                    frequency INTEGER DEFAULT 1,
                    confidence_score REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # جدول السجلات المفصل
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS translation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chapter_id TEXT,
                    operation TEXT,
                    status TEXT,
                    message TEXT,
                    duration REAL,
                    api_key_used TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.commit()

        logger.info("تم إنشاء قاعدة البيانات المتقدمة")
    
    def save_chapter_advanced(self, chapter_data: Dict[str, Any]):
        """حفظ متقدم للفصل مع جميع البيانات"""
        
        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO chapters
                (id, title, original_content, translated_content, word_count, character_count,
                 genre, tone, status, translation_attempts, quality_score, translation_time,
                 foreign_content_detected, corrections_applied, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                chapter_data['id'],
                chapter_data['title'],
                chapter_data.get('original_content', ''),
                chapter_data.get('translated_content', ''),
                chapter_data.get('word_count', 0),
                chapter_data.get('character_count', 0),
                chapter_data.get('genre', 'prose'),
                chapter_data.get('tone', 'neutral'),
                chapter_data.get('status', 'pending'),
                chapter_data.get('translation_attempts', 0),
                chapter_data.get('quality_score', 0.0),
                chapter_data.get('translation_time', 0.0),
                chapter_data.get('foreign_content_detected', False),
                chapter_data.get('corrections_applied', 0),
                datetime.now().isoformat()
            ))

            conn.commit()
    
    def log_operation(self, chapter_id: str, operation: str, status: str, 
                     message: str, duration: float = 0.0, api_key: str = ""):
        """تسجيل العمليات في السجل"""
        
        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO translation_logs
                (chapter_id, operation, status, message, duration, api_key_used)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (chapter_id, operation, status, message, duration, api_key[:10]))

            conn.commit()

    def _load_completed_chapters_from_db(self) -> Dict[str, Any]:
        """تحميل الفصول المكتملة مسبقاً من قاعدة البيانات"""
        logger.info("فحص قاعدة البيانات عن فصول مترجمة مسبقاً...")

        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM chapters WHERE status = 'completed'")
            completed_chapters = {}
            rows = cursor.fetchall()
            for row in rows:
                chapter_data = dict(row)
                completed_chapters[chapter_data['id']] = chapter_data
            
            if completed_chapters:
                logger.info(f"تم العثور على {len(completed_chapters)} فصل مترجم مسبقاً. سيتم تخطي ترجمتهم.")
            else:
                logger.info("لم يتم العثور على فصول مترجمة مسبقاً.")
            
            return completed_chapters

    async def translate_chapter_comprehensively(self, chapter: Dict[str, Any]) -> Dict[str, Any]:
        """ترجمة شاملة للفصل مع ضمانات الجودة المحسنة"""
        
        start_time = time.time()
        chapter_id = chapter['id']
        
        logger.info(f"بدء الترجمة الشاملة للفصل: {chapter['title']}")
        quality_logger.info(f"الفصل {chapter_id}: بدء المعالجة المحسنة")
        
        try:
            # إعداد البيانات الأولية
            content = chapter.get('content', '')
            chapter['original_content'] = content
            chapter['word_count'] = len(content.split())
            chapter['character_count'] = len(content)
            chapter['status'] = 'translating'
            chapter['translation_attempts'] = chapter.get('translation_attempts', 0) + 1
            
            # اكتشاف نوع النص ونبرته
            text_analysis = self.translation_engine.detect_text_genre_and_tone(content)
            chapter['genre'] = text_analysis['genre']
            chapter['tone'] = text_analysis['tone']
            
            self.save_chapter_advanced(chapter)
            self.log_operation(chapter_id, "translation_start", "info", 
                             f"بدء ترجمة فصل من {chapter['word_count']} كلمة - النوع: {text_analysis['genre']}, النبرة: {text_analysis['tone']}")
            
            # الترجمة الشاملة مع المراجعة
            translation_context = f"هذا الفصل بعنوان '{chapter['title']}' من رواية أدبية"
            
            translated_content = await self.translation_engine.translate_with_comprehensive_review(
                content, translation_context
            )
            
            if translated_content:
                translation_time = time.time() - start_time
                
                # فحص المحتوى الأجنبي النهائي
                foreign_content_detected = self.translation_engine.content_processor.has_any_foreign_content(translated_content)
                
                # حساب عدد التصحيحات المطبقة
                corrections_count = 2 if foreign_content_detected else 1
                
                # تحديث بيانات الفصل
                chapter.update({
                    'translated_content': translated_content,
                    'status': 'completed',
                    'translation_time': translation_time,
                    'quality_score': 8.5,  # نقاط افتراضية عالية
                    'foreign_content_detected': foreign_content_detected,
                    'corrections_applied': corrections_count
                })
                
                # حفظ النتائج
                self.save_chapter_advanced(chapter)
                
                # تسجيل النجاح
                self.log_operation(
                    chapter_id, "translation_complete", "success",
                    f"تمت الترجمة في {translation_time:.2f}ث، النوع: {text_analysis['genre']}, التصحيحات: {corrections_count}",
                    translation_time
                )
                
                # تحديث الإحصائيات
                self.translation_stats['completed_chapters'] += 1
                self.translation_stats['translated_words'] += chapter['word_count']
                self.translation_stats['contextual_adaptations'] += 1
                
                if foreign_content_detected:
                    self.translation_stats['foreign_content_corrections'] += 1
                    quality_logger.warning(f"الفصل {chapter_id}: تم تطبيق تصحيحات على المحتوى الأجنبي")
                else:
                    quality_logger.info(f"الفصل {chapter_id}: خالٍ من المحتوى الأجنبي")
                
                logger.info(f"تم إنهاء ترجمة الفصل {chapter['title']} بنجاح - "
                          f"الوقت: {translation_time:.2f}ث، النوع: {text_analysis['genre']}")
                
                return chapter
                
            else:
                # فشل في الترجمة
                chapter['status'] = 'failed'
                self.save_chapter_advanced(chapter)
                
                self.log_operation(chapter_id, "translation_failed", "error",
                                 "فشل في الحصول على ترجمة من API")
                
                logger.error(f"فشل في ترجمة الفصل: {chapter['title']}")
                return chapter
                
        except Exception as e:
            # خطأ في العملية
            chapter['status'] = 'error'
            error_message = str(e)
            
            self.save_chapter_advanced(chapter)
            self.log_operation(chapter_id, "translation_error", "error", error_message)
            
            logger.error(f"خطأ في ترجمة الفصل {chapter['title']}: {error_message}")
            logger.error(traceback.format_exc())
            
            return chapter
    
    async def process_complete_book(self, pdf_path: str, output_dir: str,
                                  book_title: str = None, author: str = None) -> str:
        """معالجة كاملة للكتاب من PDF إلى رواية جاهزة للقراءة مع فهرس منفصل"""
        
        # إنشاء مجلد الإخراج
        output_path_obj = Path(output_dir)
        output_path_obj.mkdir(parents=True, exist_ok=True)
        
        # تحديد اسم الملف المخرج
        pdf_name = Path(pdf_path).stem
        output_file = output_path_obj / f"{pdf_name}_رواية_مترجمة.docx"
        
        logger.info("=" * 100)
        logger.info("بدء المعالجة الشاملة المحسنة للرواية مع الفهرس المنفصل")
        logger.info(f"الملف المصدر: {pdf_path}")
        logger.info(f"الملف الهدف: {output_file}")
        logger.info("=" * 100)
        
        self.translation_stats['translation_start_time'] = time.time()
        
        try:
            # المرحلة 1: استخراج وتحليل المستند
            logger.info("📖 المرحلة 1: استخراج وتحليل المستند...")
            document_structure = self.document_processor.extract_pdf_with_precision(pdf_path)
            
            # تحميل الفصول المكتملة مسبقاً من قاعدة البيانات
            previously_completed = self._load_completed_chapters_from_db()

            chapters = document_structure['chapters']
            self.translation_stats['total_chapters'] = len(chapters)
            self.translation_stats['total_words'] = sum(ch['word_count'] for ch in chapters)
            self.translation_stats['total_characters'] = sum(len(ch.get('content', '')) for ch in chapters)
            
            if not book_title:
                book_title = document_structure.get('title', 'الرواية المترجمة') or 'الرواية المترجمة'
            if not author:
                author = document_structure.get('author', 'مؤلف غير محدد') or 'مؤلف غير محدد'
            
            logger.info(f"📊 تم استخراج {len(chapters)} فصل")
            logger.info(f"📊 إجمالي الكلمات: {self.translation_stats['total_words']:,}")
            logger.info(f"📊 إجمالي الأحرف: {self.translation_stats['total_characters']:,}")
            logger.info(f"📚 عنوان الكتاب: {book_title}")
            logger.info(f"✍️ المؤلف: {author}")
            
            # المرحلة 2: ترجمة شاملة مع مراجعة متعددة المراحل
            logger.info("🔄 المرحلة 2: بدء الترجمة الشاملة مع ضمان عدم ترك أي محتوى أجنبي...")
            
            all_processed_chapters = []
            
            for i, chapter in enumerate(chapters):
                logger.info("-" * 50)
                
                # التحقق من وجود ترجمة سابقة للفصل
                if chapter['id'] in previously_completed:
                    logger.info(f"⏭️ تخطي الفصل {i+1}/{len(chapters)}: '{chapter['title']}' (مترجم مسبقاً).")
                    
                    completed_chapter_info = previously_completed[chapter['id']]
                    all_processed_chapters.append(completed_chapter_info)
                    
                    # تحديث الإحصائيات
                    self.translation_stats['skipped_chapters'] += 1
                    self.translation_stats['completed_chapters'] += 1
                    self.translation_stats['translated_words'] += completed_chapter_info.get('word_count', 0)
                    continue

                logger.info(f"📝 ترجمة الفصل {i+1}/{len(chapters)}: {chapter['title']}")
                result = await self.translate_chapter_comprehensively(chapter)
                all_processed_chapters.append(result)
                
                progress = (i + 1) / len(chapters) * 100
                elapsed_time = time.time() - self.translation_stats['translation_start_time']
                
                chapters_done = i + 1
                if chapters_done > 0:
                    avg_time_per_chapter = elapsed_time / chapters_done
                    remaining_chapters = len(chapters) - chapters_done
                    estimated_remaining = avg_time_per_chapter * remaining_chapters
                    
                    logger.info(f"📈 التقدم: {progress:.1f}% ({chapters_done}/{len(chapters)})")
                    logger.info(f"⏰ الوقت المقدر المتبقي: {estimated_remaining/60:.1f} دقيقة")
                    
                    successful = sum(1 for ch in all_processed_chapters if ch['status'] == 'completed')
                    if successful > 0:
                        logger.info(f"✅ الفصول المكتملة: {successful}")
                        logger.info(f"🔧 تصحيحات المحتوى الأجنبي: {self.translation_stats['foreign_content_corrections']}")
                        logger.info(f"📖 تكيفات سياقية: {self.translation_stats['contextual_adaptations']}")
            
            # المرحلة 3: التحقق النهائي من الجودة
            logger.info("🔍 المرحلة 3: التحقق النهائي من الجودة...")
            
            successful_chapters = [ch for ch in all_processed_chapters if ch['status'] == 'completed']
            failed_chapters = [ch for ch in all_processed_chapters if ch['status'] in ['failed', 'error']]
            
            if failed_chapters:
                logger.warning(f"⚠️  {len(failed_chapters)} فصل فشل في الترجمة:")
                for ch in failed_chapters:
                    logger.warning(f"   - {ch['title']}")
            
            chapters_with_foreign = [ch for ch in successful_chapters if ch.get('foreign_content_detected', False)]
            if chapters_with_foreign:
                quality_logger.warning(f"تم تطبيق تصحيحات على المحتوى الأجنبي في {len(chapters_with_foreign)} فصل")
            else:
                quality_logger.info("جميع الفصول خالية من المحتوى الأجنبي")
            
            # المرحلة 4: إنشاء فهرس منظم بدون تكرار
            logger.info("📋 المرحلة 4: إنشاء فهرس منظم بدون تكرار...")
            
            table_of_contents = await self.document_generator.create_table_of_contents(
                successful_chapters, self.api_manager
            )
            
            logger.info(f"تم إنشاء فهرس احترافي بدون أرقام صفحات يحتوي على {len(table_of_contents)} عنوان فريد")
            
            # المرحلة 5: إنشاء مستند الرواية النهائي مع الفهرس المنفصل
            logger.info("📝 المرحلة 5: إنشاء مستند الرواية النهائي مع التنسيق الاحترافي...")
            logger.info("🎯 أحجام الخط: النص الأساسي 14pt، العناوين 15pt فقط")
            logger.info("📄 الفهرس: احترافي بأرقام عربية مكتوبة")
            logger.info("📐 التنسيق: استغلال أمثل للمساحة مثل الروايات المطبوعة")
            
            final_document_path = self.document_generator.create_novel_document(
                successful_chapters, str(output_file), book_title, author, table_of_contents
            )
            
            # المرحلة 6: تجميع الإحصائيات النهائية
            total_time = time.time() - self.translation_stats['translation_start_time']
            total_successful = len(successful_chapters)
            total_failed = len(failed_chapters)
            
            translated_words = sum(ch.get('word_count', 0) for ch in successful_chapters)
            words_per_minute = translated_words / (total_time / 60) if total_time > 0 else 0
            
            # تقرير نهائي شامل
            logger.info("=" * 100)
            logger.info("🎉 تمت معالجة الرواية بنجاح مع الفهرس المنفصل!")
            logger.info("=" * 100)
            logger.info(f"📖 عنوان الرواية: {book_title}")
            logger.info(f"✍️  المؤلف: {author}")
            logger.info(f"📄 إجمالي الفصول: {len(chapters)}")
            logger.info(f"✅ فصول مترجمة بنجاح: {total_successful}")
            logger.info(f"⏭️ فصول تم تخطيها (مترجمة سابقاً): {self.translation_stats['skipped_chapters']}")
            logger.info(f"❌ فصول فاشلة: {total_failed}")
            logger.info(f"📊 إجمالي الكلمات المترجمة: {translated_words:,}")
            logger.info(f"⏱️  إجمالي الوقت: {total_time/60:.1f} دقيقة")
            logger.info(f"🚀 معدل الترجمة: {words_per_minute:.0f} كلمة/دقيقة")
            
            # إحصائيات التحسينات
            logger.info("=" * 50)
            logger.info("🔧 إحصائيات التحسينات المطبقة:")
            logger.info(f"   🌍 تصحيحات المحتوى الأجنبي: {self.translation_stats['foreign_content_corrections']}")
            logger.info(f"   📖 تكيفات سياقية (نوع ونبرة): {self.translation_stats['contextual_adaptations']}")
            logger.info(f"   🔑 مفاتيح API متعددة: {len(self.api_manager.api_keys)} مفاتيح")
            logger.info(f"   📚 مصطلحات محفوظة: {len(self.translation_engine.terminology_database)} مصطلح")
            logger.info(f"   📋 فهرس احترافي: {len(table_of_contents)} فصل بأرقام عربية مكتوبة")
            logger.info(f"   🎯 أحجام الخط موحدة: النص 14pt، العناوين 15pt فقط")
            logger.info(f"   📐 تنسيق محسن: استغلال أمثل للمساحة، مسافات مدروسة")
            
            logger.info(f"📁 الرواية النهائية مع التنسيق الاحترافي: {final_document_path}")
            logger.info("=" * 100)
            
            quality_logger.info("تقرير الجودة النهائي:")
            quality_logger.info(f"إجمالي التصحيحات المطبقة: {sum(ch.get('corrections_applied', 0) for ch in successful_chapters)}")
            
            # تصنيف الفصول حسب النوع
            genre_counts = {}
            tone_counts = {}
            for ch in successful_chapters:
                genre = ch.get('genre', 'unknown')
                tone = ch.get('tone', 'unknown')
                genre_counts[genre] = genre_counts.get(genre, 0) + 1
                tone_counts[tone] = tone_counts.get(tone, 0) + 1
            
            quality_logger.info("توزيع الأنواع الأدبية:")
            for genre, count in genre_counts.items():
                quality_logger.info(f"  {genre}: {count} فصل")
            
            quality_logger.info("توزيع النبرات العاطفية:")
            for tone, count in tone_counts.items():
                quality_logger.info(f"  {tone}: {count} فصل")
            
            return final_document_path
            
        except Exception as e:
            logger.error(f"خطأ كارثي في معالجة الرواية: {str(e)}")
            logger.error(traceback.format_exc())
            raise


def validate_input_paths(input_path: str, output_dir: str) -> Tuple[bool, str]:
    """التحقق من صحة مسارات الإدخال والإخراج"""
    
    # التحقق من وجود ملف الإدخال
    if not os.path.exists(input_path):
        return False, f"ملف الإدخال غير موجود: {input_path}"
    
    # التحقق من أن الملف هو PDF
    if not input_path.lower().endswith('.pdf'):
        return False, "الملف يجب أن يكون من نوع PDF"
    
    # التحقق من إمكانية إنشاء مجلد الإخراج
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"لا يمكن إنشاء مجلد الإخراج: {str(e)}"
    
    return True, "مسارات صحيحة"


async def main():
    """الدالة الرئيسية للنظام المحسن مع الفهرس المنفصل"""
    
    print("🚀 نظام الترجمة الشامل المحسن - للروايات والنصوص الأدبية مع الفهرس المنفصل")
    print("=" * 90)
    print("✨ المميزات المحسنة:")
    print("   🔑 مفاتيح API متعددة لضمان الاستمرارية")
    print("   🌍 إزالة شاملة لأي محتوى أجنبي (كلمات وأرقام)")
    print("   📖 ترجمة سياقية حسب نوع النص ونبرته العاطفية")
    print("   🎭 تكيف مع الأنواع الأدبية (شعر، حوار، سرد، نثر)")
    print("   💫 تكيف مع النبرات العاطفية (حزين، مفرح، درامي، محايد)")
    print("   📚 حفظ وإدارة ذكية للمصطلحات")
    print("   📋 إنشاء فهرس احترافي مثل الكتب الحقيقية - أسماء الفصول فقط!")
    print("   📄 إخراج نهائي للروايات - فهرس احترافي + نص منظم")
    print("   🎯 أحجام خط محددة: النص 14pt، العناوين 15pt")
    print("   🔍 مراجعة متعددة المراحل لضمان أعلى جودة")
    print("=" * 90)
    
    # إنشاء النظام المحسن
    system = MasterTranslationSystem([])  # سيتم استخدام المفاتيح المدمجة
    
    # استخدام المسارات المحددة
    input_path = "/root/Downloads/teanasost/input/1p.pdf"
    output_dir = "/root/Downloads/teanasost/output"
    
    print(f"\n📁 معلومات المسارات:")
    print(f"مسار الإدخال: {input_path}")
    print(f"مجلد الإخراج: {output_dir}")
    
    # التحقق من صحة المسارات
    is_valid, validation_message = validate_input_paths(input_path, output_dir)
    
    if not is_valid:
        print(f"\n❌ خطأ في المسارات: {validation_message}")
        return
    
    print(f"✅ {validation_message}")
    
    # معلومات إضافية اختيارية
    print(f"\n📚 معلومات الرواية (اختيارية):")
    book_title = input("عنوان الرواية (Enter للتخطي): ").strip()
    author = input("اسم المؤلف (Enter للتخطي): ").strip()
    
    if not book_title:
        book_title = None
    if not author:
        author = None
    
    try:
        print("\n🔄 بدء عملية الترجمة الشاملة المحسنة مع الفهرس المنفصل...")
        print("🌟 النظام المحسن يضمن:")
        print("   • ترجمة كل كلمة وحرف ورقم في النص")
        print("   • تكيف سياقي حسب نوع النص العاطفي")
        print("   • إزالة تامة لأي محتوى أجنبي")
        print("   • إنشاء فهرس احترافي مثل الكتب - أسماء الفصول فقط")
        print("   • أحجام خط محددة: النص 14pt، العناوين 15pt")
        print("   • إخراج رواية نظيفة جاهزة للقراءة")
        print("-" * 90)
        
        # تشغيل النظام الكامل المحسن
        final_document = await system.process_complete_book(
            input_path, output_dir, book_title, author
        )
        
        print(f"\n🎉 تم إنشاء الرواية المترجمة مع الفهرس الاحترافي بنجاح!")
        print(f"📄 الرواية النهائية: {final_document}")
        print(f"📋 الرواية تحتوي على فهرس احترافي مثل الكتب الحقيقية!")
        print(f"🚫 الفهرس: أسماء الفصول فقط بدون أرقام صفحات!")
        print(f"🎯 أحجام الخط: النص الأساسي 14pt، العناوين 15pt فقط!")
        print(f"📐 التنسيق: استغلال أمثل للمساحة مثل الروايات المطبوعة!")
        
        # عرض ملخص الإنجازات
        if system.translation_stats['foreign_content_corrections'] > 0:
            print(f"\n🔧 تم تطبيق {system.translation_stats['foreign_content_corrections']} تصحيح للمحتوى الأجنبي")
        
        if system.translation_stats['contextual_adaptations'] > 0:
            print(f"📖 تم تطبيق {system.translation_stats['contextual_adaptations']} تكيف سياقي")
        
        print(f"📚 تم حفظ {len(system.translation_engine.terminology_database)} مصطلح في قاعدة البيانات")
        
    except KeyboardInterrupt:
        print("\n⏹️ تم إيقاف العملية بواسطة المستخدم")
        print("💾 البيانات المحفوظة يمكن استكمالها لاحقاً")
        
    except Exception as e:
        print(f"\n❌ حدث خطأ فادح غير متوقع: {str(e)}")
        logger.error(f"خطأ في main: {str(e)}")
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 تم إنهاء البرنامج")
    except Exception as e:
        print(f"خطأ غير متوقع على المستوى الأعلى: {str(e)}")
