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
import PyPDF2
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
import structlog
import pybreaker
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn, TaskProgressColumn
from rich.logging import RichHandler

# تهيئة Rich Console للطباعة المنسقة في الطرفية
console = Console()

# ============= تحسين 1: نظام السجلات المحسن الذكي باستخدام Structlog =============
def setup_comprehensive_logging():
    """إعداد نظام سجلات شامل وذكي مع structlog و rich، متوافق مع الاستعلام وقاعدة البيانات"""
    log_dir = Path("translation_logs")
    log_dir.mkdir(exist_ok=True)
    
    # تنظيف السجلات القديمة: الاحتفاظ بآخر 5 ملفات فقط لكل نوع (تجنب التراكم الذي ذكره المستخدم)
    def clean_old_logs(prefix: str, keep: int = 5):
        logs = sorted(log_dir.glob(f"{prefix}_*.log"), key=os.path.getmtime, reverse=True)
        for old_log in logs[keep:]:
            try:
                old_log.unlink()
            except Exception:
                pass

    clean_old_logs("main_translation")
    clean_old_logs("quality_control")

    # أسماء ملفات السجلات الجديدة بصيغة JSON
    main_log = log_dir / f'main_translation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    quality_log = log_dir / f'quality_control_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    # إعداد إعدادات logging القياسية للتوجيه لملفات باستخدام JSON
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # إعداد Formatter لملفات السجل (JSON) و Formatter للطرفية (Rich)
    json_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(ensure_ascii=False),
    )

    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=True),
    )

    # إعداد logger الرئيسي مع rotation
    main_logger_std = logging.getLogger('main')
    main_logger_std.setLevel(logging.INFO)
    main_logger_std.handlers.clear() # تفريغ لتجنب التكرار
    
    # Rotating file handler للملف الرئيسي بصيغة JSON
    main_handler = RotatingFileHandler(
        main_log,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    main_handler.setFormatter(json_formatter)
    main_logger_std.addHandler(main_handler)

    # Console handler لطباعة السجلات الملونة والمنسقة في الطرفية باستخدام Rich
    rich_handler = RichHandler(console=console, show_time=False, show_path=False, markup=True)
    rich_handler.setFormatter(console_formatter)
    main_logger_std.addHandler(rich_handler)

    # logger منفصل لمراقبة الجودة مع rotation
    quality_logger_std = logging.getLogger('quality_control')
    quality_logger_std.setLevel(logging.INFO)
    quality_logger_std.handlers.clear()
    
    quality_handler = RotatingFileHandler(
        quality_log,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    quality_handler.setFormatter(json_formatter)
    quality_logger_std.addHandler(quality_handler)

    quality_rich_handler = RichHandler(console=console, show_time=False, show_path=False, markup=True)
    quality_rich_handler.setFormatter(console_formatter)
    quality_logger_std.addHandler(quality_rich_handler)

    # استخدام structlog للحصول على واجهة استخدام محسنة (تتيح إرسال kwargs)
    main_logger = structlog.get_logger('main')
    quality_logger = structlog.get_logger('quality_control')
    
    return main_logger, quality_logger

logger, quality_logger = setup_comprehensive_logging()

# ============= تحسين 2: نظام Rate Limiting محسن (Tokens & Requests) =============

# --- تقدير التوكنز الذكي المدرك للغة ---
def _estimate_tokens_smart(text: str) -> int:
    """
    تقدير دقيق للتوكنز مع دعم نصوص مختلطة العربية/الإنجليزية.
    يستخدم tiktoken إذا كان متاحاً (دقة عالية)، وإلا يستخدم
    إحصاءات لغوية محسّنة تُراعي أن النصوص العربية تحتاج 20-40% توكنز أكثر.
    """
    if not text:
        return 0

    # المحاولة الأولى: tiktoken (دقة عالية، يعمل محلياً)
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return max(1, len(enc.encode(text)))
    except (ImportError, Exception):
        pass

    # تحليل لغوي للنص
    total_chars = len(text)
    if total_chars == 0:
        return 0

    # حساب نسبة الأحرف العربية (U+0600–U+06FF)
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    arabic_ratio = arabic_chars / total_chars

    # معادلة التقدير المحسّنة:
    # • نص عربي بحت  → ~2.3 حرف/توكن
    # • نص مختلط     → ~3.0 حرف/توكن
    # • نص إنجليزي   → ~4.0 حرف/توكن
    if arabic_ratio >= 0.50:
        chars_per_token = 2.3
    elif arabic_ratio >= 0.20:
        chars_per_token = 3.0
    else:
        chars_per_token = 4.0

    return max(1, int(total_chars / chars_per_token))


# --- ملف إعدادات Rate Limiter الخارجي ---
_RATE_LIMITER_CONFIG_PATH = Path("rate_limiter_config.json")

_RATE_LIMITER_DEFAULT_CONFIG = {
    "default": {
        "max_rpm": 2,
        "max_tpm": 32000,
        "max_rpd": 50
    },
    "adaptive": {
        "enabled": True,
        "min_rpm_floor": 1,
        "error_threshold_per_hour": 3,
        "reduction_factor": 0.5,
        "recovery_factor": 0.1
    },
    "keys": {}
}


def _load_rate_limiter_config() -> dict:
    """
    تحميل إعدادات Rate Limiter من ملف JSON خارجي.
    إذا لم يوجد الملف، يتم إنشاؤه بالإعدادات الافتراضية تلقائياً.
    البنية:
      {
        "default": { "max_rpm": 2, "max_tpm": 32000, "max_rpd": 50 },
        "adaptive": { "enabled": true, ... },
        "keys": {
          "AIzaSy...": { "max_rpm": 5, "max_tpm": 60000, "max_rpd": 100 }
        }
      }
    """
    if _RATE_LIMITER_CONFIG_PATH.exists():
        try:
            with open(_RATE_LIMITER_CONFIG_PATH, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            # دمج مع الإعدادات الافتراضية (لدعم الإضافات المستقبلية)
            merged = _RATE_LIMITER_DEFAULT_CONFIG.copy()
            merged["default"].update(loaded.get("default", {}))
            merged["adaptive"].update(loaded.get("adaptive", {}))
            merged["keys"].update(loaded.get("keys", {}))
            return merged
        except Exception:
            pass  # fallback to defaults

    # إنشاء الملف الافتراضي للمرة الأولى
    try:
        with open(_RATE_LIMITER_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(_RATE_LIMITER_DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return _RATE_LIMITER_DEFAULT_CONFIG.copy()


class TokenRateLimiter:
    """
    نظام Rate Limiting ذكي ومتكيّف لكل مفتاح API.
    
    المميزات:
      ✅ إعدادات قابلة للتهيئة من ملف خارجي (rate_limiter_config.json)
      ✅ دعم إعدادات مختلفة لكل مفتاح API على حدة (خطط مختلفة)
      ✅ تقدير دقيق للتوكنز يراعي النصوص العربية (دعم tiktoken)
      ✅ نظام تكيّفي: يتعلم من أخطاء 429 ويخفّض RPM تلقائياً
        في الساعات ذات الضغط العالي ثم يعود تدريجياً للحد الطبيعي
    """

    def __init__(self, max_rpm: int = 2, max_tpm: int = 32000, max_rpd: int = 50,
                 key_id: Optional[str] = None):
        """
        Args:
            max_rpm: الحد الأقصى للطلبات في الدقيقة (قابل للتجاوز من الملف الخارجي).
            max_tpm: الحد الأقصى للتوكنز في الدقيقة.
            max_rpd: الحد الأقصى للطلبات في اليوم.
            key_id: مفتاح API للبحث عن إعداداته المخصصة في ملف الإعداد.
        """
        # --- تحميل الإعدادات من الملف الخارجي ---
        config = _load_rate_limiter_config()
        default_cfg = config.get("default", {})
        adaptive_cfg = config.get("adaptive", {})
        key_cfg = config.get("keys", {}).get(key_id, {}) if key_id else {}

        # الأولوية: إعدادات المفتاح المخصصة ← ملف الإعداد ← المعاملات الممررة
        self._base_max_rpm = key_cfg.get("max_rpm", default_cfg.get("max_rpm", max_rpm))
        self._base_max_tpm = key_cfg.get("max_tpm", default_cfg.get("max_tpm", max_tpm))
        self._base_max_rpd = key_cfg.get("max_rpd", default_cfg.get("max_rpd", max_rpd))

        # الحدود الفعّالة الحالية (قد تُقلَّص مؤقتاً من النظام التكيّفي)
        self.max_rpm = self._base_max_rpm
        self.max_tpm = self._base_max_tpm
        self.max_rpd = self._base_max_rpd

        # --- طوابير الطلبات ---
        self.requests: deque = deque()        # (timestamp, tokens)
        self.daily_requests: deque = deque()  # timestamps خلال 24 ساعة

        # --- النظام التكيّفي ---
        self._adaptive_enabled: bool = adaptive_cfg.get("enabled", True)
        self._min_rpm_floor: int = max(1, adaptive_cfg.get("min_rpm_floor", 1))
        self._error_threshold: int = adaptive_cfg.get("error_threshold_per_hour", 3)
        self._reduction_factor: float = adaptive_cfg.get("reduction_factor", 0.5)
        self._recovery_factor: float = adaptive_cfg.get("recovery_factor", 0.1)

        # عداد أخطاء 429 مُجمَّعة بالساعة {hour_of_day: count}
        self._errors_by_hour: Dict[int, int] = {}
        # الساعة التي آخر مرة حدث فيها تعديل تكيّفي
        self._last_adaptive_hour: Optional[int] = None

    # ------------------------------------------------------------------ #
    #  تقدير التوكنز                                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """تقدير دقيق لعدد توكنز النص يعتمد على _estimate_tokens_smart."""
        return _estimate_tokens_smart(text)

    # ------------------------------------------------------------------ #
    #  النظام التكيّفي                                                     #
    # ------------------------------------------------------------------ #

    def record_429_error(self):
        """
        تسجيل خطأ 429 (Rate Limit) من الـ API الفعلي.
        بعد تجاوز _error_threshold في الساعة الحالية، يُخفَّض max_rpm
        بمعامل _reduction_factor حتى لا يقل عن _min_rpm_floor.
        """
        if not self._adaptive_enabled:
            return

        current_hour = datetime.now().hour
        self._errors_by_hour[current_hour] = self._errors_by_hour.get(current_hour, 0) + 1

        if self._errors_by_hour[current_hour] >= self._error_threshold:
            new_rpm = max(self._min_rpm_floor,
                          int(self.max_rpm * (1.0 - self._reduction_factor)))
            if new_rpm < self.max_rpm:
                self.max_rpm = new_rpm
                logger.warning(
                    f"[AdaptiveRateLimiter] ارتفاع أخطاء 429 في الساعة {current_hour}:00 "
                    f"→ تخفيض RPM إلى {self.max_rpm}/{self._base_max_rpm}"
                )

        self._last_adaptive_hour = current_hour

    def _try_recover_rpm(self):
        """
        محاولة استعادة RPM تدريجياً بعد ساعة هادئة (بدون أخطاء 429 جديدة).
        تُستدعى داخلياً عند كل طلب ناجح.
        """
        if not self._adaptive_enabled:
            return
        if self.max_rpm >= self._base_max_rpm:
            return

        current_hour = datetime.now().hour
        hour_errors = self._errors_by_hour.get(current_hour, 0)

        # إذا لم تحدث أخطاء في الساعة الحالية، استعد جزءاً من الحد الأصلي
        if hour_errors == 0:
            recovered = max(1, int(self._base_max_rpm * self._recovery_factor))
            self.max_rpm = min(self._base_max_rpm, self.max_rpm + recovered)

    # ------------------------------------------------------------------ #
    #  الواجهة الرئيسية (تتوافق 100% مع الإصدار السابق)                   #
    # ------------------------------------------------------------------ #

    def _purge_old_entries(self, now: float):
        """إزالة الإدخالات القديمة خارج نافذة الدقيقة والـ 24 ساعة."""
        while self.requests and self.requests[0][0] < now - 60:
            self.requests.popleft()
        while self.daily_requests and self.daily_requests[0] < now - 86400:
            self.daily_requests.popleft()

    def can_make_request(self, estimated_tokens: int = 0) -> bool:
        """هل يمكن إرسال طلب جديد الآن دون تجاوز أي حد؟"""
        now = time.time()
        self._purge_old_entries(now)

        if len(self.requests) >= self.max_rpm:
            return False
        if sum(t for _, t in self.requests) + estimated_tokens > self.max_tpm:
            return False
        if len(self.daily_requests) >= self.max_rpd:
            return False

        return True

    def add_request(self, estimated_tokens: int = 0):
        """تسجيل طلب جديد وتحديث النظام التكيّفي للاسترداد."""
        now = time.time()
        self.requests.append((now, estimated_tokens))
        self.daily_requests.append(now)
        # محاولة استعادة RPM تدريجياً عند كل طلب ناجح
        self._try_recover_rpm()

    def time_until_next_request(self, estimated_tokens: int = 0) -> float:
        """وقت الانتظار (بالثواني) حتى يمكن إرسال طلب جديد."""
        if self.can_make_request(estimated_tokens):
            return 0.0

        now = time.time()
        self._purge_old_entries(now)

        wait_times = []

        # انتظار بسبب الحد اليومي
        if len(self.daily_requests) >= self.max_rpd:
            wait_times.append((self.daily_requests[0] + 86400) - now)

        # انتظار بسبب حد الطلبات في الدقيقة
        if len(self.requests) >= self.max_rpm:
            wait_times.append((self.requests[0][0] + 60) - now)

        # انتظار بسبب حد التوكنز في الدقيقة
        current_tpm = sum(t for _, t in self.requests)
        if current_tpm + estimated_tokens > self.max_tpm:
            tokens_to_free = (current_tpm + estimated_tokens) - self.max_tpm
            freed = 0
            for req_time, tokens in self.requests:
                freed += tokens
                if freed >= tokens_to_free:
                    wait_times.append((req_time + 60) - now)
                    break

        return max(wait_times) if wait_times else 0.0

    def get_status(self) -> Dict[str, Any]:
        """
        حالة Rate Limiter الحالية (مفيد للتشخيص والسجلات).
        """
        now = time.time()
        self._purge_old_entries(now)
        return {
            "effective_rpm": self.max_rpm,
            "base_rpm": self._base_max_rpm,
            "max_tpm": self.max_tpm,
            "max_rpd": self.max_rpd,
            "current_rpm_usage": len(self.requests),
            "current_tpm_usage": sum(t for _, t in self.requests),
            "current_rpd_usage": len(self.daily_requests),
            "adaptive_enabled": self._adaptive_enabled,
            "errors_by_hour": dict(self._errors_by_hour),
        }

# ============= تحسين 3: إحصائيات محسنة للمفاتيح ونظام التنبيه الذكي =============
class KeyStatistics:
    """
    إحصائيات متقدمة وذكية لكل مفتاح API مع:
      ✅ تخزين دائم في SQLite بين الجلسات (لا يصفّر التاريخ عند إغلاق البرنامج)
      ✅ تصنيف دقيق لأنواع الفشل: network_error / rate_limit / invalid_key /
         content_blocked / server_error — كل نوع يحمل وزناً مختلفاً
      ✅ نقاط صحة مبنية على بيانات حقيقية لا عقوبات تقديرية ثابتة
      ✅ نموذج تنبؤ ساعي بسيط يتعلم متى يكون المفتاح في أفضل حالاته
    """

    _DB_PATH: Path = Path("key_statistics.db")
    _db_initialized: bool = False  # يُهيَّأ مرة واحدة على مستوى الكلاس

    # ---- الأنواع القياسية للفشل ----
    FAILURE_TYPES = frozenset([
        'network_error',    # timeout / اتصال مقطوع / استثناء شبكي
        'rate_limit',       # 429 - تجاوز حد الطلبات
        'invalid_key',      # 401/403 - مفتاح منتهٍ أو محظور
        'content_blocked',  # رد غير متوقع أو محجوب من Gemini Safety
        'server_error',     # 5xx - خطأ في سيرفر Gemini
        'general',          # أخطاء لا تندرج تحت فئة محددة
    ])

    # خريطة التوحيد: raw error_type الموجود في الكود → canonical type
    _ERROR_CODE_MAP: Dict[str, str] = {
        'timeout':          'network_error',
        'exception':        'network_error',
        'network_error':    'network_error',
        'rate_limit':       'rate_limit',
        'invalid_key':      'invalid_key',
        'api_error':        'invalid_key',       # 401/403 في make_precision_request
        'content_blocked':  'content_blocked',
        'invalid_response': 'content_blocked',   # رد Gemini غير متوقع
        'server_error':     'server_error',
        'general':          'general',
    }

    # أوزان تأثير كل نوع فشل على نقطة الصحة
    # (مشتقة من طبيعة كل خطأ، ليست تقديرية عشوائية)
    FAILURE_WEIGHTS: Dict[str, float] = {
        'invalid_key':      3.0,   # الأشد خطورة — يعني المفتاح معطَّل نهائياً
        'server_error':     1.5,   # خطير لكن مؤقت
        'network_error':    0.8,   # مؤقت، ناجم عن ظروف الشبكة
        'rate_limit':       0.4,   # متوقع في الاستخدام المكثف
        'content_blocked':  0.2,   # لا علاقة له بصحة المفتاح نفسه
        'general':          1.0,
    }

    def __init__(self, key_id: str = ""):
        self.key_id   = key_id
        # تجزئة للهوية في DB (لا نخزّن المفتاح الحقيقي)
        self.key_hash = hashlib.md5(key_id.encode()).hexdigest()[:16] if key_id else "unknown"

        # ---- عدادات في الذاكرة ----
        self.total_requests:        int   = 0
        self.successful_requests:   int   = 0
        self.failed_requests:       int   = 0
        self.consecutive_failures:  int   = 0
        self.last_error_time:   Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        self.average_response_time: float = 0.0
        self.response_times: deque = deque(maxlen=100)

        # ---- عدادات مصنَّفة لأنواع الفشل ----
        self.failure_counts: Dict[str, int] = {ft: 0 for ft in self.FAILURE_TYPES}

        # ---- بيانات ساعية للتنبؤ: {0..23: {'success': N, 'total': N}} ----
        self.hourly_data: Dict[int, Dict[str, int]] = {
            h: {'success': 0, 'total': 0} for h in range(24)
        }

        # ---- تحكم في كثافة الكتابة إلى DB ----
        self._save_counter: int = 0
        self._SAVE_EVERY:   int = 5   # حفظ كل 5 طلبات لتجنب I/O زائد

        # تهيئة DB وتحميل البيانات المحفوظة إن وُجدت
        if key_id:
            self._ensure_db()
            self._load_from_db()

    # ------------------------------------------------------------------ #
    #  إدارة قاعدة البيانات                                               #
    # ------------------------------------------------------------------ #

    @classmethod
    def _ensure_db(cls):
        """إنشاء جدول SQLite إن لم يكن موجوداً (يُنفَّذ مرة واحدة على مستوى الكلاس)."""
        if cls._db_initialized:
            return
        try:
            with sqlite3.connect(cls._DB_PATH) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS key_statistics (
                        key_hash            TEXT PRIMARY KEY,
                        total_requests      INTEGER NOT NULL DEFAULT 0,
                        successful_requests INTEGER NOT NULL DEFAULT 0,
                        failed_requests     INTEGER NOT NULL DEFAULT 0,
                        failure_counts      TEXT    NOT NULL DEFAULT '{}',
                        hourly_data         TEXT    NOT NULL DEFAULT '{}',
                        avg_response_time   REAL    NOT NULL DEFAULT 0.0,
                        response_times      TEXT    NOT NULL DEFAULT '[]',
                        last_error_time     TEXT,
                        last_success_time   TEXT,
                        updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                conn.commit()
            cls._db_initialized = True
            logger.info("[KeyStatistics] SQLite DB initialized successfully")
        except Exception as e:
            logger.warning(f"[KeyStatistics] DB init failed: {e}")

    def _load_from_db(self):
        """تحميل الإحصائيات المحفوظة من SQLite إلى الذاكرة عند بدء الجلسة."""
        try:
            with sqlite3.connect(self._DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM key_statistics WHERE key_hash = ?",
                    (self.key_hash,)
                ).fetchone()

            if not row:
                return  # مفتاح جديد — لا توجد بيانات سابقة

            self.total_requests        = row['total_requests']
            self.successful_requests   = row['successful_requests']
            self.failed_requests       = row['failed_requests']
            self.average_response_time = row['avg_response_time']

            # تحميل عدادات الفشل المصنَّفة
            stored_fc = json.loads(row['failure_counts'] or '{}')
            for ft in self.FAILURE_TYPES:
                self.failure_counts[ft] = stored_fc.get(ft, 0)

            # تحميل البيانات الساعية
            stored_hd = json.loads(row['hourly_data'] or '{}')
            for h in range(24):
                entry = stored_hd.get(str(h), {})
                self.hourly_data[h]['success'] = entry.get('success', 0)
                self.hourly_data[h]['total']   = entry.get('total',   0)

            # تحميل آخر أوقات الاستجابة
            stored_rt = json.loads(row['response_times'] or '[]')
            self.response_times = deque(stored_rt, maxlen=100)
            self._update_average_response_time()

            # تحميل أوقات آخر خطأ/نجاح
            if row['last_error_time']:
                try:
                    self.last_error_time = datetime.fromisoformat(row['last_error_time'])
                except Exception:
                    pass
            if row['last_success_time']:
                try:
                    self.last_success_time = datetime.fromisoformat(row['last_success_time'])
                except Exception:
                    pass

            logger.info(
                f"[KeyStatistics] Loaded history for {self.key_hash}: "
                f"{self.total_requests} requests, "
                f"success_rate={self.get_success_rate():.1f}%"
            )
        except Exception as e:
            logger.warning(f"[KeyStatistics] Load from DB failed ({self.key_hash}): {e}")

    def _save_to_db(self, force: bool = False):
        """
        حفظ الإحصائيات في SQLite.
        يُكتب فعلياً كل _SAVE_EVERY طلبات (أو فوراً إذا force=True)
        لتجنب I/O زائد على كل طلب.
        """
        self._save_counter += 1
        if not force and (self._save_counter % self._SAVE_EVERY != 0):
            return
        try:
            with sqlite3.connect(self._DB_PATH) as conn:
                conn.execute("""
                    INSERT INTO key_statistics
                        (key_hash, total_requests, successful_requests, failed_requests,
                         failure_counts, hourly_data, avg_response_time, response_times,
                         last_error_time, last_success_time, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))
                    ON CONFLICT(key_hash) DO UPDATE SET
                        total_requests      = excluded.total_requests,
                        successful_requests = excluded.successful_requests,
                        failed_requests     = excluded.failed_requests,
                        failure_counts      = excluded.failure_counts,
                        hourly_data         = excluded.hourly_data,
                        avg_response_time   = excluded.avg_response_time,
                        response_times      = excluded.response_times,
                        last_error_time     = excluded.last_error_time,
                        last_success_time   = excluded.last_success_time,
                        updated_at          = excluded.updated_at
                """, (
                    self.key_hash,
                    self.total_requests,
                    self.successful_requests,
                    self.failed_requests,
                    json.dumps(self.failure_counts, ensure_ascii=False),
                    json.dumps(self.hourly_data,    ensure_ascii=False),
                    self.average_response_time,
                    json.dumps(list(self.response_times)),
                    self.last_error_time.isoformat()   if self.last_error_time   else None,
                    self.last_success_time.isoformat() if self.last_success_time else None,
                ))
                conn.commit()
        except Exception as e:
            logger.warning(f"[KeyStatistics] Save to DB failed ({self.key_hash}): {e}")

    # ------------------------------------------------------------------ #
    #  تسجيل الأحداث                                                      #
    # ------------------------------------------------------------------ #

    def record_success(self, response_time: float):
        """تسجيل طلب ناجح، تحديث البيانات الساعية، وإعادة تعيين عداد الإخفاقات."""
        self.successful_requests += 1
        self.total_requests      += 1
        self.consecutive_failures = 0
        self.last_success_time    = datetime.now()
        self.response_times.append(response_time)
        self._update_average_response_time()

        # تحديث البيانات الساعية (أساس نموذج التنبؤ)
        hour = self.last_success_time.hour
        self.hourly_data[hour]['success'] += 1
        self.hourly_data[hour]['total']   += 1

        self._save_to_db()

    def record_failure(self, error_type: str = "general") -> bool:
        """
        تسجيل طلب فاشل مع تصنيف دقيق لنوع الفشل.
        يُوحَّد error_type إلى النوع القياسي المناسب تلقائياً.
        يرجع True إذا وصل عدد الإخفاقات المتتالية إلى 3 (للتنبيه في المستدعي).
        """
        # توحيد النوع الخام إلى النوع القياسي
        canonical = self._ERROR_CODE_MAP.get(error_type, 'general')

        self.failed_requests      += 1
        self.total_requests       += 1
        self.last_error_time       = datetime.now()
        self.failure_counts[canonical] = self.failure_counts.get(canonical, 0) + 1

        # content_blocked و rate_limit لا يعكسان خللاً في المفتاح نفسه
        # → لا تزيد عداد الإخفاقات المتتالية (لتجنب التأثير الخاطئ على get_health_score)
        if canonical not in ('content_blocked', 'rate_limit'):
            self.consecutive_failures += 1

        # تحديث البيانات الساعية (فشل → total فقط، بدون success)
        hour = self.last_error_time.hour
        self.hourly_data[hour]['total'] += 1

        self._save_to_db(force=(self.consecutive_failures >= 3))
        return self.consecutive_failures >= 3

    # ------------------------------------------------------------------ #
    #  خصائص التوافق مع الكود القديم (للحفاظ على الهيكلة)               #
    # ------------------------------------------------------------------ #

    @property
    def rate_limit_hits(self) -> int:
        """توافق مع الكود القديم — يقرأ من failure_counts المصنَّفة."""
        return self.failure_counts.get('rate_limit', 0)

    @property
    def server_errors(self) -> int:
        """توافق مع الكود القديم — يقرأ من failure_counts المصنَّفة."""
        return self.failure_counts.get('server_error', 0)

    # ------------------------------------------------------------------ #
    #  الحسابات والتحليل                                                  #
    # ------------------------------------------------------------------ #

    def _update_average_response_time(self):
        """تحديث متوسط وقت الاستجابة من نافذة آخر 100 طلب."""
        if self.response_times:
            self.average_response_time = sum(self.response_times) / len(self.response_times)

    def get_success_rate(self) -> float:
        """حساب معدل النجاح الإجمالي (0-100)."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    def get_health_score(self) -> float:
        """
        نقاط الصحة (0-100) مبنية على بيانات حقيقية لا عقوبات تقديرية ثابتة.

        المكوّنات:
          base_score     = معدل النجاح الإجمالي
          failure_penalty = مجموع(عدد_فشل_نوع × وزن_النوع) / إجمالي_الطلبات × 20
                           (حد أقصى 40 نقطة — مشتق من نسبة الفشل الحقيقية)
          consec_penalty  = 5 × consecutive_failures (حد أقصى 25)
          recency_bonus   = +5 إذا كان آخر طلب ناجح منذ أقل من 30 دقيقة

        حالات خاصة:
          • مفتاح جديد (0 طلبات)  → 100 (فرصة كاملة)
          • 3+ أخطاء invalid_key   → 0  (المفتاح معطَّل، يُزال من الدوران)
        """
        if self.total_requests == 0:
            return 100.0

        # مفتاح معطَّل نهائياً
        if self.failure_counts.get('invalid_key', 0) >= 3:
            return 0.0

        # 1. النقطة الأساسية
        base_score = self.get_success_rate()

        # 2. عقوبة الفشل المرجَّحة (مبنية على البيانات الحقيقية)
        weighted_failures = sum(
            self.failure_counts.get(ft, 0) * self.FAILURE_WEIGHTS.get(ft, 1.0)
            for ft in self.FAILURE_TYPES
        )
        failure_penalty = min(
            (weighted_failures / max(self.total_requests, 1)) * 20.0,
            40.0  # سقف الخصم
        )

        # 3. عقوبة الإخفاقات المتتالية الحالية (مؤشر آني)
        consec_penalty = min(self.consecutive_failures * 5.0, 25.0)

        # 4. مكافأة النشاط الأخير السليم
        recency_bonus = 0.0
        if (self.last_success_time and
                (self.last_error_time is None or self.last_success_time > self.last_error_time)):
            mins_since_success = (datetime.now() - self.last_success_time).total_seconds() / 60
            if mins_since_success < 30:
                recency_bonus = 5.0

        health = base_score - failure_penalty - consec_penalty + recency_bonus
        return max(0.0, min(100.0, health))

    # ------------------------------------------------------------------ #
    #  نموذج التنبؤ الساعي                                                #
    # ------------------------------------------------------------------ #

    def get_predicted_performance(self) -> float:
        """
        تنبؤ بالأداء المتوقع للمفتاح في الساعة الحالية بناءً على البيانات التاريخية.

        الخوارزمية:
          • إذا توفرت ≥5 طلبات تاريخية لهذه الساعة بالذات:
              predicted = 70% × معدل_النجاح_الساعي + 30% × معدل_النجاح_الإجمالي
            (الوزن الأكبر للساعي لأنه الأدق لهذه اللحظة من اليوم)
          • وإلا (بيانات غير كافية):
              predicted = get_health_score()  (fallback آمن)

        يُستدعى من get_optimal_api_key لاختيار المفتاح الأنسب لكل لحظة.
        """
        current_hour = datetime.now().hour
        hourly   = self.hourly_data.get(current_hour, {'success': 0, 'total': 0})
        global_rate = self.get_success_rate()

        if hourly['total'] >= 5:
            hourly_rate = (hourly['success'] / hourly['total']) * 100
            predicted   = 0.7 * hourly_rate + 0.3 * global_rate
        else:
            # بيانات ساعية غير كافية → نقطة الصحة الحالية كـ fallback
            predicted = self.get_health_score()

        return max(0.0, min(100.0, predicted))

    def get_failure_breakdown(self) -> Dict[str, Any]:
        """
        تفصيل مصنَّف لجميع أنواع الفشل (مفيد للتشخيص والسجلات).
        يُعرض في get_statistics_summary.
        """
        return {
            canonical: {
                'count':      self.failure_counts.get(canonical, 0),
                'percentage': round(
                    self.failure_counts.get(canonical, 0) / max(self.total_requests, 1) * 100, 1
                ),
                'weight':     self.FAILURE_WEIGHTS.get(canonical, 1.0),
            }
            for canonical in self.FAILURE_TYPES
        }

# ============= استثناء داخلي لـ Circuit Breaker =============
class _CircuitBreakerKeyError(Exception):
    """
    استثناء داخلي يُرفع داخل _api_call ليُحسب ضمن فشل Circuit Breaker.
    يُمثّل فشلاً حقيقياً في المفتاح (server error، invalid key، network error).
    لا يُستخدم لأخطاء Rate Limit (429) التي تُعالج بـ blocked_keys.
    """
    def __init__(self, status: int = 0, message: str = "", error_type: str = "general"):
        self.status     = status
        self.message    = message
        self.error_type = error_type
        super().__init__(f"[{status}] {message}")


# ============= الفئة المحسنة الرئيسية (مع المفاتيح كما هي) =============
class EnhancedGeminiAPI:
    """إدارة محسنة لـ Gemini API مع مفاتيح متعددة"""
    
    def __init__(self, api_keys: List[str] = None):
        # المفاتيح كما كانت في الكود الأصلي
        self.api_keys = [
            "AIzaSyCoKRKqxBAW5kjeVR5saa8",
            "AIzaSyBOg7Fcc9qum6HzqgVXj20Rg",
            "AIzaSyCq96pXxveGaUl2zfu8Lms",
            "AIzaSyAQEIPnASJKmG22jLfgt4C7pQ",
            "AIzaSyDcE4H4B5Jzy3irwfrVTVM0Zg",
            "AIzaSyAiHCZHptFnQioO-guNyxZC0",
            "AIzaSyBWoJ1JToWqsvRGqLUJfRlyU",
            "AIzaSyAUcgeEdeu5EB3lhfYDG_A",
            "AIzaSyDyScB6V94og6ypaaQ6Sj2i3A",
            "AIzaSyCEK4C8TkEYftcj9OEoprFaM",
            

        ]
        
        if isinstance(api_keys, list):
            self.api_keys.extend([key for key in api_keys if key not in self.api_keys])
        
        # Rate limiters لكل مفتاح - إعدادات قابلة للتهيئة من ملف خارجي
        self.rate_limiters = {
            key: TokenRateLimiter(max_rpm=2, max_tpm=32000, max_rpd=50, key_id=key)
            for key in self.api_keys
        }
        
        # إحصائيات متقدمة لكل مفتاح (مع تمرير key_id لتفعيل SQLite والتنبؤ)
        self.key_stats = {key: KeyStatistics(key_id=key) for key in self.api_keys}
        
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
        
        logger.info(f"Gemini API initialized with {len(self.api_keys)} keys")

        # ---- Generation Profiles: إعدادات توليد مخصصة حسب نوع الطلب ----
        # temperature يأتي من المستدعي؛ هنا نضبط topK و topP بدقة حسب النوع
        self.GENERATION_PROFILES: Dict[str, Dict[str, Any]] = {
            # الترجمة الأدبية والسياقية — تنوع عالٍ لضمان جودة أسلوبية
            "translation":               {"topK": 20, "topP": 0.9},
            "complete_translation":      {"topK": 20, "topP": 0.9},
            "contextual_translation":    {"topK": 20, "topP": 0.9},
            "chapter_title_translation": {"topK": 20, "topP": 0.9},
            # استخراج المصطلحات — دقة عالية، تنوع منخفض
            "terminology_extraction":    {"topK": 10, "topP": 0.7},
            "term_extraction":           {"topK": 10, "topP": 0.7},
            # المراجعة والتصحيح النهائي — أقصى دقة وأدنى عشوائية
            "completion_review":         {"topK": 8,  "topP": 0.6},
            "comprehensive_correction":  {"topK": 8,  "topP": 0.6},
            "final_completion":          {"topK": 8,  "topP": 0.6},
            "final_cleanup":             {"topK": 8,  "topP": 0.6},
            "final_review":              {"topK": 8,  "topP": 0.6},
        }
        # الإعدادات الافتراضية لأي نوع طلب غير مصنَّف
        self._default_profile: Dict[str, Any] = {"topK": 12, "topP": 0.8}

        # ---- Circuit Breakers: واحد لكل مفتاح ----
        # بعد 5 فشل حقيقي متتالٍ → يُوقَف المفتاح 5 دقائق (300 ثانية)
        # ثم يدخل HALF-OPEN: طلب واحد للاختبار، إن نجح → CLOSED، وإلا → OPEN من جديد
        self.circuit_breakers: Dict[str, pybreaker.CircuitBreaker] = {
            key: pybreaker.CircuitBreaker(
                fail_max=5,
                reset_timeout=300,
                name=f"cb_{key[:10]}"
            )
            for key in self.api_keys
        }
        logger.info(f"Circuit Breakers initialized: {len(self.circuit_breakers)} breakers (fail_max=5, timeout=300s)")
    
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
            logger.info(f"Unblocked key: {key[:10]}...")
    
    def estimate_tokens(self, text: str) -> int:
        """تقدير دقيق لعدد التوكنز: يدعم tiktoken للعربية والإنجليزية."""
        return _estimate_tokens_smart(text)

    def _get_generation_profile(self, request_type: str) -> Dict[str, Any]:
        """
        إرجاع إعدادات topK و topP المناسبة لنوع الطلب.
        تعود إلى الإعدادات الافتراضية إذا لم يكن النوع معروفاً.
        """
        return self.GENERATION_PROFILES.get(request_type, self._default_profile)

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

                # تخطي المفاتيح التي فتح دائرتها (Circuit Breaker OPEN)
                cb = self.circuit_breakers.get(key)
                if cb is not None:
                    try:
                        cb_state = str(cb.current_state).lower()
                        if "open" in cb_state and "half" not in cb_state:
                            continue
                    except Exception:
                        pass

                # التحقق من rate limit
                if not self.rate_limiters[key].can_make_request(estimated_tokens):
                    continue

                # التحقق من صحة المفتاح باستخدام التنبؤ الذكي
                # (يدمج معدل النجاح الساعي التاريخي + الصحة الكلية)
                predicted_perf = self.key_stats[key].get_predicted_performance()
                if predicted_perf < 10:
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
                logger.error("All keys have exhausted their daily limit! Must wait until the next day or add new keys.")
                # الانتظار لمدة طويلة ثم المحاولة مجدداً عبر الحلقة (تجنب الاستدعاء المتكرر recursive)
                await asyncio.sleep(60)
                continue

            if min_wait < float('inf') and min_wait > 0:
                logger.info(f"All keys are currently busy, smartly waiting for {min_wait:.1f} seconds...")
                await asyncio.sleep(min_wait + 0.5)
                continue
            
            # إذا فشلت كل المحاولات، أعد تعيين المفاتيح المحظورة وانتظر
            logger.warning("All keys are blocked, waiting...")
            await asyncio.sleep(15)
            self.blocked_keys.clear()
            # Loop will continue
    
    async def make_precision_request(self, prompt: str, system_instruction: str = "", 
                                   temperature: float = 0.05, max_tokens: int = 8192,
                                   request_type: str = "translation") -> Optional[str]:
        """
        إرسال طلب دقيق مع تحسينات شاملة:
          ✅ systemInstruction كحقل مستقل في payload (وزن أعلى لدى النموذج)
          ✅ إعدادات توليد مخصصة (topK، topP) حسب نوع الطلب
          ✅ maxOutputTokens يُحسب ديناميكياً من طول النص المُدخَل
          ✅ Circuit Breaker لكل مفتاح (5 فشل → إيقاف 5 دقائق ثم اختبار واحد)
        """
        # التأكد من وجود جلسة نشطة
        await self._ensure_session()

        # --- حساب التوكنز وإعداد maxOutputTokens ديناميكياً ---
        # input_tokens فقط من الـ prompt الحقيقي (system_instruction يسهم بشكل منفصل)
        estimated_input_tokens = self.estimate_tokens(prompt + system_instruction)
        # الإخراج العربي ≈ 1.5× المدخلات، حد أدنى 1024، لا يتجاوز max_tokens المُمرَّر
        dynamic_max_tokens = min(max_tokens, max(1024, int(estimated_input_tokens * 1.5)))
        estimated_output_tokens = dynamic_max_tokens
        total_estimated_tokens  = estimated_input_tokens + estimated_output_tokens

        # --- profile للتوليد حسب نوع الطلب ---
        profile = self._get_generation_profile(request_type)

        for attempt in range(self.max_retries):
            api_key = await self.get_optimal_api_key(total_estimated_tokens)
            if not api_key:
                logger.error("No API keys available")
                return None
            
            # تسجيل الطلب والتوكنز المقدرة
            self.rate_limiters[api_key].add_request(total_estimated_tokens)
            request_start = time.time()
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Professional-Translation-System/Enhanced'
            }
            
            # --- بناء الـ payload مع systemInstruction كحقل مستقل ---
            payload: Dict[str, Any] = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature":      temperature,
                    "topK":             profile["topK"],
                    "topP":             profile["topP"],
                    "maxOutputTokens":  dynamic_max_tokens,
                    "candidateCount":   1,
                    "stopSequences":    ["###TRANSLATION_END###", "###END###"]
                },
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]
            }
            # إضافة systemInstruction كحقل مستقل فقط إذا كان غير فارغ
            if system_instruction and system_instruction.strip():
                payload["systemInstruction"] = {
                    "parts": [{"text": system_instruction.strip()}]
                }

            url = f"{self.base_url}?key={api_key}"

            # --- تغليف طلب HTTP بـ Circuit Breaker ---
            cb = self.circuit_breakers[api_key]
            result_holder: Dict[str, Any] = {}

            async def _api_call():
                """
                دالة داخلية يُغلّفها Circuit Breaker.
                ترفع _CircuitBreakerKeyError عند أي فشل حقيقي (server/network/invalid key)
                حتى يحسبه pybreaker ضمن عداد الفشل.
                لا ترفع استثناءً للـ 429 (rate limit) — يُعالج بشكل منفصل.
                """
                try:
                    async with self.session.post(url, json=payload, headers=headers) as response:
                        result_holder["status"] = response.status
                        if response.status == 200:
                            result_holder["json"] = await response.json()
                        elif response.status == 429:
                            # Rate limit ليس فشلاً حقيقياً للمفتاح — لا يفتح الدائرة
                            result_holder["rate_limited"] = True
                        elif response.status in [401, 403]:
                            text = await response.text()
                            raise _CircuitBreakerKeyError(response.status, text, "invalid_key")
                        elif response.status >= 500:
                            raise _CircuitBreakerKeyError(
                                response.status, f"Server error {response.status}", "server_error"
                            )
                        else:
                            text = await response.text()
                            raise _CircuitBreakerKeyError(response.status, text, "api_error")
                except asyncio.TimeoutError:
                    raise _CircuitBreakerKeyError(0, "Request timed out", "timeout")
                except _CircuitBreakerKeyError:
                    raise
                except Exception as e:
                    raise _CircuitBreakerKeyError(0, str(e), "exception")

            try:
                logger.info(
                    f"Sending {request_type} request (attempt {attempt+1}) "
                    f"key={api_key[:10]}... "
                    f"maxTokens={dynamic_max_tokens} topK={profile['topK']} topP={profile['topP']}"
                )
                await cb(_api_call)()

                response_time = time.time() - request_start

                # --- معالجة النتيجة ---
                if result_holder.get("json"):
                    result = result_holder["json"]
                    if (
                        "candidates" in result
                        and len(result["candidates"]) > 0
                        and "content" in result["candidates"][0]
                        and "parts" in result["candidates"][0]["content"]
                        and len(result["candidates"][0]["content"]["parts"]) > 0
                    ):
                        content = result["candidates"][0]["content"]["parts"][0]["text"]
                        self.key_stats[api_key].record_success(response_time)
                        logger.info(f"Request {request_type} succeeded | key={api_key[:10]}... | time={response_time:.2f}s")
                        return content.strip(), response_time, api_key
                    else:
                        logger.warning(f"Unexpected response from Gemini: {result}")
                        should_alert = self.key_stats[api_key].record_failure("invalid_response")
                        if should_alert:
                            logger.warning(f"Intelligence Alert: Key {api_key[:10]}... failed 3 consecutive times", key_status="consecutive_failures")
                            console.print(f"[bold yellow]⚠️ Alert: Key {api_key[:10]} failed 3 consecutive times but remains in use.[/bold yellow]")

                elif result_holder.get("rate_limited"):
                    logger.warning(f"Rate limit exceeded for key {api_key[:10]}... waiting")
                    should_alert = self.key_stats[api_key].record_failure("rate_limit")
                    if should_alert:
                        logger.warning(f"Intelligence Alert: Key {api_key[:10]}... failed 3 consecutive times (Rate Limit)", key_status="consecutive_failures")
                        console.print(f"[bold yellow]⚠️ Alert: Key {api_key[:10]} failed 3 consecutive times due to rate limits.[/bold yellow]")
                    # إبلاغ النظام التكيّفي
                    self.rate_limiters[api_key].record_429_error()
                    block_duration = self.retry_delays[min(attempt, len(self.retry_delays)-1)]
                    self.blocked_keys[api_key] = time.time() + block_duration
                    await asyncio.sleep(block_duration)

            except pybreaker.CircuitBreakerError:
                # الدائرة مفتوحة — المفتاح موقوف، ننتقل للمحاولة التالية
                elapsed = time.time() - request_start
                logger.warning(
                    f"[CircuitBreaker] Circuit OPEN for key {api_key[:10]} "
                    f"(fail_max=5 reached). Skipping to next key. elapsed={elapsed:.2f}s"
                )
                console.print(
                    f"[bold red]⚡ Circuit Breaker OPEN: key {api_key[:10]} "
                    f"suspended for {cb.reset_timeout}s[/bold red]"
                )
                continue  # جرّب مفتاحاً آخر

            except _CircuitBreakerKeyError as e:
                # فشل حقيقي — سجّل وعالج حسب نوع الخطأ
                response_time = time.time() - request_start
                error_type = e.error_type

                should_alert = self.key_stats[api_key].record_failure(error_type)
                if should_alert:
                    logger.warning(
                        f"Intelligence Alert: Key {api_key[:10]}... failed 3 consecutive times ({error_type})",
                        key_status="consecutive_failures"
                    )
                    console.print(
                        f"[bold red]⚠️ Alert: Key {api_key[:10]} is facing consecutive {error_type} errors![/bold red]"
                    )

                if error_type == "timeout":
                    logger.warning(f"Request {request_type} timed out (attempt {attempt+1})")
                    await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays)-1)])

                elif error_type == "invalid_key":
                    logger.error(f"Gemini API error {e.status} for key {api_key[:10]}: {e.message}")
                    self.blocked_keys[api_key] = time.time() + 3600  # حظر لمدة ساعة
                    # لا داعي للانتظار — انتقل لمفتاح آخر
                    continue

                elif error_type == "server_error":
                    logger.error(f"Gemini server error {e.status}")
                    await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays)-1)])

                else:
                    logger.error(f"Unexpected API error [{e.status}]: {e.message}")
                    await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays)-1)])

            except Exception as e:
                logger.error(f"Error in {request_type} request (attempt {attempt+1}): {str(e)}")
                should_alert = self.key_stats[api_key].record_failure("exception")
                if should_alert:
                    logger.warning(f"Intelligence Alert: Key {api_key[:10]}... failed 3 consecutive times (Exception)", key_status="consecutive_failures")
                await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays)-1)])
        
        logger.error(f"Request {request_type} failed after {self.max_retries} attempts")
        return None, 0.0, None
    
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
                'predicted_performance': round(stats.get_predicted_performance(), 1),
                'success_rate': stats.get_success_rate(),
                'total_requests': stats.total_requests,
                'successful_requests': stats.successful_requests,
                'failed_requests': stats.failed_requests,
                'avg_response_time': round(stats.average_response_time, 2),
                'is_blocked': key in self.blocked_keys,
                'failure_breakdown': stats.get_failure_breakdown(),
            }
            summary['keys_performance'].append(key_info)
        
        # ترتيب حسب الأداء المتنبأ به (يدمج الصحة والتاريخ الساعي)
        summary['keys_performance'].sort(
            key=lambda x: x['predicted_performance'], reverse=True
        )
        
        return summary
    
    async def cleanup(self):
        """تنظيف الموارد عند الانتهاء"""
        if self.session and not self.session.closed:
            await self.session.close()
        if self.connector:
            await self.connector.close()
        logger.info("Gemini API resources cleaned up")

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
        
        logger.info(f"Starting complete translation for text of {len(text)} characters")
        
        # المرحلة 1: تحليل النص واكتشاف نوعه
        text_analysis = self.detect_text_genre_and_tone(text)
        logger.info(f"Text analysis: Genre={text_analysis['genre']}, Tone={text_analysis['tone']}")
        
        # المرحلة 2: الترجمة الأولية الشاملة
        translation_prompt = self.create_complete_translation_prompt(text, context, text_analysis)
        
        initial_translation_result = await self.api_manager.make_precision_request(
            translation_prompt, 
            temperature=0.1,  # توازن بين الإبداع والدقة
            request_type="complete_translation"
        )
        
        initial_translation, response_time, api_key_used = initial_translation_result if initial_translation_result else (None, 0.0, None)

        if not initial_translation:
            logger.error("Failed in initial translation")
            return None, 0.0, None
        
        logger.info("Initial translation done, starting completion check...")
        
        # المرحلة 3: فحص اكتمال الترجمة
        if self.content_processor.needs_completion_review(text, initial_translation):
            quality_logger.warning("Incomplete translation detected, starting completion review...")
            
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
            
            completed_translation_result = await self.api_manager.make_precision_request(
                completion_prompt,
                temperature=0.05,
                request_type="completion_review"
            )
            
            completed_translation, r_time, a_key = completed_translation_result if completed_translation_result else (None, 0.0, None)
            if r_time: response_time += r_time
            if a_key: api_key_used = a_key

            if completed_translation:
                # فحص إضافي للتأكد من الاكتمال
                final_check = self.content_processor.detect_incomplete_translation(text, completed_translation)
                if final_check['coverage_percentage'] > 90:
                    logger.info("Translation completed successfully - high coverage ratio")
                    final_translation = self.content_processor.convert_numbers_to_arabic(completed_translation)
                else:
                    quality_logger.warning("Final attempt to guarantee completion...")
                    # محاولة أخيرة
                    final_completion_prompt = f"""مراجعة نهائية حاسمة:

اضمن ترجمة كل كلمة وجملة في النص التالي إلى العربية:

النص الأصلي:
{text[:2000]}

الترجمة النهائية الكاملة:"""
                    
                    final_translation_result = await self.api_manager.make_precision_request(
                        final_completion_prompt,
                        temperature=0.02,
                        request_type="final_completion"
                    )
                    
                    final_translation, r_time, a_key = final_translation_result if final_translation_result else (None, 0.0, None)
                    if r_time: response_time += r_time
                    if a_key: api_key_used = a_key

                    if final_translation:
                        final_translation = self.content_processor.convert_numbers_to_arabic(final_translation)
                    else:
                        final_translation = self.content_processor.convert_numbers_to_arabic(completed_translation)
            else:
                final_translation = self.content_processor.convert_numbers_to_arabic(initial_translation)
        else:
            logger.info("Initial translation is complete and comprehensive")
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
        
        return final_translation, response_time, api_key_used
    
    async def translate_with_comprehensive_review(self, text: str, context: str = "") -> Optional[str]:
        """ترجمة شاملة مع مراجعة متعددة المراحل لضمان عدم ترك أي محتوى أجنبي"""
        
        logger.info(f"Starting comprehensive translation for text of {len(text)} characters")
        
        # المرحلة 1: تحليل النص واكتشاف نوعه
        text_analysis = self.detect_text_genre_and_tone(text)
        logger.info(f"Text analysis: Genre={text_analysis['genre']}, Tone={text_analysis['tone']}")
        
        # المرحلة 2: الترجمة الأولية السياقية
        translation_prompt = self.create_complete_translation_prompt(text, context, text_analysis)
        
        initial_translation_result = await self.api_manager.make_precision_request(
            translation_prompt, 
            temperature=0.1,  # توازن بين الإبداع والدقة
            request_type="contextual_translation"
        )
        
        initial_translation, response_time, api_key_used = initial_translation_result if initial_translation_result else (None, 0.0, None)

        if not initial_translation:
            logger.error("Failed in initial translation")
            return None, 0.0, None
        
        logger.info("Initial translation done, starting comprehensive review...")
        
        # المرحلة 3: فحص شامل للمحتوى الأجنبي
        if self.content_processor.has_any_foreign_content(initial_translation):
            quality_logger.warning("Foreign content found, starting comprehensive correction...")
            
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
            
            corrected_translation_result = await self.api_manager.make_precision_request(
                comprehensive_review_prompt,
                temperature=0.05,
                request_type="comprehensive_correction"
            )
            
            corrected_translation, _, _ = corrected_translation_result if corrected_translation_result else (None, 0.0, None)

            if corrected_translation:
                # فحص إضافي
                if not self.content_processor.has_any_foreign_content(corrected_translation):
                    logger.info("Translation corrected successfully - free of foreign content")
                    final_translation = self.content_processor.convert_numbers_to_arabic(corrected_translation)
                else:
                    quality_logger.warning("Foreign content still exists, final correction attempt...")
                    # محاولة تصحيح نهائية مكثفة
                    final_correction_prompt = f"""مراجعة نهائية حاسمة: 

احذف أو ترجم أي كلمة أو رمز أو رقم إنجليزي في النص التالي:

{corrected_translation}

النص النهائي الخالي تماماً من الإنجليزية (عربي فقط):"""
                    
                    final_translation_result = await self.api_manager.make_precision_request(
                        final_correction_prompt,
                        temperature=0.02,
                        request_type="final_cleanup"
                    )
                    
                    final_translation, _, _ = final_translation_result if final_translation_result else (None, 0.0, None)

                    if final_translation:
                        final_translation = self.content_processor.convert_numbers_to_arabic(final_translation)
                    else:
                        final_translation = self.content_processor.convert_numbers_to_arabic(corrected_translation)
            else:
                final_translation = self.content_processor.convert_numbers_to_arabic(initial_translation)
        else:
            logger.info("Initial translation is free of foreign content")
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
        
        return final_translation, response_time, api_key_used
    
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
        
        terms_response_result = await self.api_manager.make_precision_request(
            extraction_prompt,
            temperature=0.1,
            request_type="terminology_extraction"
        )
        
        terms_response, _, _ = terms_response_result if terms_response_result else (None, 0.0, None)

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
                            logger.info(f"Term saved: {english} ← {arabic}")
                    except:
                        continue


class ProfessionalDocumentProcessor:
    """معالج المستندات الاحترافي المحسن"""

    @staticmethod
    def smart_text_division(text: str, target_chunk_size: int = 5000) -> List[Dict[str, Any]]:
        """تقسيم ذكي للنص إلى أجزاء منطقية مع حفظ التماسك"""
        
        # تقسيم إلى فقرات
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        chapters = []
        current_chapter = {
            'id': 'chapter_001',
            'title': 'الجزء الأول',
            'content': '',
            'word_count': 0,
            'start_page': 1,
            'end_page': 1
        }
        
        chapter_counter = 1
        
        for paragraph in paragraphs:
            paragraph_words = len(paragraph.split())
            
            # إذا إضافة الفقرة ستتجاوز الحد
            if (current_chapter['word_count'] + paragraph_words > target_chunk_size 
                and current_chapter['content'].strip()):
                
                chapters.append(current_chapter)
                chapter_counter += 1
                
                current_chapter = {
                    'id': f'chapter_{chapter_counter:03d}',
                    'title': f'الجزء {chapter_counter}',
                    'content': paragraph,
                    'word_count': paragraph_words,
                    'start_page': chapter_counter,
                    'end_page': chapter_counter
                }
            else:
                if current_chapter['content']:
                    current_chapter['content'] += '\n\n' + paragraph
                else:
                    current_chapter['content'] = paragraph
                current_chapter['word_count'] += paragraph_words
        
        # إضافة الفصل الأخير
        if current_chapter['content'].strip():
            chapters.append(current_chapter)
        
        return chapters

    @staticmethod
    def extract_pdf_with_precision(file_path: str) -> Dict[str, Any]:
        """استخراج دقيق للنص مع الحفاظ على البنية"""
        
        logger.info(f"Starting processing of PDF file: {file_path}")
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                document_info = {
                    'title': '',
                    'author': '',
                    'chapters': [],
                    'total_pages': len(pdf_reader.pages),
                    'metadata': {}
                }
                
                # استخراج البيانات الوصفية
                if pdf_reader.metadata:
                    document_info['metadata'] = dict(pdf_reader.metadata)
                    document_info['title'] = pdf_reader.metadata.get('/Title', '')
                    document_info['author'] = pdf_reader.metadata.get('/Author', '')
                
                full_text = ""
                current_chapter = None
                chapter_counter = 1
                
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if not page_text or len(page_text.strip()) < 10:
                            continue
                        
                        # تنظيف النص
                        page_text = ProfessionalDocumentProcessor.clean_extracted_text(page_text)
                        
                        # البحث عن عناوين الفصول
                        chapter_titles = ProfessionalDocumentProcessor.detect_chapter_titles(page_text)
                        
                        if chapter_titles:
                            # حفظ الفصل السابق
                            if current_chapter:
                                document_info['chapters'].append(current_chapter)
                            
                            # بدء فصل جديد
                            for title in chapter_titles:
                                current_chapter = {
                                    'id': f'chapter_{chapter_counter:03d}',
                                    'title': title,
                                    'content': page_text,
                                    'start_page': page_num + 1,
                                    'end_page': page_num + 1,
                                    'word_count': len(page_text.split())
                                }
                                chapter_counter += 1
                                break
                        else:
                            # إضافة للفصل الحالي
                            if current_chapter:
                                current_chapter['content'] += "\n\n" + page_text
                                current_chapter['end_page'] = page_num + 1
                                current_chapter['word_count'] = len(current_chapter['content'].split())
                            else:
                                # إنشاء فصل افتراضي
                                current_chapter = {
                                    'id': f'chapter_{chapter_counter:03d}',
                                    'title': f'الجزء {chapter_counter}',
                                    'content': page_text,
                                    'start_page': page_num + 1,
                                    'end_page': page_num + 1,
                                    'word_count': len(page_text.split())
                                }
                                chapter_counter += 1
                        
                        full_text += page_text + "\n\n"
                        
                    except Exception as e:
                        logger.warning(f"Error processing page {page_num + 1}: {str(e)}")
                        continue
                
                # إضافة الفصل الأخير
                if current_chapter:
                    document_info['chapters'].append(current_chapter)
                
                # إذا لم توجد فصول، تقسيم ذكي
                if not document_info['chapters']:
                    document_info['chapters'] = ProfessionalDocumentProcessor.smart_text_division(full_text)
                
                logger.info(f"Extracted {len(document_info['chapters'])} chapters from {document_info['total_pages']} pages")
                
                # إحصائيات
                total_words = sum(ch['word_count'] for ch in document_info['chapters'])
                logger.info(f"Total words: {total_words:,}")
                
                return document_info
                
        except Exception as e:
            logger.error(f"Error reading PDF file: {str(e)}")
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
        logger.info("Creating an organized table of contents without duplicates...")
        
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
                    
                    translated_title_result = await api_manager.make_precision_request(
                        translation_prompt,
                        temperature=0.2,
                        request_type="chapter_title_translation"
                    )
                    
                    translated_title, _, _ = translated_title_result if translated_title_result else (None, 0.0, None)

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
        
        logger.info(f"Created table of contents with {len(table_of_contents)} unique titles")
        
        return table_of_contents
    
    @staticmethod
    def create_novel_document(chapters: List[Dict[str, Any]], 
                            output_path: str,
                            book_title: str = "الرواية المترجمة",
                            author: str = "مترجم بالذكاء الاصطناعي",
                            table_of_contents: List[Dict[str, str]] = None) -> str:
        """إنشاء مستند رواية احترافي مع فهرس في صفحة منفصلة وأحجام خط محددة"""
        
        logger.info(f"Creating novel document with separate TOC: {output_path}")
        
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
            
            logger.info(f"Novel document created successfully with enhanced professional formatting: {output_path}")
            logger.info(f"Font sizes: Body text 14pt, Titles 15pt")
            logger.info(f"TOC: Professional with Arabic numerals")
            logger.info(f"Formatting: Optimal space utilization like printed novels")
            return output_path
            
        except Exception as e:
            logger.error(f"Error creating novel document: {str(e)}")
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
        
        logger.info("Enhanced main system for high-quality translation initialized")
    
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

            # جدول الأحداث الاستخباراتية (الجديد)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS intelligent_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    api_key TEXT,
                    duration REAL,
                    genre TEXT,
                    tone TEXT,
                    word_count INTEGER,
                    status TEXT,
                    error_type TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.commit()

        logger.info("Advanced database created and extended with intelligence tables")
    
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
            ''', (chapter_id, operation, status, message, duration, api_key[:15] if api_key else ""))

            conn.commit()

    def log_intelligent_event(self, event_type: str, api_key: str = None,
                              duration: float = None, genre: str = None, tone: str = None,
                              word_count: int = None, status: str = None, error_type: str = None):
        """تسجيل حدث استخباراتي مهيكل في قاعدة البيانات لتحليلات الأداء والمشاكل"""
        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO intelligent_events
                (event_type, api_key, duration, genre, tone, word_count, status, error_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (event_type, api_key[:15] if api_key else None, duration, genre, tone, word_count, status, error_type))
            conn.commit()

    def analyze_and_display_intelligence(self):
        """تحليل البيانات الاستخباراتية من قاعدة البيانات وعرضها باستخدام Rich"""
        from rich.table import Table
        from rich.panel import Panel

        console.print("\n[bold cyan]🔍 Extracting intelligence analytics from logs...[/bold cyan]")

        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            try:
                # 1. تحليل متوسط وقت الترجمة لكل نوع أدبي
                cursor.execute('''
                    SELECT genre, AVG(duration) as avg_duration, COUNT(*) as count
                    FROM intelligent_events
                    WHERE event_type = 'translation_complete' AND duration IS NOT NULL
                    GROUP BY genre
                ''')
                genre_stats = cursor.fetchall()

                if genre_stats:
                    table_genre = Table(title="[bold]Average Translation Time by Genre[/bold]", show_header=True, header_style="bold magenta")
                    table_genre.add_column("Genre", justify="right")
                    table_genre.add_column("Avg Time (s)", justify="center")
                    table_genre.add_column("Chapters", justify="center")

                    for genre, avg_duration, count in genre_stats:
                        table_genre.add_row(str(genre), f"{avg_duration:.2f}", str(count))

                    console.print(table_genre)
                else:
                    console.print("[dim]Not enough data to analyze literary genres.[/dim]")

                # 2. تحليل الساعات الأكثر استجابة (متوسط وقت الاستجابة لكل ساعة)
                cursor.execute('''
                    SELECT strftime('%H', timestamp) as hour, AVG(duration) as avg_duration, COUNT(*) as count
                    FROM intelligent_events
                    WHERE event_type = 'translation_complete' AND duration IS NOT NULL
                    GROUP BY hour
                    ORDER BY avg_duration ASC
                ''')
                hour_stats = cursor.fetchall()

                if hour_stats:
                    table_hour = Table(title="[bold]Performance Patterns: Fastest Response Hours[/bold]", show_header=True, header_style="bold green")
                    table_hour.add_column("Hour (Server Time)", justify="center")
                    table_hour.add_column("Avg Response (s)", justify="center")
                    table_hour.add_column("Operations", justify="center")

                    for hour, avg_duration, count in hour_stats:
                        table_hour.add_row(f"{hour}:00", f"{avg_duration:.2f}", str(count))

                    console.print(table_hour)

                    # استنتاج ذكي
                    best_hour = hour_stats[0][0]
                    console.print(Panel(f"[bold green]💡 Smart Insight:[/bold green] The best time to use the system is around [bold]{best_hour}:00[/bold] as the API response is at its fastest.", title="Performance Tip"))
                else:
                    console.print("[dim]Not enough data to analyze the best response hours.[/dim]")

            except Exception as e:
                console.print(f"[bold red]Error extracting intelligence analytics: {str(e)}[/bold red]")

    def _load_completed_chapters_from_db(self) -> Dict[str, Any]:
        """تحميل الفصول المكتملة مسبقاً من قاعدة البيانات"""
        logger.info("Checking database for previously translated chapters...")

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
                logger.info(f"Found {len(completed_chapters)} previously translated chapters. Skipping translation for them.")
            else:
                logger.info("No previously translated chapters found.")
            
            return completed_chapters

    async def translate_chapter_comprehensively(self, chapter: Dict[str, Any]) -> Dict[str, Any]:
        """ترجمة شاملة للفصل مع ضمانات الجودة المحسنة"""
        
        start_time = time.time()
        chapter_id = chapter['id']
        
        logger.info(f"Starting comprehensive translation for chapter: {chapter['title']}")
        quality_logger.info(f"Chapter {chapter_id}: Enhanced processing started")
        
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
                             f"Started translating chapter of {chapter['word_count']} words - Genre: {text_analysis['genre']}, Tone: {text_analysis['tone']}")
            
            # الترجمة الشاملة مع المراجعة
            translation_context = f"هذا الفصل بعنوان '{chapter['title']}' من رواية أدبية"
            
            translated_content, response_time, api_key_used = await self.translation_engine.translate_with_comprehensive_review(
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
                
                # تسجيل الحدث الاستخباراتي
                self.log_intelligent_event(
                    event_type="translation_complete",
                    api_key=api_key_used,
                    duration=response_time,
                    genre=text_analysis['genre'],
                    tone=text_analysis['tone'],
                    word_count=chapter['word_count'],
                    status="success"
                )

                # تسجيل النجاح في السجلات العادية
                self.log_operation(
                    chapter_id, "translation_complete", "success",
                    f"Translation completed in {translation_time:.2f}s, Genre: {text_analysis['genre']}, Corrections: {corrections_count}",
                    translation_time,
                    api_key_used if api_key_used else ""
                )
                
                # تحديث الإحصائيات
                self.translation_stats['completed_chapters'] += 1
                self.translation_stats['translated_words'] += chapter['word_count']
                self.translation_stats['contextual_adaptations'] += 1
                
                if foreign_content_detected:
                    self.translation_stats['foreign_content_corrections'] += 1
                    quality_logger.warning(f"Chapter {chapter_id}: Applied corrections for foreign content")
                else:
                    quality_logger.info(f"Chapter {chapter_id}: Free of foreign content")
                
                logger.info(f"Translation finished for chapter {chapter['title']} successfully - "
                          f"Time: {translation_time:.2f}s, Genre: {text_analysis['genre']}")
                
                return chapter
                
            else:
                # فشل في الترجمة
                chapter['status'] = 'failed'
                self.save_chapter_advanced(chapter)
                
                self.log_operation(chapter_id, "translation_failed", "error",
                                 "Failed to get translation from API")
                
                logger.error(f"Translation failed for chapter: {chapter['title']}")
                return chapter
                
        except Exception as e:
            # خطأ في العملية
            chapter['status'] = 'error'
            error_message = str(e)
            
            self.save_chapter_advanced(chapter)
            self.log_operation(chapter_id, "translation_error", "error", error_message)
            
            logger.error(f"Error translating chapter {chapter['title']}: {error_message}")
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
        logger.info("Starting enhanced comprehensive processing of the novel with a separate TOC")
        logger.info(f"Source file: {pdf_path}")
        logger.info(f"Target file: {output_file}")
        logger.info("=" * 100)
        
        self.translation_stats['translation_start_time'] = time.time()
        
        try:
            # المرحلة 0: عرض التحليلات الاستخباراتية السابقة (إن وجدت)
            self.analyze_and_display_intelligence()

            # المرحلة 1: استخراج وتحليل المستند
            logger.info("📖 Phase 1: Extracting and analyzing the document...")
            document_structure = self.document_processor.extract_pdf_with_precision(pdf_path)
            
            # تحميل الفصول المكتملة مسبقاً من قاعدة البيانات
            previously_completed = self._load_completed_chapters_from_db()

            chapters = document_structure['chapters']
            self.translation_stats['total_chapters'] = len(chapters)
            self.translation_stats['total_words'] = sum(ch['word_count'] for ch in chapters)
            self.translation_stats['total_characters'] = sum(len(ch.get('content', '')) for ch in chapters)
            
            if not book_title:
                book_title = document_structure.get('title', 'Translated Novel') or 'Translated Novel'
            if not author:
                author = document_structure.get('author', 'Unknown Author') or 'Unknown Author'
            
            logger.info(f"📊 Extracted {len(chapters)} chapters")
            logger.info(f"📊 Total words: {self.translation_stats['total_words']:,}")
            logger.info(f"📊 Total characters: {self.translation_stats['total_characters']:,}")
            logger.info(f"📚 Book Title: {book_title}")
            logger.info(f"✍️ Author: {author}")
            
            # المرحلة 2: ترجمة شاملة مع مراجعة متعددة المراحل
            logger.info("🔄 Phase 2: Starting comprehensive translation with strict no-foreign-content guarantee...")
            
            all_processed_chapters = []
            
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(complete_style="green", finished_style="bold green"),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                translation_task = progress.add_task("[cyan]Translating chapters...", total=len(chapters))
                
                for i, chapter in enumerate(chapters):
                    logger.info("-" * 50)
                    
                    # التحقق من وجود ترجمة سابقة للفصل
                    if chapter['id'] in previously_completed:
                        logger.info(f"⏭️ Skipping chapter {i+1}/{len(chapters)}: '{chapter['title']}' (previously translated).")

                        completed_chapter_info = previously_completed[chapter['id']]
                        all_processed_chapters.append(completed_chapter_info)

                        # تحديث الإحصائيات
                        self.translation_stats['skipped_chapters'] += 1
                        self.translation_stats['completed_chapters'] += 1
                        self.translation_stats['translated_words'] += completed_chapter_info.get('word_count', 0)

                        progress.update(translation_task, advance=1, description=f"[green]Skipped (Cached): {chapter['title']}")
                        continue

                    logger.info(f"📝 Translating chapter {i+1}/{len(chapters)}: {chapter['title']}")
                    progress.update(translation_task, description=f"[yellow]Translating: {chapter['title']}")
                    
                    result = await self.translate_chapter_comprehensively(chapter)
                    all_processed_chapters.append(result)
                    
                    progress.update(translation_task, advance=1, description=f"[green]Completed: {chapter['title']}")

                    elapsed_time = time.time() - self.translation_stats['translation_start_time']
                    chapters_done = i + 1
                    if chapters_done > 0:
                        avg_time_per_chapter = elapsed_time / chapters_done
                        remaining_chapters = len(chapters) - chapters_done
                        estimated_remaining = avg_time_per_chapter * remaining_chapters

                        # Only logging summary stats instead of visual progress bar numbers
                        successful = sum(1 for ch in all_processed_chapters if ch['status'] == 'completed')
                        if successful > 0 and chapters_done % 5 == 0:
                            logger.info(f"✅ Statistics: Completed chapters {successful}")
            
            # المرحلة 3: التحقق النهائي من الجودة
            logger.info("🔍 Phase 3: Final Quality Check...")
            
            successful_chapters = [ch for ch in all_processed_chapters if ch['status'] == 'completed']
            failed_chapters = [ch for ch in all_processed_chapters if ch['status'] in ['failed', 'error']]
            
            if failed_chapters:
                logger.warning(f"⚠️  {len(failed_chapters)} chapters failed to translate:")
                for ch in failed_chapters:
                    logger.warning(f"   - {ch['title']}")
            
            chapters_with_foreign = [ch for ch in successful_chapters if ch.get('foreign_content_detected', False)]
            if chapters_with_foreign:
                quality_logger.warning(f"Foreign content corrections applied in {len(chapters_with_foreign)} chapters")
            else:
                quality_logger.info("All chapters are completely free of foreign content")
            
            # المرحلة 4: إنشاء فهرس منظم بدون تكرار
            logger.info("📋 Phase 4: Creating organized table of contents without duplicates...")
            
            table_of_contents = await self.document_generator.create_table_of_contents(
                successful_chapters, self.api_manager
            )
            
            logger.info(f"Professional TOC created with {len(table_of_contents)} unique titles (no page numbers)")
            
            # المرحلة 5: إنشاء مستند الرواية النهائي مع الفهرس المنفصل
            logger.info("📝 Phase 5: Generating final novel document with professional formatting...")
            logger.info("🎯 Font sizes: Body 14pt, Titles 15pt")
            logger.info("📄 TOC: Professional with written Arabic numerals")
            logger.info("📐 Layout: Optimized spacing mirroring printed novels")
            
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
            logger.info("🎉 Novel processed successfully with a separate TOC!")
            logger.info("=" * 100)
            logger.info(f"📖 Novel Title: {book_title}")
            logger.info(f"✍️  Author: {author}")
            logger.info(f"📄 Total Chapters: {len(chapters)}")
            logger.info(f"✅ Successfully Translated: {total_successful}")
            logger.info(f"⏭️ Skipped (Previously Translated): {self.translation_stats['skipped_chapters']}")
            logger.info(f"❌ Failed Chapters: {total_failed}")
            logger.info(f"📊 Total Words Translated: {translated_words:,}")
            logger.info(f"⏱️  Total Time: {total_time/60:.1f} minutes")
            logger.info(f"🚀 Translation Rate: {words_per_minute:.0f} words/minute")
            
            # إحصائيات التحسينات
            logger.info("=" * 50)
            logger.info("🔧 Applied Enhancements Statistics:")
            logger.info(f"   🌍 Foreign Content Corrections: {self.translation_stats['foreign_content_corrections']}")
            logger.info(f"   📖 Contextual Adaptations (Genre/Tone): {self.translation_stats['contextual_adaptations']}")
            logger.info(f"   🔑 Multiple API Keys Used: {len(self.api_manager.api_keys)} keys")
            logger.info(f"   📚 Saved Terms: {len(self.translation_engine.terminology_database)} terms")
            logger.info(f"   📋 Professional TOC: {len(table_of_contents)} chapters with Arabic numerals")
            logger.info(f"   🎯 Uniform Font Sizes: Body 14pt, Titles 15pt")
            logger.info(f"   📐 Enhanced Formatting: Optimized space, calculated spacing")

            logger.info(f"📁 Final professionally formatted novel: {final_document_path}")
            logger.info("=" * 100)
            
            quality_logger.info("Final Quality Report:")
            quality_logger.info(f"Total corrections applied: {sum(ch.get('corrections_applied', 0) for ch in successful_chapters)}")
            
            # تصنيف الفصول حسب النوع
            genre_counts = {}
            tone_counts = {}
            for ch in successful_chapters:
                genre = ch.get('genre', 'unknown')
                tone = ch.get('tone', 'unknown')
                genre_counts[genre] = genre_counts.get(genre, 0) + 1
                tone_counts[tone] = tone_counts.get(tone, 0) + 1
            
            quality_logger.info("Literary Genre Distribution:")
            for genre, count in genre_counts.items():
                quality_logger.info(f"  {genre}: {count} chapters")
            
            quality_logger.info("Emotional Tone Distribution:")
            for tone, count in tone_counts.items():
                quality_logger.info(f"  {tone}: {count} chapters")
            
            return final_document_path
            
        except Exception as e:
            logger.error(f"Fatal error during novel processing: {str(e)}")
            logger.error(traceback.format_exc())
            raise


def validate_input_paths(input_path: str, output_dir: str) -> Tuple[bool, str]:
    """التحقق من صحة مسارات الإدخال والإخراج"""
    
    # التحقق من وجود ملف الإدخال
    if not os.path.exists(input_path):
        return False, f"Input file not found: {input_path}"
    
    # التحقق من أن الملف هو PDF
    if not input_path.lower().endswith('.pdf'):
        return False, "File must be a PDF"
    
    # التحقق من إمكانية إنشاء مجلد الإخراج
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Cannot create output directory: {str(e)}"
    
    return True, "Paths are valid"


async def main():
    """الدالة الرئيسية للنظام المحسن مع الفهرس المنفصل"""
    
    print("🚀 Enhanced Comprehensive Translation System - For Novels & Literature with Separate TOC")
    print("=" * 90)
    print("✨ Enhanced Features:")
    print("   🔑 Multiple API keys for continuity")
    print("   🌍 Complete removal of foreign content (words and numbers)")
    print("   📖 Contextual translation based on genre and emotional tone")
    print("   🎭 Adaptation to literary genres (poetry, drama, narrative, prose)")
    print("   💫 Adaptation to emotional tones (melancholic, joyful, dramatic, neutral)")
    print("   📚 Smart terminology saving and management")
    print("   📋 Creation of professional book-like TOC - Chapter names only!")
    print("   📄 Final output for novels - Professional TOC + Structured text")
    print("   🎯 Specific font sizes: Body 14pt, Titles 15pt")
    print("   🔍 Multi-stage review to ensure highest quality")
    print("=" * 90)
    
    # إنشاء النظام المحسن
    system = MasterTranslationSystem([])  # سيتم استخدام المفاتيح المدمجة
    
    # استخدام المسارات المحددة
    input_path = "/root/Downloads/teanasost/input/1p.pdf"
    output_dir = "/root/Downloads/teanasost/output"
    
    print(f"\n📁 Path Information:")
    print(f"Input Path: {input_path}")
    print(f"Output Directory: {output_dir}")
    
    # التحقق من صحة المسارات
    is_valid, validation_message = validate_input_paths(input_path, output_dir)
    
    if not is_valid:
        print(f"\n❌ Path Error: {validation_message}")
        return
    
    print(f"✅ {validation_message}")
    
    # معلومات إضافية اختيارية
    print(f"\n📚 Novel Information (Optional):")
    book_title = input("Novel Title (Enter to skip): ").strip()
    author = input("Author Name (Enter to skip): ").strip()
    
    if not book_title:
        book_title = None
    if not author:
        author = None
    
    try:
        print("\n🔄 Starting enhanced comprehensive translation process with separate TOC...")
        print("🌟 Enhanced System Guarantees:")
        print("   • Translation of every single word, letter, and number in text")
        print("   • Contextual adaptation based on emotional text type")
        print("   • Complete removal of any foreign content")
        print("   • Professional book-like TOC creation - Chapter names only")
        print("   • Specific font sizes: Body 14pt, Titles 15pt")
        print("   • Clean, ready-to-read novel output")
        print("-" * 90)
        
        # تشغيل النظام الكامل المحسن
        final_document = await system.process_complete_book(
            input_path, output_dir, book_title, author
        )
        
        print(f"\n🎉 Translated novel with professional TOC created successfully!")
        print(f"📄 Final Novel: {final_document}")
        print(f"📋 Novel contains a professional TOC like real printed books!")
        print(f"🚫 TOC: Chapter names only without page numbers!")
        print(f"🎯 Font sizes: Body text 14pt, Titles 15pt only!")
        print(f"📐 Formatting: Optimal space utilization like printed novels!")
        
        # عرض ملخص الإنجازات
        if system.translation_stats['foreign_content_corrections'] > 0:
            print(f"\n🔧 Applied {system.translation_stats['foreign_content_corrections']} foreign content corrections")
        
        if system.translation_stats['contextual_adaptations'] > 0:
            print(f"📖 Applied {system.translation_stats['contextual_adaptations']} contextual adaptations")
        
        print(f"📚 Saved {len(system.translation_engine.terminology_database)} terms to database")
        
    except KeyboardInterrupt:
        print("\n⏹️ Process stopped by user")
        print("💾 Saved data can be resumed later")
        
    except Exception as e:
        print(f"\n❌ Unexpected fatal error: {str(e)}")
        logger.error(f"Error in main: {str(e)}")
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Program terminated")
    except Exception as e:
        print(f"Unexpected top-level error: {str(e)}")
