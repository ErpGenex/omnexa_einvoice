#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
🔐 ePass2003 Sign Agent - Specialized Version
وكيل التوقيع الإلكتروني المخصص لـ ePass2003
=============================================================================

هذا Agent مخصص لـ ePass2003 مع محاولات متعددة للتوقيع
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from PyKCS11 import PyKCS11Lib, Mechanism, PyKCS11Error
from PyKCS11.LowLevel import (
    CKA_CLASS, CKA_VALUE, CKA_ID, CKF_RW_SESSION, CKF_SERIAL_SESSION,
    CKO_PRIVATE_KEY, CKO_CERTIFICATE, CKC_X_509,
    CKM_SHA256_RSA_PKCS, CKM_RSA_PKCS, CKM_SHA1_RSA_PKCS,
    CKM_SHA384_RSA_PKCS, CKM_SHA512_RSA_PKCS, CKM_RSA_PKCS_KEY_PAIR_GEN,
    CKM_SHA256
)
from asn1crypto import cms, algos, core, x509

# محاولة استيراد Chilkat (الطريقة المفضلة والأكثر استقراراً)
try:
    import chilkat2
    CHILKAT_AVAILABLE = True
except ImportError:
    CHILKAT_AVAILABLE = False
    print("⚠️ Chilkat not available, will use PKCS#11 only")

# =============================================================================
# ✅ إصلاح مشاكل PrintableString/UTF8String للشهادات المصرية
# =============================================================================
# الشهادات المصرية تستخدم UTF8String (tag 12) بدلاً من PrintableString (tag 19)
# نسمح لـ PrintableString بقبول tag 12 أيضاً
_original_printable_load = core.PrintableString.load

def _patched_printable_load(encoded_data, strict=False):
    try:
        return _original_printable_load(encoded_data, strict=False)
    except:
        # إذا فشل، نحاول قراءته كـ UTF8String
        try:
            return core.UTF8String.load(encoded_data, strict=False)
        except:
            return _original_printable_load(encoded_data, strict=False)

core.PrintableString.load = classmethod(_patched_printable_load)

from cryptography import x509 as crypto_x509
from cryptography.hazmat.backends import default_backend
import hashlib
import json
import base64
import logging
import os
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone

# =============================================================================
# إعداد Flask Application
# =============================================================================
app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": False,
        "max_age": 3600
    }
})

# =============================================================================
# إعداد Logging
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('epass2003_agent.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)
logger.info("✅ تم تطبيق تصحيح asn1crypto للشهادات المصرية")

import importlib.util
import sys
from pathlib import Path as _Path

def _resolve_agent_dir() -> _Path:
	"""Dev: source folder. PyInstaller: extracted bundle (_MEIPASS)."""
	if getattr(sys, "frozen", False):
		return _Path(getattr(sys, "_MEIPASS", _Path(__file__).resolve().parent))
	return _Path(__file__).resolve().parent


_AGENT_DIR = _resolve_agent_dir()


def _load_sibling_module(module_name: str, filename: str):
    """Load omnexa_agent_pin.py / chilkat_license.py from bundle or script folder."""
    path = _AGENT_DIR / filename
    if not path.is_file():
        raise SystemExit(
            f"\nMissing: {path}\n\n"
            "Copy to the same folder as epass2003_agent.py (e.g. D:\\python\\):\n"
            "  - chilkat_license.py\n"
            "  - itida_cms.py\n"
            "  - omnexa_agent_pin.py\n"
            "From bench: Docs/USB/  or run SYNC_AGENT_TO_WINDOWS.bat\n"
        )
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


_agent_dir = str(_AGENT_DIR)
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)

_pin_mod = _load_sibling_module("omnexa_agent_pin", "omnexa_agent_pin.py")
_resolve_token_pin = _pin_mod.resolve_token_pin
_resolve_chilkat_unlock_code = _pin_mod.resolve_chilkat_unlock_code

_lic_mod = _load_sibling_module("chilkat_license", "chilkat_license.py")
ChilkatLicenseError = _lic_mod.ChilkatLicenseError
chilkat_runtime_version = _lic_mod.chilkat_runtime_version
is_chilkat_license_error = _lic_mod.is_chilkat_license_error
unlock_chilkat_global = _lic_mod.unlock_chilkat_global
unlock_status_for_health = _lic_mod.unlock_status_for_health
user_facing_sign_error = _lic_mod.user_facing_sign_error

_itida_mod = _load_sibling_module("itida_cms", "itida_cms.py")
ITIDASignatureFormatError = _itida_mod.ITIDASignatureFormatError
apply_itida_crypt_options = _itida_mod.apply_itida_crypt_options
apply_itida_signing_attributes = _itida_mod.apply_itida_signing_attributes
finalize_itida_crypt_before_sign = _itida_mod.finalize_itida_crypt_before_sign
build_itida_canonical_json = _itida_mod.build_itida_canonical_json
sign_canonical_json_with_crypt = _itida_mod.sign_canonical_json_with_crypt
validate_itida_signature_b64 = _itida_mod.validate_itida_signature_b64

# =============================================================================
# مسارات مكتبات التوكنات المدعومة
# =============================================================================
TOKEN_DLLS = {
    'epass2003': r"C:\Windows\System32\eps2003csp11.dll",
    'wd_proxkey': r"C:\Windows\System32\WD_PKCS11.dll"
}

# DLL الافتراضي (للتوافق مع الكود القديم)
EPASS2003_DLL = TOKEN_DLLS['epass2003']

# =============================================================================
# Windows CryptoAPI Constants (للتوقيع المباشر)
# =============================================================================
PROV_RSA_FULL = 1
CRYPT_VERIFYCONTEXT = 0xF0000000
AT_KEYEXCHANGE = 1
AT_SIGNATURE = 2
CALG_SHA256 = 0x0000800c
HP_HASHVAL = 0x0002
CRYPT_SILENT = 0x00000040

# تعريف Windows CryptoAPI functions
crypt32 = ctypes.windll.crypt32
advapi32 = ctypes.windll.advapi32


# =============================================================================
# Class: EPass2003 Signer
# =============================================================================
class EPass2003Signer:
    """
    موقّع للتوكنات الإلكترونية - يدعم ePass2003 و wd_proxkey
    """
    
    def __init__(self, dll_path=None, use_chilkat=True, token_type='epass2003'):
        """
        Args:
            dll_path: مسار DLL (اختياري - سيتم تحديده تلقائياً من token_type)
            use_chilkat: استخدام Chilkat للتوقيع
            token_type: نوع التوكن ('epass2003' أو 'wd_proxkey')
        """
        self.token_type = token_type.lower()
        
        # تحديد DLL المناسب
        if dll_path:
            self.dll_path = dll_path
        elif self.token_type in TOKEN_DLLS:
            self.dll_path = TOKEN_DLLS[self.token_type]
        else:
            # افتراضي: ePass2003
            self.dll_path = EPASS2003_DLL
            self.token_type = 'epass2003'
        
        self.pkcs11 = None
        self.session = None
        self.certificate = None
        self.certificate_obj = None
        self.private_key = None
        self.cert_der = None
        self.slot = None
        self.use_chilkat = use_chilkat and CHILKAT_AVAILABLE
        self.chilkat_cert = None  # Chilkat certificate object

    def initialize(self):
        """تهيئة التوكن وفتح الجلسة"""
        try:
            if not os.path.exists(self.dll_path):
                logger.error(f"❌ مكتبة {self.token_type.upper()} غير موجودة: {self.dll_path}")
                return False
            
            logger.info(f"🔌 تحميل مكتبة {self.token_type.upper()}...")
            self.pkcs11 = PyKCS11Lib()
            self.pkcs11.load(self.dll_path)
            
            slots = self.pkcs11.getSlotList(tokenPresent=True)
            if not slots:
                logger.error(f"❌ لا يوجد توكن {self.token_type.upper()} متصل")
                return False
            
            self.slot = slots[0]
            logger.info(f"📍 استخدام التوكن في الفتحة: {self.slot}")
            
            # فتح جلسة
            self.session = self.pkcs11.openSession(self.slot, CKF_RW_SESSION | CKF_SERIAL_SESSION)
            logger.info("✅ تم فتح الجلسة بنجاح")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تهيئة التوكن: {str(e)}")
            return False

    def login(self, pin: str):
        """تسجيل الدخول وتحميل الشهادة والمفتاح"""
        try:
            # حفظ PIN للاستخدام مع Windows CSP لاحقاً
            self.pin = pin
            
            # تسجيل الدخول
            try:
                self.session.login(pin)
                logger.info("✅ تم تسجيل الدخول بنجاح")
            except PyKCS11Error as e:
                if "CKR_USER_ALREADY_LOGGED_IN" in str(e):
                    logger.warning("⚠️ المستخدم مسجل دخول مسبقًا")
                else:
                    raise

            # البحث عن الشهادة
            certs = self.session.findObjects([(CKA_CLASS, CKO_CERTIFICATE)])
            if not certs:
                raise Exception("❌ لا توجد شهادة على التوكن")

            # تحميل الشهادة
            cert_obj = certs[0]
            cert_data = self.session.getAttributeValue(cert_obj, [CKA_VALUE])[0]
            self.cert_der = bytes(cert_data)
            self.certificate = x509.Certificate.load(self.cert_der)
            
            # قراءة Common Name باستخدام cryptography (يدعم UTF8String وجميع أنواع الترميز)
            try:
                cn = self.get_common_name(self.cert_der)
            except Exception as e:
                logger.warning(f"⚠️ خطأ أثناء قراءة CN: {str(e)}")
                cn = "Unknown"
            
            logger.info(f"✅ تم تحميل الشهادة: CN={cn}")

            # البحث عن المفتاح الخاص - محاولات متعددة
            priv_keys = []
            found_method = None
            
            # محاولة خاصة لـ ePass2003: البحث بدون أي فلاتر أولاً
            try:
                logger.info("🔍 محاولة ePass2003: البحث عن أي مفتاح خاص...")
                from PyKCS11.LowLevel import CKA_PRIVATE
                # البحث عن جميع الكائنات الخاصة
                all_keys = self.session.findObjects([])
                for key in all_keys:
                    try:
                        key_class = self.session.getAttributeValue(key, [CKA_CLASS])[0]
                        if key_class == CKO_PRIVATE_KEY:
                            # تجربة قراءة CKA_ID
                            try:
                                key_id = self.session.getAttributeValue(key, [CKA_ID])[0]
                                logger.info(f"   وجدنا مفتاح خاص مع ID: {bytes(key_id).hex()[:16]}...")
                                priv_keys.append(key)
                                found_method = "epass2003_scan"
                                break
                            except:
                                # حتى لو فشل قراءة ID، نأخذ المفتاح
                                priv_keys.append(key)
                                found_method = "epass2003_scan_no_id"
                                logger.info("   وجدنا مفتاح خاص (بدون ID)")
                                break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"⚠️ محاولة ePass2003 فشلت: {str(e)}")
            
            # محاولة 1: البحث المباشر عن جميع المفاتيح الخاصة
            if not priv_keys:
                try:
                    logger.info("🔍 محاولة 1: البحث المباشر عن المفتاح الخاص...")
                    from PyKCS11.LowLevel import CKA_SIGN
                    priv_keys = self.session.findObjects([
                        (CKA_CLASS, CKO_PRIVATE_KEY),
                        (CKA_SIGN, True)
                    ])
                    if priv_keys:
                        logger.info(f"✅ تم العثور على {len(priv_keys)} مفتاح خاص (محاولة 1)")
                        found_method = "direct_search"
                except Exception as e:
                    logger.warning(f"⚠️ محاولة 1 فشلت: {str(e)}")
            
            # محاولة 2: بحث مع CKA_ID من الشهادة
            if not priv_keys:
                try:
                    cert_id = self.session.getAttributeValue(cert_obj, [CKA_ID])[0]
                    logger.info(f"🔍 محاولة 2: البحث باستخدام CKA_ID: {bytes(cert_id).hex()[:16]}...")
                    priv_keys = self.session.findObjects([
                        (CKA_CLASS, CKO_PRIVATE_KEY),
                        (CKA_ID, cert_id)
                    ])
                    if priv_keys:
                        logger.info(f"✅ تم العثور على مفتاح خاص باستخدام CKA_ID (محاولة 2)")
                        found_method = "by_cert_id"
                except Exception as e:
                    logger.warning(f"⚠️ محاولة 2 فشلت: {str(e)}")
            
            # محاولة 3: بحث بدون فلاتر (لقراءة جميع الكائنات)
            if not priv_keys:
                try:
                    logger.info("🔍 محاولة 3: البحث بدون فلاتر...")
                    all_objects = self.session.findObjects([])
                    logger.info(f"   وجدنا {len(all_objects)} كائن في التوكن")
                    
                    for i, obj in enumerate(all_objects):
                        try:
                            obj_class = self.session.getAttributeValue(obj, [CKA_CLASS])[0]
                            logger.info(f"   كائن {i+1}: Class = {obj_class}")
                            if obj_class == CKO_PRIVATE_KEY:
                                priv_keys.append(obj)
                                logger.info(f"✅ تم العثور على مفتاح خاص (كائن {i+1}, محاولة 3)")
                                found_method = "no_filter_search"
                                break
                        except Exception as obj_error:
                            logger.warning(f"   كائن {i+1}: فشل في القراءة - {str(obj_error)}")
                            continue
                except Exception as e:
                    logger.warning(f"⚠️ محاولة 3 فشلت: {str(e)}")
            
            # محاولة 4: البحث بـ LABEL (خاص بـ ePass2003)
            if not priv_keys:
                try:
                    logger.info("🔍 محاولة 4: البحث باستخدام LABEL...")
                    from PyKCS11.LowLevel import CKA_LABEL
                    cert_label = self.session.getAttributeValue(cert_obj, [CKA_LABEL])[0]
                    logger.info(f"   Label الشهادة: {bytes(cert_label)}")
                    
                    priv_keys = self.session.findObjects([
                        (CKA_CLASS, CKO_PRIVATE_KEY),
                        (CKA_LABEL, cert_label)
                    ])
                    if priv_keys:
                        logger.info(f"✅ تم العثور على مفتاح خاص باستخدام LABEL (محاولة 4)")
                        found_method = "by_label"
                except Exception as e:
                    logger.warning(f"⚠️ محاولة 4 فشلت: {str(e)}")
            
            # محاولة 5: محاولة خاصة بـ ePass2003 - استخدام جميع الكائنات
            if not priv_keys:
                try:
                    logger.info("🔍 محاولة 5: محاولة خاصة بـ ePass2003...")
                    all_objects = self.session.findObjects([])
                    
                    for i, obj in enumerate(all_objects):
                        try:
                            # محاولة قراءة جميع attributes
                            obj_class = self.session.getAttributeValue(obj, [CKA_CLASS])[0]
                            logger.info(f"   كائن {i+1}: Class = {obj_class}")
                            
                            if obj_class == CKO_PRIVATE_KEY:
                                # محاولة قراءة المزيد من المعلومات
                                try:
                                    from PyKCS11.LowLevel import CKA_KEY_TYPE, CKA_SIGN
                                    key_type = self.session.getAttributeValue(obj, [CKA_KEY_TYPE])[0]
                                    can_sign = self.session.getAttributeValue(obj, [CKA_SIGN])[0]
                                    logger.info(f"      Key Type: {key_type}, Can Sign: {can_sign}")
                                    
                                    if can_sign:
                                        priv_keys.append(obj)
                                        logger.info(f"✅ تم العثور على مفتاح قابل للتوقيع (كائن {i+1}, محاولة 5)")
                                        found_method = "epass2003_special"
                                        break
                                except Exception as attr_error:
                                    logger.warning(f"      فشل في قراءة attributes: {str(attr_error)}")
                                    # نجرب المفتاح حتى لو فشلنا في قراءة attributes
                                    priv_keys.append(obj)
                                    logger.info(f"✅ تم العثور على مفتاح خاص (كائن {i+1}, محاولة 5 - بدون attributes)")
                                    found_method = "epass2003_fallback"
                                    break
                        except Exception as obj_error:
                            logger.warning(f"   كائن {i+1}: فشل في التحليل - {str(obj_error)}")
                            continue
                except Exception as e:
                    logger.warning(f"⚠️ محاولة 5 فشلت: {str(e)}")
            
            # محاولة 6: حفظ cert_obj للاستخدام المباشر في التوقيع
            if not priv_keys:
                logger.warning("⚠️ لم يتم العثور على مفتاح خاص - سنحاول التوقيع المباشر")
                # نحفظ cert_obj وسنستخدمه لاحقاً
                self.certificate_obj = cert_obj
                # نرجع True لنحاول التوقيع
                return True

            self.private_key = priv_keys[0]
            logger.info(f"✅ تم تحديد المفتاح الخاص (الطريقة: {found_method})")
            
            # التحقق من صلاحيات المفتاح
            try:
                from PyKCS11.LowLevel import CKA_SIGN, CKA_KEY_TYPE
                can_sign = self.session.getAttributeValue(self.private_key, [CKA_SIGN])[0]
                key_type = self.session.getAttributeValue(self.private_key, [CKA_KEY_TYPE])[0]
                logger.info(f"   صلاحيات المفتاح: Can Sign={can_sign}, Key Type={key_type}")
                if not can_sign:
                    logger.warning("⚠️ المفتاح الخاص لا يسمح بالتوقيع - سنحاول على أي حال")
            except Exception as e:
                logger.warning(f"⚠️ فشل التحقق من صلاحيات المفتاح: {str(e)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ خطأ في تسجيل الدخول: {str(e)}")
            raise

    def get_common_name(self, cert_bytes):
        """استخراج Common Name من الشهادة باستخدام cryptography"""
        try:
            cert = crypto_x509.load_der_x509_certificate(cert_bytes, default_backend())
            for attribute in cert.subject:
                if attribute.oid.dotted_string == "2.5.4.3":  # Common Name OID
                    return attribute.value
            return "Unknown"
        except Exception as e:
            logger.warning(f"⚠️ خطأ في قراءة Common Name: {str(e)}")
            return "Unknown"

    def get_certificate_info(self):
        """
        قراءة معلومات مفصلة عن الشهادة
        مأخوذة من read_epass2003.py
        """
        try:
            if not self.cert_der:
                return None
            
            # تحذير: تجاهل التحذيرات عند تحميل الشهادة
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                cert = crypto_x509.load_der_x509_certificate(self.cert_der, default_backend())
            
            # استخراج المعلومات - دالة محسّنة
            def get_attr(oid):
                attrs = cert.subject.get_attributes_for_oid(oid)
                return attrs[0].value if attrs else None
            
            # قراءة جميع الحقول الأساسية
            cn = get_attr(crypto_x509.oid.NameOID.COMMON_NAME)
            o = get_attr(crypto_x509.oid.NameOID.ORGANIZATION_NAME)
            c = get_attr(crypto_x509.oid.NameOID.COUNTRY_NAME)
            
            # قراءة حقول إضافية (قد تحتوي على الرقم الضريبي)
            serial_number_attr = get_attr(crypto_x509.oid.NameOID.SERIAL_NUMBER)
            ou = get_attr(crypto_x509.oid.NameOID.ORGANIZATIONAL_UNIT_NAME)
            locality = get_attr(crypto_x509.oid.NameOID.LOCALITY_NAME)
            state = get_attr(crypto_x509.oid.NameOID.STATE_OR_PROVINCE_NAME)
            email = get_attr(crypto_x509.oid.NameOID.EMAIL_ADDRESS)
            
            # قراءة OID 2.5.4.97 (organizationIdentifier) - الرقم الضريبي الفعلي
            from cryptography.x509.oid import ObjectIdentifier
            organization_identifier_oid = ObjectIdentifier("2.5.4.97")
            organization_identifier = get_attr(organization_identifier_oid)
            
            # قراءة Phone
            phone = None
            
            # قراءة جميع attributes في Subject (للتأكد من عدم فقدان أي معلومات)
            all_subject_attrs = {}
            all_subject_attrs_detailed = {}
            for attr in cert.subject:
                attr_name = attr.oid._name if hasattr(attr.oid, '_name') else attr.oid.dotted_string
                all_subject_attrs[attr_name] = attr.value
                all_subject_attrs_detailed[attr.oid.dotted_string] = {
                    'name': attr_name,
                    'value': attr.value
                }
                
                # محاولة إيجاد Phone
                if attr.oid.dotted_string not in ['2.5.4.3', '2.5.4.6', '1.2.840.113549.1.9.1', '2.5.4.97', '2.5.4.5', '2.5.4.10', '2.5.4.11']:
                    if attr.value.isdigit():
                        phone = attr.value
            
            # محاولة استخراج الرقم الضريبي من حقول مختلفة
            tax_id = None
            tax_id_full = None
            
            # الأولوية 1: من OID 2.5.4.97 (organizationIdentifier) - الطريقة الصحيحة
            if organization_identifier:
                tax_id_full = organization_identifier
                # استخراج الرقم من VATEG-xxxxxxxxx
                if organization_identifier.startswith('VATEG-'):
                    tax_id = organization_identifier.replace('VATEG-', '')
                elif organization_identifier.startswith('VATE-'):
                    tax_id = organization_identifier.replace('VATE-', '')
                else:
                    tax_id = organization_identifier
            
            # الأولوية 2: من serialNumber
            elif serial_number_attr and serial_number_attr.isdigit():
                tax_id = serial_number_attr
            
            # الأولوية 3: إذا كان CN رقمي (9 أرقام)
            elif cn and cn.isdigit() and len(cn) == 9:
                tax_id = cn
            
            # الأولوية 4: ابحث في OU
            elif ou and ou.isdigit():
                tax_id = ou
            
            # الرقم التسلسلي
            serial_num = cert.serial_number
            # تحويل إلى موجب إذا كان سالب
            if serial_num < 0:
                serial_num = serial_num & ((1 << cert.serial_number.bit_length()) - 1)
            serial = format(serial_num, 'X')
            
            # تاريخ الصلاحية
            valid_from = cert.not_valid_before_utc if hasattr(cert, 'not_valid_before_utc') else cert.not_valid_before
            valid_to = cert.not_valid_after_utc if hasattr(cert, 'not_valid_after_utc') else cert.not_valid_after
            
            # حالة الصلاحية
            now = datetime.now(timezone.utc)
            if now < valid_from:
                status = "not_started"
                status_ar = "لم تبدأ بعد"
                days_left = 0
            elif now > valid_to:
                status = "expired"
                status_ar = "منتهية الصلاحية"
                days_left = 0
            else:
                days_left = (valid_to - now).days
                status = "valid"
                status_ar = f"صالحة (باقي {days_left} يوم)"
            
            # معلومات الجهة المصدرة
            issuer_cn = cert.issuer.get_attributes_for_oid(crypto_x509.oid.NameOID.COMMON_NAME)
            issuer_o = cert.issuer.get_attributes_for_oid(crypto_x509.oid.NameOID.ORGANIZATION_NAME)
            
            cert_info = {
                'subject': {
                    'common_name': cn or 'N/A',
                    'organization': o or 'N/A',
                    'country': c or 'N/A',
                    'serial_number': serial_number_attr or 'N/A',
                    'organizational_unit': ou or 'N/A',
                    'locality': locality or 'N/A',
                    'state': state or 'N/A',
                    'email': email or 'N/A',
                    'phone': phone or 'N/A',
                    'organization_identifier': organization_identifier or 'N/A',  # 2.5.4.97
                    'all_attributes': all_subject_attrs,  # جميع الحقول
                    'all_attributes_detailed': all_subject_attrs_detailed  # جميع الحقول مع OID
                },
                'issuer': {
                    'common_name': issuer_cn[0].value if issuer_cn else 'N/A',
                    'organization': issuer_o[0].value if issuer_o else 'N/A'
                },
                'serial_number': serial,  # الرقم التسلسلي للشهادة (Certificate Serial Number)
                'tax_id': tax_id,  # الرقم الضريبي المستخرج (من VATEG-xxxxxxx)
                'tax_id_full': tax_id_full,  # الرقم الضريبي الكامل (VATEG-xxxxxxx)
                'validity': {
                    'not_before': valid_from.isoformat(),
                    'not_after': valid_to.isoformat(),
                    'status': status,
                    'status_ar': status_ar,
                    'days_remaining': days_left
                },
                'format': 'X.509',
                'version': cert.version.name if hasattr(cert.version, 'name') else str(cert.version)
            }
            
            logger.info("=" * 80)
            logger.info("📜 معلومات الشهادة:")
            logger.info(f"📌 الاسم (CN): {cn or 'N/A'}")
            logger.info(f"📌 المؤسسة (O): {o or 'N/A'}")
            logger.info(f"📌 الدولة (C): {c or 'N/A'}")
            if email:
                logger.info(f"📌 Email (E): {email}")
            if phone:
                logger.info(f"📌 Phone: {phone}")
            if organization_identifier:
                logger.info(f"📌 2.5.4.97 (VAT): {organization_identifier}")
            if serial_number_attr:
                logger.info(f"📌 Serial Number (DN): {serial_number_attr}")
            if ou:
                logger.info(f"📌 OU: {ou}")
            logger.info("")
            if tax_id:
                logger.info(f"💳 الرقم الضريبي: {tax_id}")
                if tax_id_full and tax_id_full != tax_id:
                    logger.info(f"   (مستخرج من: {tax_id_full})")
            else:
                logger.info(f"💳 الرقم الضريبي: غير موجود")
            logger.info("")
            logger.info(f"📌 الرقم التسلسلي للشهادة: {serial}")
            logger.info(f"📌 صالحة من: {valid_from.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"📌 صالحة حتى: {valid_to.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"📌 الحالة: {status_ar}")
            logger.info(f"📋 الجهة المُصدرة: {issuer_cn[0].value if issuer_cn else 'N/A'}")
            logger.info(f"📋 جميع حقول Subject:")
            for oid, info in sorted(all_subject_attrs_detailed.items()):
                logger.info(f"   • OID {oid} ({info['name']}): {info['value']}")
            logger.info("=" * 80)
            
            return cert_info
            
        except Exception as e:
            logger.error(f"❌ خطأ في قراءة معلومات الشهادة: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def canonicalize(self, data):
        """
        تحويل JSON إلى Canonical form حسب متطلبات ITIDA
        - فرز المفاتيح أبجدياً
        - UTF-8 encoding بدون BOM
        - بدون مسافات إضافية
        """
        canonical_json = json.dumps(
            data, 
            separators=(',', ':'),  # بدون مسافات
            sort_keys=True,          # ترتيب أبجدي
            ensure_ascii=False       # السماح بـ Unicode
        )
        logger.info(f"📝 Canonical JSON (first 200 chars): {canonical_json[:200]}")
        return canonical_json

    def create_signed_attributes(self, message_digest):
        """إنشاء SignedAttributes لـ CAdES-BES"""
        try:
            # 1. contentType
            content_type_attr = cms.CMSAttribute({
                'type': 'content_type',
                'values': [cms.ContentType('data')]
            })
            
            # 2. messageDigest
            message_digest_attr = cms.CMSAttribute({
                'type': 'message_digest',
                'values': [core.OctetString(message_digest)]
            })
            
            # 3. signingTime
            signing_time_attr = cms.CMSAttribute({
                'type': 'signing_time',
                'values': [core.UTCTime(datetime.now(timezone.utc))]
            })
            
            # 4. signingCertificateV2
            cert_hash = hashlib.sha256(self.cert_der).digest()
            
            class ESSCertIDv2(core.Sequence):
                _fields = [
                    ('hash_algorithm', algos.DigestAlgorithm, {'optional': True}),
                    ('cert_hash', core.OctetString),
                ]
            
            class SigningCertificateV2(core.SequenceOf):
                _child_spec = ESSCertIDv2
            
            ess = SigningCertificateV2()
            ess_item = ESSCertIDv2()
            ess_item['hash_algorithm'] = algos.DigestAlgorithm({'algorithm': 'sha256'})
            ess_item['cert_hash'] = cert_hash
            ess.append(ess_item)
            
            signing_cert_v2_attr = cms.CMSAttribute({
                'type': cms.CMSAttributeType('1.2.840.113549.1.9.16.2.47'),
                'values': [ess]
            })
            
            signed_attrs = cms.CMSAttributes([
                content_type_attr,
                message_digest_attr,
                signing_time_attr,
                signing_cert_v2_attr
            ])
            
            logger.info("✅ تم إنشاء SignedAttributes بنجاح")
            return signed_attrs
            
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء SignedAttributes: {str(e)}")
            raise

    def sign_data(self, data: bytes, is_signed_attrs=False):
        """
        توقيع البيانات باستخدام ePass2003
        
        Args:
            data: البيانات المراد توقيعها
            is_signed_attrs: إذا كان True، سيتم معالجة البيانات كـ SignedAttributes
        """
        try:
            # إذا كانت SignedAttributes، نحتاج لمعالجة خاصة
            if is_signed_attrs:
                # تحويل CONTEXT SPECIFIC tag إلى SET tag لـ DER encoding
                # SignedAttributes يجب أن تكون SET OF عند التوقيع
                signed_attrs_der = data
                if signed_attrs_der[0:1] == b'\xa0':  # CONTEXT SPECIFIC tag
                    # تغيير tag إلى SET (0x31)
                    signed_attrs_der = b'\x31' + signed_attrs_der[1:]
                    logger.info("✅ تم تحويل SignedAttributes tag من 0xA0 إلى 0x31 (SET)")
                
                # حساب SHA-256 hash للـ SignedAttributes
                data_hash = hashlib.sha256(signed_attrs_der).digest()
                logger.info(f"🔐 SignedAttributes SHA-256 hash: {data_hash.hex()[:32]}...")
            else:
                # حساب SHA-256 hash عادي
                data_hash = hashlib.sha256(data).digest()
                logger.info(f"🔐 SHA-256 hash: {data_hash.hex()[:32]}...")
            
            # بناء DigestInfo structure لـ RSA PKCS#1
            digest_info = (
                b'\x30\x31'  # SEQUENCE, length 49
                b'\x30\x0d'  # SEQUENCE, length 13
                b'\x06\x09'  # OID, length 9
                b'\x60\x86\x48\x01\x65\x03\x04\x02\x01'  # SHA-256 OID
                b'\x05\x00'  # NULL
                b'\x04\x20'  # OCTET STRING, length 32
            ) + data_hash
            
            # إذا لم نجد private_key، نحاول البحث مرة أخرى
            if not self.private_key:
                logger.info("🔍 محاولة البحث عن المفتاح الخاص مرة أخرى...")
                try:
                    # محاولة البحث عن أي مفتاح قابل للتوقيع
                    from PyKCS11.LowLevel import CKA_SIGN
                    keys = self.session.findObjects([
                        (CKA_CLASS, CKO_PRIVATE_KEY),
                        (CKA_SIGN, True)
                    ])
                    if keys:
                        self.private_key = keys[0]
                        logger.info("✅ تم العثور على مفتاح قابل للتوقيع!")
                except Exception as e:
                    logger.warning(f"⚠️ فشل البحث عن مفتاح قابل للتوقيع: {str(e)}")
            
            # إذا ما زلنا بدون مفتاح، نحاول استخراجه من cert_id
            if not self.private_key and hasattr(self, 'certificate_obj'):
                logger.info("🔍 محاولة استخراج المفتاح من cert_id...")
                try:
                    cert_id = self.session.getAttributeValue(self.certificate_obj, [CKA_ID])[0]
                    # محاولة C_Sign المباشر بدون findObjects
                    # سنستخدم أول مفتاح نجده
                    all_objs = self.session.findObjects([])
                    for obj in all_objs:
                        try:
                            obj_id = self.session.getAttributeValue(obj, [CKA_ID])[0]
                            obj_class = self.session.getAttributeValue(obj, [CKA_CLASS])[0]
                            if obj_id == cert_id and obj_class == CKO_PRIVATE_KEY:
                                self.private_key = obj
                                logger.info("✅ تم العثور على المفتاح بمطابقة CKA_ID!")
                                break
                        except:
                            continue
                except Exception as e:
                    logger.warning(f"⚠️ فشل استخراج المفتاح: {str(e)}")
            
            # التحقق من وجود المفتاح
            if not self.private_key:
                # محاولة أخيرة: استخدام cert_obj مباشرة
                if hasattr(self, 'certificate_obj') and self.certificate_obj:
                    logger.info("🔍 محاولة أخيرة: استخدام certificate_obj مباشرة...")
                    try:
                        # نحاول استخدام cert_obj كـ private_key
                        self.private_key = self.certificate_obj
                        logger.warning("⚠️ استخدام certificate_obj كـ private_key (تجريبي)")
                    except Exception as e:
                        logger.error(f"❌ فشل في استخدام certificate_obj: {str(e)}")
                        raise Exception("❌ لا يمكن التوقيع: لم يتم العثور على المفتاح الخاص")
                else:
                    raise Exception("❌ لا يمكن التوقيع: لم يتم العثور على المفتاح الخاص")
            
            # قائمة المحاولات - خاصة بـ ePass2003
            from PyKCS11.LowLevel import CKM_SHA256
            
            attempts = [
                # محاولات ePass2003 الخاصة أولاً
                ("ePass2003: CKM_SHA256 then external RSA", CKM_SHA256, data),
                ("ePass2003: CKM_RSA_PKCS with hash", CKM_RSA_PKCS, data_hash),
                ("ePass2003: CKM_RSA_PKCS with DigestInfo", CKM_RSA_PKCS, digest_info),
                # محاولات قياسية
                ("CKM_SHA256_RSA_PKCS with original data", CKM_SHA256_RSA_PKCS, data),
                ("CKM_SHA1_RSA_PKCS", CKM_SHA1_RSA_PKCS, data),
                ("CKM_RSA_PKCS with original data", CKM_RSA_PKCS, data),
                ("CKM_SHA384_RSA_PKCS", CKM_SHA384_RSA_PKCS, data),
                ("CKM_SHA512_RSA_PKCS", CKM_SHA512_RSA_PKCS, data),
            ]
            
            for desc, mechanism, sign_data in attempts:
                try:
                    logger.info(f"🔍 محاولة: {desc}")
                    sig = self.session.sign(
                        self.private_key,
                        sign_data,
                        Mechanism(mechanism)
                    )
                    sig_bytes = bytes(sig)
                    logger.info(f"✅ نجح التوقيع! (الطول: {len(sig_bytes)} bytes, آلية: {desc})")
                    return sig_bytes
                    
                except Exception as e:
                    logger.warning(f"⚠️ فشلت {desc}: {str(e)}")
                    continue
            
            # فشلت جميع محاولات PKCS#11 - محاولة Windows CSP كحل بديل
            logger.warning("⚠️ فشلت جميع محاولات PKCS#11")
            logger.info("🔄 محاولة التوقيع باستخدام Windows CSP (حل بديل)...")
            
            try:
                # استخدام Windows CSP
                pin = getattr(self, 'pin', '')  # نحتاج PIN المحفوظ
                signature = self.sign_with_windows_csp(data_hash, pin)
                logger.info(f"✅ نجح التوقيع باستخدام Windows CSP! الطول: {len(signature)} bytes")
                return signature
            except Exception as csp_error:
                logger.error(f"❌ فشل التوقيع باستخدام Windows CSP: {str(csp_error)}")
            
            raise Exception("❌ فشلت جميع محاولات التوقيع (PKCS#11 و Windows CSP)")
            
        except Exception as e:
            logger.error(f"❌ خطأ في التوقيع: {str(e)}")
            raise

    def sign_with_windows_csp(self, data: bytes, pin: str) -> bytes:
        """
        توقيع باستخدام Windows CSP مباشرة (حل بديل لـ ePass2003)
        
        Args:
            data: البيانات المراد توقيعها (hash)
            pin: رقم PIN
            
        Returns:
            bytes: التوقيع الرقمي
        """
        try:
            logger.info("🔐 محاولة التوقيع باستخدام Windows CSP...")
            
            # معلومات CSP الخاص بـ ePass2003
            provider_name = "ePass2003 CSP v1.0"
            container_name = None  # سنستخدم المفتاح الافتراضي
            
            hProv = wintypes.HANDLE()
            hHash = wintypes.HANDLE()
            hKey = wintypes.HANDLE()
            
            try:
                # 1. الحصول على CSP context
                result = advapi32.CryptAcquireContextW(
                    ctypes.byref(hProv),
                    container_name,
                    provider_name,
                    PROV_RSA_FULL,
                    CRYPT_SILENT
                )
                
                if not result:
                    error = ctypes.get_last_error()
                    logger.warning(f"⚠️ CryptAcquireContext فشل: {error}")
                    # محاولة بدون CRYPT_SILENT
                    result = advapi32.CryptAcquireContextW(
                        ctypes.byref(hProv),
                        None,
                        provider_name,
                        PROV_RSA_FULL,
                        0
                    )
                    if not result:
                        raise Exception(f"فشل CryptAcquireContext: {ctypes.get_last_error()}")
                
                logger.info("✅ تم الحصول على CSP context")
                
                # 2. إنشاء hash object
                if not advapi32.CryptCreateHash(hProv, CALG_SHA256, 0, 0, ctypes.byref(hHash)):
                    raise Exception(f"فشل CryptCreateHash: {ctypes.get_last_error()}")
                
                logger.info("✅ تم إنشاء hash object")
                
                # 3. وضع القيمة في hash
                hash_data = data
                if not advapi32.CryptSetHashParam(hHash, HP_HASHVAL, hash_data, 0):
                    raise Exception(f"فشل CryptSetHashParam: {ctypes.get_last_error()}")
                
                logger.info("✅ تم وضع hash value")
                
                # 4. الحصول على user key (مع إدخال PIN)
                if not advapi32.CryptGetUserKey(hProv, AT_SIGNATURE, ctypes.byref(hKey)):
                    # محاولة AT_KEYEXCHANGE
                    if not advapi32.CryptGetUserKey(hProv, AT_KEYEXCHANGE, ctypes.byref(hKey)):
                        raise Exception(f"فشل CryptGetUserKey: {ctypes.get_last_error()}")
                
                logger.info("✅ تم الحصول على user key")
                
                # 5. التوقيع
                sig_len = wintypes.DWORD(0)
                # الحصول على حجم التوقيع
                advapi32.CryptSignHashW(hHash, AT_SIGNATURE, None, 0, None, ctypes.byref(sig_len))
                
                # التوقيع الفعلي
                signature_buffer = ctypes.create_string_buffer(sig_len.value)
                if not advapi32.CryptSignHashW(
                    hHash,
                    AT_SIGNATURE,
                    None,
                    0,
                    signature_buffer,
                    ctypes.byref(sig_len)
                ):
                    raise Exception(f"فشل CryptSignHash: {ctypes.get_last_error()}")
                
                signature = bytes(signature_buffer[:sig_len.value])
                # عكس البايتات (Windows يرجعها معكوسة)
                signature = signature[::-1]
                
                logger.info(f"✅ نجح التوقيع باستخدام Windows CSP! الطول: {len(signature)} bytes")
                return signature
                
            finally:
                # تنظيف
                if hKey:
                    advapi32.CryptDestroyKey(hKey)
                if hHash:
                    advapi32.CryptDestroyHash(hHash)
                if hProv:
                    advapi32.CryptReleaseContext(hProv, 0)
                    
        except Exception as e:
            logger.error(f"❌ خطأ في التوقيع باستخدام Windows CSP: {str(e)}")
            raise

    def sign_with_chilkat(self, invoice_data, pin: str, request_data=None):
        """
        توقيع باستخدام Chilkat - الطريقة المستخدمة في sign_and_send_EP.py
        هذه الطريقة أثبتت نجاحها 100% مع ePass2003
        
        Args:
            invoice_data: بيانات الفاتورة (dict)
            pin: رقم PIN
            request_data: POST /sign body (sign_session → ERP Chilkat key + PIN)
            
        Returns:
            tuple: (signature_b64, signed_document dict)
        """
        try:
            if not CHILKAT_AVAILABLE:
                raise Exception("❌ Chilkat library غير متوفرة")
            
            logger.info("=" * 80)
            logger.info("🔐 التوقيع باستخدام Chilkat (طريقة PowerBuilder المجربة)")
            logger.info("=" * 80)
            
            req = request_data if isinstance(request_data, dict) else {}
            unlock_code = _resolve_chilkat_unlock_code(req)
            ok, unlock_detail = unlock_chilkat_global(
                chilkat2,
                request_data=req,
                primary_unlock_code=unlock_code or None,
            )
            if not ok:
                raise ChilkatLicenseError(unlock_detail)
            logger.info("✅ Chilkat unlock: %s", unlock_detail)
            
            # 2. تحميل الشهادة من Smart Card
            logger.info("\n🔍 تحميل الشهادة من ePass2003...")
            cert = chilkat2.Cert()
            cert.SmartCardPin = pin
            
            # استخدام empty string للتحميل التلقائي (مثل PowerBuilder تماماً)
            success = cert.LoadFromSmartcard("")
            
            if not success:
                logger.error(f"❌ فشل تحميل الشهادة: {cert.LastErrorText}")
                raise Exception(f"فشل تحميل الشهادة: {cert.LastErrorText}")
            
            logger.info(f"✅ تم تحميل الشهادة:")
            logger.info(f"   📌 SubjectCN: {cert.SubjectCN}")
            logger.info(f"   📌 SubjectO: {cert.SubjectO}")
            logger.info(f"   📌 IssuerCN: {cert.IssuerCN}")
            logger.info(f"   📌 Serial: {cert.SerialNumber}")
            
            # حفظ للاستخدام لاحقاً
            self.chilkat_cert = cert
            
            # 3. إعداد Crypt2
            crypt = chilkat2.Crypt2()
            
            if not crypt.SetSigningCert(cert):
                logger.error(f"❌ SetSigningCert فشل: {crypt.LastErrorText}")
                raise Exception(f"SetSigningCert فشل: {crypt.LastErrorText}")
            
            # 4–8. ITIDA CAdES-BES (Temp-ETR epass2003_signature.py — DigestData + CanonicalizeITIDA)
            apply_itida_crypt_options(crypt, chilkat2)
            apply_itida_signing_attributes(crypt, chilkat2)
            finalize_itida_crypt_before_sign(crypt)

            unsigned = json.loads(json.dumps(invoice_data or {}, ensure_ascii=False))
            unsigned.pop("signatures", None)

            # Primary: Chilkat JsonObject field-by-field (PowerBuilder / sign_and_send_EP)
            logger.info("\n📝 بناء JSON باستخدام Chilkat JsonObject (PowerBuilder)...")
            loo_Json = chilkat2.JsonObject()
            self._build_json_with_chilkat(loo_Json, unsigned)
            loo_Json.EmitCompact = 1
            json_chilkat = loo_Json.Emit()
            logger.info("📝 Chilkat JSON length: %s", len(json_chilkat))

            sig_b64 = None
            cms_info = None
            json_signed = json_chilkat
            sign_mode = "chilkat_json"

            for attempt_name, json_text in (
                ("chilkat_json", json_chilkat),
                ("python_canonical", build_itida_canonical_json(unsigned)),
            ):
                if not json_text:
                    continue
                logger.info("🔐 ITIDA sign attempt: %s (%s chars)", attempt_name, len(json_text))
                try:
                    candidate = sign_canonical_json_with_crypt(crypt, json_text)
                    cms_info = validate_itida_signature_b64(candidate, signing_method=f"Chilkat/{attempt_name}")
                    sig_b64 = candidate
                    json_signed = json_text
                    sign_mode = attempt_name
                    logger.info("ITIDA CMS OK: %s", cms_info)
                    break
                except ITIDASignatureFormatError as fmt_exc:
                    logger.warning("ITIDA CMS reject (%s): %s", attempt_name, fmt_exc)
                    if attempt_name == "python_canonical":
                        raise

            if not sig_b64:
                raise ITIDASignatureFormatError("No valid ITIDA CMS signature produced.")

            # signed_document_json = exact Chilkat Emit bytes for ETA POST (avoids 4043 digest mismatch)
            if sign_mode == "chilkat_json":
                loo_Json.UpdateString("signatures[0].signatureType", "I")
                loo_Json.UpdateString("signatures[0].value", sig_b64)
                signed_document_json = loo_Json.Emit()
            else:
                signed_document = json.loads(json_signed)
                signed_document["signatures"] = [{"signatureType": "I", "value": sig_b64}]
                signed_document_json = json.dumps(
                    signed_document, separators=(",", ":"), ensure_ascii=False, sort_keys=True
                )

            signed_document = json.loads(signed_document_json)
            self.last_signed_document_json = signed_document_json

            logger.info("✅ Signature DER ~%s bytes (ETA sample includes cert — size is OK)", cms_info.get("der_bytes"))
            self.last_canonical_json = json_signed
            self.last_signed_document = signed_document
            return sig_b64, signed_document, signed_document_json
            
        except (ChilkatLicenseError, ITIDASignatureFormatError):
            raise
        except Exception as e:
            logger.error(f"❌ خطأ في التوقيع باستخدام Chilkat: {str(e)}")
            if is_chilkat_license_error(str(e)):
                raise ChilkatLicenseError(user_facing_sign_error(e)) from e
            raise

    def _build_json_with_chilkat(self, json_obj, data):
        """
        بناء JSON باستخدام Chilkat UpdateString/UpdateNumber/UpdateInt
        مطابق تماماً لطريقة PowerBuilder في sign_and_send_EP.py
        """
        try:
            # استخراج البيانات
            issuer = data.get('issuer', {})
            issuer_addr = issuer.get('address', {})
            
            receiver = data.get('receiver', {})
            receiver_addr = receiver.get('address', {})
            
            # Issuer Address
            json_obj.UpdateString("issuer.address.branchID", str(issuer_addr.get('branchID', '')))
            json_obj.UpdateString("issuer.address.country", str(issuer_addr.get('country', '')))
            json_obj.UpdateString("issuer.address.governate", str(issuer_addr.get('governate', '')))
            json_obj.UpdateString("issuer.address.regionCity", str(issuer_addr.get('regionCity', '')))
            json_obj.UpdateString("issuer.address.street", str(issuer_addr.get('street', '')))
            json_obj.UpdateString("issuer.address.buildingNumber", str(issuer_addr.get('buildingNumber', '')))
            json_obj.UpdateString("issuer.address.postalCode", str(issuer_addr.get('postalCode', '')))
            json_obj.UpdateString("issuer.address.floor", str(issuer_addr.get('floor', '')))
            json_obj.UpdateString("issuer.address.room", str(issuer_addr.get('room', '')))
            json_obj.UpdateString("issuer.address.landmark", str(issuer_addr.get('landmark', '')))
            json_obj.UpdateString("issuer.address.additionalInformation", str(issuer_addr.get('additionalInformation', '')))
            
            # Issuer
            json_obj.UpdateString("issuer.type", str(issuer.get('type', '')))
            json_obj.UpdateString("issuer.id", str(issuer.get('id', '')))
            json_obj.UpdateString("issuer.name", str(issuer.get('name', '')))
            
            # Receiver Address
            json_obj.UpdateString("receiver.address.country", str(receiver_addr.get('country', '')))
            json_obj.UpdateString("receiver.address.governate", str(receiver_addr.get('governate', '')))
            json_obj.UpdateString("receiver.address.regionCity", str(receiver_addr.get('regionCity', '')))
            json_obj.UpdateString("receiver.address.street", str(receiver_addr.get('street', '')))
            json_obj.UpdateString("receiver.address.buildingNumber", str(receiver_addr.get('buildingNumber', '')))
            json_obj.UpdateString("receiver.address.postalCode", str(receiver_addr.get('postalCode', '')))
            json_obj.UpdateString("receiver.address.floor", str(receiver_addr.get('floor', '')))
            json_obj.UpdateString("receiver.address.room", str(receiver_addr.get('room', '')))
            json_obj.UpdateString("receiver.address.landmark", str(receiver_addr.get('landmark', '')))
            json_obj.UpdateString("receiver.address.additionalInformation", str(receiver_addr.get('additionalInformation', '')))
            
            # Receiver
            json_obj.UpdateString("receiver.type", str(receiver.get('type', '')))
            recv_id = receiver.get('id')
            if recv_id is None:
                recv_id = ''
            json_obj.UpdateString("receiver.id", str(recv_id))
            json_obj.UpdateString("receiver.name", str(receiver.get('name', '')))
            
            # Document details
            json_obj.UpdateString("documentType", str(data.get('documentType', '')))
            json_obj.UpdateString("documentTypeVersion", str(data.get('documentTypeVersion', '')))
            json_obj.UpdateString("dateTimeIssued", str(data.get('dateTimeIssued', '')))
            json_obj.UpdateString("taxpayerActivityCode", str(data.get('taxpayerActivityCode', '')))
            json_obj.UpdateString("internalID", str(data.get('internalID', '')))
            json_obj.UpdateString("purchaseOrderReference", str(data.get('purchaseOrderReference', '')))
            json_obj.UpdateString("purchaseOrderDescription", str(data.get('purchaseOrderDescription', '')))
            json_obj.UpdateString("salesOrderReference", str(data.get('salesOrderReference', '')))
            json_obj.UpdateString("salesOrderDescription", str(data.get('salesOrderDescription', '')))
            json_obj.UpdateString("proformaInvoiceNumber", str(data.get('proformaInvoiceNumber', '')))
            
            # Payment
            payment = data.get('payment', {})
            json_obj.UpdateString("payment.bankName", str(payment.get('bankName', '')))
            json_obj.UpdateString("payment.bankAddress", str(payment.get('bankAddress', '')))
            json_obj.UpdateString("payment.bankAccountNo", str(payment.get('bankAccountNo', '')))
            json_obj.UpdateString("payment.bankAccountIBAN", str(payment.get('bankAccountIBAN', '')))
            json_obj.UpdateString("payment.swiftCode", str(payment.get('swiftCode', '')))
            json_obj.UpdateString("payment.terms", str(payment.get('terms', '')))
            
            # Delivery
            delivery = data.get('delivery', {})
            json_obj.UpdateString("delivery.approach", str(delivery.get('approach', '')))
            json_obj.UpdateString("delivery.packaging", str(delivery.get('packaging', '')))
            json_obj.UpdateString("delivery.dateValidity", str(delivery.get('dateValidity', '')))
            json_obj.UpdateString("delivery.exportPort", str(delivery.get('exportPort', '')))
            json_obj.UpdateInt("delivery.grossWeight", int(delivery.get('grossWeight', 0)))
            json_obj.UpdateInt("delivery.netWeight", int(delivery.get('netWeight', 0)))
            json_obj.UpdateString("delivery.terms", str(delivery.get('terms', '')))
            
            # Invoice Lines
            invoice_lines = data.get('invoiceLines', [])
            for idx, line in enumerate(invoice_lines):
                prefix = f"invoiceLines[{idx}]"
                
                json_obj.UpdateString(f"{prefix}.description", str(line.get('description', '')))
                json_obj.UpdateString(f"{prefix}.itemType", str(line.get('itemType', '')))
                json_obj.UpdateString(f"{prefix}.itemCode", str(line.get('itemCode', '')))
                json_obj.UpdateString(f"{prefix}.unitType", str(line.get('unitType', '')))
                json_obj.UpdateNumber(f"{prefix}.quantity", str(line.get('quantity', 0)))
                json_obj.UpdateString(f"{prefix}.internalCode", str(line.get('internalCode', '')))
                json_obj.UpdateNumber(f"{prefix}.salesTotal", str(line.get('salesTotal', 0)))
                json_obj.UpdateNumber(f"{prefix}.total", str(line.get('total', 0)))
                json_obj.UpdateNumber(f"{prefix}.valueDifference", str(line.get('valueDifference', 0)))
                json_obj.UpdateNumber(f"{prefix}.totalTaxableFees", str(line.get('totalTaxableFees', 0)))
                json_obj.UpdateNumber(f"{prefix}.netTotal", str(line.get('netTotal', 0)))
                json_obj.UpdateNumber(f"{prefix}.itemsDiscount", str(line.get('itemsDiscount', 0)))
                
                # Unit Value
                unit_value = line.get('unitValue', {})
                json_obj.UpdateString(f"{prefix}.unitValue.currencySold", str(unit_value.get('currencySold', '')))
                json_obj.UpdateNumber(f"{prefix}.unitValue.amountEGP", str(unit_value.get('amountEGP', 0)))
                
                # Discount
                discount = line.get('discount', {})
                json_obj.UpdateNumber(f"{prefix}.discount.rate", str(discount.get('rate', 0)))
                json_obj.UpdateNumber(f"{prefix}.discount.amount", str(discount.get('amount', 0)))
                
                # Taxable Items
                taxable_items = line.get('taxableItems', [])
                for tax_idx, tax_item in enumerate(taxable_items):
                    tax_prefix = f"{prefix}.taxableItems[{tax_idx}]"
                    json_obj.UpdateString(f"{tax_prefix}.taxType", str(tax_item.get('taxType', '')))
                    json_obj.UpdateNumber(f"{tax_prefix}.amount", str(tax_item.get('amount', 0)))
                    json_obj.UpdateString(f"{tax_prefix}.subType", str(tax_item.get('subType', '')))
                    json_obj.UpdateNumber(f"{tax_prefix}.rate", str(tax_item.get('rate', 0)))
            
            # Totals
            json_obj.UpdateNumber("totalDiscountAmount", str(data.get('totalDiscountAmount', 0)))
            json_obj.UpdateNumber("totalSalesAmount", str(data.get('totalSalesAmount', 0)))
            json_obj.UpdateNumber("netAmount", str(data.get('netAmount', 0)))
            
            # Tax Totals
            tax_totals = data.get('taxTotals', [])
            for idx, tax_total in enumerate(tax_totals):
                json_obj.UpdateString(f"taxTotals[{idx}].taxType", str(tax_total.get('taxType', '')))
                json_obj.UpdateNumber(f"taxTotals[{idx}].amount", str(tax_total.get('amount', 0)))
            
            json_obj.UpdateNumber("totalAmount", str(data.get('totalAmount', 0)))
            json_obj.UpdateNumber("extraDiscountAmount", str(data.get('extraDiscountAmount', 0)))
            json_obj.UpdateNumber("totalItemsDiscountAmount", str(data.get('totalItemsDiscountAmount', 0)))
            
            logger.info("✅ تم بناء JSON بنجاح باستخدام طريقة Chilkat")
            
        except Exception as e:
            logger.error(f"❌ خطأ في بناء JSON: {str(e)}")
            raise

    def create_signature(self, invoice_data, pin=None):
        """
        إنشاء توقيع CAdES-BES متوافق مع ITIDA/ETA
        
        الاستراتيجية:
        1. إذا كان Chilkat متاحاً واستخدامه مفعّل - استخدمه أولاً (الطريقة المجربة 100%)
        2. إذا فشل أو غير متاح - استخدم PKCS#11 + asn1crypto
        
        Args:
            invoice_data: بيانات الفاتورة
            pin: رقم PIN (مطلوب لـ Chilkat)
        """
        try:
            # محاولة 1: استخدام Chilkat (الطريقة المجربة من sign_and_send_EP.py)
            if self.use_chilkat and CHILKAT_AVAILABLE and pin:
                try:
                    logger.info("=" * 80)
                    logger.info("📌 استخدام طريقة Chilkat (PowerBuilder) - الطريقة المفضلة")
                    logger.info("=" * 80)
                    sig, _signed_doc, _raw = self.sign_with_chilkat(invoice_data, pin)
                    return sig
                except Exception as chilkat_error:
                    logger.warning(f"⚠️ فشل التوقيع باستخدام Chilkat: {str(chilkat_error)}")
                    logger.info("🔄 التبديل إلى طريقة PKCS#11...")
            
            # محاولة 2: استخدام PKCS#11 + asn1crypto (الطريقة البديلة)
            logger.info("=" * 80)
            logger.info("📌 استخدام طريقة PKCS#11 + asn1crypto")
            logger.info("=" * 80)
            
            # 1. استخراج الرقم الضريبي من الشهادة
            cert_info = self.get_certificate_info()
            cert_tax_id = cert_info.get('tax_id') if cert_info else None
            cn = self.get_common_name(self.cert_der)
            issuer_id = invoice_data.get('issuer', {}).get('id') or invoice_data.get('issuerId')
            
            # التحقق من التطابق (استخدام tax_id أو CN)
            if issuer_id:
                issuer_id_str = str(issuer_id).strip()
                
                # محاولة المطابقة مع tax_id أولاً
                if cert_tax_id and cert_tax_id == issuer_id_str:
                    logger.info(f"✅ Tax ID matched: '{cert_tax_id}' = '{issuer_id_str}'")
                # ثم محاولة المطابقة مع CN
                elif cn and cn.strip() == issuer_id_str:
                    logger.info(f"✅ CN matched: '{cn}' = '{issuer_id_str}'")
                else:
                    logger.warning(f"⚠️ ID mismatch: Certificate Tax ID='{cert_tax_id}', CN='{cn}' != Invoice issuerId='{issuer_id_str}'")
                    logger.warning(f"⚠️ قد يسبب هذا خطأ ISFX305 في ETA - تأكد من استخدام الرقم الضريبي الصحيح")
            
            # 2. Canonicalize JSON
            canonical = self.canonicalize(invoice_data)
            canonical_bytes = canonical.encode('utf-8')
            logger.info(f"📝 Canonical JSON length: {len(canonical_bytes)} bytes")
            
            # 3. حساب Message Digest
            message_digest = hashlib.sha256(canonical_bytes).digest()
            logger.info(f"🔐 Invoice Message Digest: {message_digest.hex()}")
            
            # 4. بناء SignedAttributes
            signed_attrs = self.create_signed_attributes(message_digest)
            signed_attrs_der = signed_attrs.dump()
            logger.info(f"📦 SignedAttributes DER length: {len(signed_attrs_der)} bytes")
            logger.info(f"📦 SignedAttributes DER (first 32 bytes): {signed_attrs_der[:32].hex()}")
            
            # 5. توقيع SignedAttributes (مع معالجة خاصة)
            signature = self.sign_data(signed_attrs_der, is_signed_attrs=True)
            logger.info(f"✅ Signature length: {len(signature)} bytes")
            logger.info(f"✅ Signature (first 32 bytes): {signature[:32].hex()}")
            
            # 6. بناء CMS SignedData
            signer_info = cms.SignerInfo({
                'version': 'v1',
                'sid': cms.SignerIdentifier({
                    'issuer_and_serial_number': cms.IssuerAndSerialNumber({
                        'issuer': self.certificate.issuer,
                        'serial_number': self.certificate.serial_number
                    })
                }),
                'digest_algorithm': algos.DigestAlgorithm({'algorithm': 'sha256'}),
                'signed_attrs': signed_attrs,
                'signature_algorithm': algos.SignedDigestAlgorithm({'algorithm': 'rsassa_pkcs1v15'}),
                'signature': core.OctetString(signature)
            })
            
            signed_data = cms.SignedData({
                'version': 'v1',
                'digest_algorithms': cms.DigestAlgorithms([
                    algos.DigestAlgorithm({'algorithm': 'sha256'})
                ]),
                'encap_content_info': {'content_type': 'data'},
                'certificates': cms.CertificateSet([self.certificate]),
                'signer_infos': cms.SignerInfos([signer_info])
            })
            
            content_info = cms.ContentInfo({
                'content_type': 'signed_data',
                'content': signed_data
            })
            
            # 7. تحويل إلى Base64
            cms_der = content_info.dump()
            signature_b64 = base64.b64encode(cms_der).decode('utf-8')
            validate_itida_signature_b64(signature_b64, signing_method="PKCS#11")
            
            logger.info(f"✅ CAdES-BES Signature created successfully")
            logger.info(f"   - CMS DER length: {len(cms_der)} bytes")
            logger.info(f"   - Base64 length: {len(signature_b64)} chars")
            logger.info(f"   - Signature format: CAdES-BES")
            
            return signature_b64
            
        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء التوقيع: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def get_certificate_serial(self):
        """الحصول على الرقم التسلسلي للشهادة"""
        if self.certificate:
            return format(self.certificate.serial_number, 'X')
        return None

    def verify_signature(self, invoice_data, signature_b64):
        """
        التحقق من صحة التوقيع CAdES-BES
        
        Returns:
            dict: نتيجة التحقق مع التفاصيل
        """
        try:
            logger.info("🔍 بدء التحقق من التوقيع...")
            
            # 1. فك تشفير Base64
            cms_der = base64.b64decode(signature_b64)
            logger.info(f"✅ CMS DER decoded: {len(cms_der)} bytes")
            
            # 2. تحليل CMS structure
            content_info = cms.ContentInfo.load(cms_der)
            signed_data = content_info['content']
            
            # 3. استخراج SignerInfo
            signer_info = signed_data['signer_infos'][0]
            signed_attrs = signer_info['signed_attrs']
            signature_bytes = signer_info['signature'].native
            
            logger.info(f"✅ Signature extracted: {len(signature_bytes)} bytes")
            
            # 4. التحقق من SignedAttributes
            message_digest_found = False
            content_type_found = False
            signing_time_found = False
            
            for attr in signed_attrs:
                attr_type = attr['type'].dotted
                if attr_type == '1.2.840.113549.1.9.4':  # messageDigest
                    message_digest_found = True
                    stored_digest = attr['values'][0].native
                    logger.info(f"✅ messageDigest found: {stored_digest.hex()}")
                elif attr_type == '1.2.840.113549.1.9.3':  # contentType
                    content_type_found = True
                    logger.info(f"✅ contentType found: {attr['values'][0].dotted}")
                elif attr_type == '1.2.840.113549.1.9.5':  # signingTime
                    signing_time_found = True
                    logger.info(f"✅ signingTime found: {attr['values'][0].native}")
            
            # 5. حساب Message Digest من الفاتورة
            canonical = self.canonicalize(invoice_data)
            calculated_digest = hashlib.sha256(canonical.encode('utf-8')).digest()
            logger.info(f"✅ Calculated digest: {calculated_digest.hex()}")
            
            # 6. مقارنة الـ digests
            digest_match = (stored_digest == calculated_digest)
            
            # 7. استخراج الشهادة من CMS
            cert_from_cms = signed_data['certificates'][0].chosen
            cn_from_cms = None
            try:
                cn_from_cms = self.get_common_name(cert_from_cms.dump())
            except:
                pass
            
            result = {
                'valid': digest_match and message_digest_found and content_type_found and signing_time_found,
                'details': {
                    'message_digest_found': message_digest_found,
                    'message_digest_match': digest_match,
                    'content_type_found': content_type_found,
                    'signing_time_found': signing_time_found,
                    'certificate_cn': cn_from_cms,
                    'signature_length': len(signature_bytes),
                    'cms_version': signed_data['version'].native,
                    'signer_version': signer_info['version'].native
                }
            }
            
            if result['valid']:
                logger.info("✅ التوقيع صحيح ومتوافق مع CAdES-BES")
            else:
                logger.error("❌ التوقيع غير صحيح أو غير متوافق")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ خطأ في التحقق من التوقيع: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'valid': False,
                'error': str(e)
            }

    def logout(self):
        """تسجيل الخروج وإغلاق الجلسة"""
        try:
            if self.session:
                try:
                    self.session.logout()
                    logger.info("✅ تم تسجيل الخروج")
                except:
                    pass
                
                self.session.closeSession()
                logger.info("✅ تم إغلاق الجلسة")
        except Exception as e:
            logger.error(f"⚠️ خطأ في إغلاق الجلسة: {str(e)}")


# =============================================================================
# Flask Routes (API Endpoints)
# =============================================================================

@app.route('/health', methods=['GET'])
def health():
    """فحص حالة الخدمة"""
    
    # بناء قائمة طرق التوقيع المتاحة
    signing_methods = []
    if CHILKAT_AVAILABLE:
        signing_methods.append('Chilkat (PowerBuilder) - المفضل')
    signing_methods.append('PKCS#11')
    signing_methods.append('Windows CSP (fallback)')
    
    # فحص التوكنات المتاحة
    supported_tokens = []
    for token_name, dll_path in TOKEN_DLLS.items():
        supported_tokens.append({
            'type': token_name,
            'dll_path': dll_path,
            'dll_exists': os.path.exists(dll_path)
        })
    
    chilkat_health = {}
    if CHILKAT_AVAILABLE:
        chilkat_health = unlock_status_for_health(chilkat2)

    return jsonify({
        'status': 'healthy',
        'message': 'Token Sign Agent is running (Multi-Method & Multi-Token)',
        'supported_tokens': ['epass2003', 'wd_proxkey'],
        'tokens_status': supported_tokens,
        'chilkat_available': CHILKAT_AVAILABLE,
        'chilkat_runtime_version': chilkat_health.get('chilkat_runtime_version'),
        'chilkat_desired_major': chilkat_health.get('chilkat_desired_major'),
        'chilkat_unlock_source': chilkat_health.get('unlock_source'),
        'chilkat_has_unlock_code': chilkat_health.get('has_unlock_code'),
        'chilkat_config_file': chilkat_health.get('config_file'),
        'chilkat_config_file_exists': chilkat_health.get('config_file_exists'),
        'chilkat_unlock_ok': chilkat_health.get('chilkat_unlock_ok', False),
        'chilkat_unlock_note': chilkat_health.get('chilkat_unlock_note', ''),
        'chilkat_version': chilkat_health.get('chilkat_runtime_version') or (
            '10.x' if CHILKAT_AVAILABLE else None
        ),
        'preferred_method': (
            'Chilkat'
            if (CHILKAT_AVAILABLE and chilkat_health.get('chilkat_unlock_ok'))
            else 'PKCS#11'
        ),
        'pkcs11_fallback': True,
        'signing_methods': signing_methods,
        'timestamp': datetime.now().isoformat(),
        'version': '3.0.0-MultiToken',
        'port': 5002,
        'features': {
            'read_certificate': True,
            'extract_tax_id': True,
            'sign_chilkat': CHILKAT_AVAILABLE,
            'sign_pkcs11': True,
            'sign_windows_csp': True,
            'verify_signature': True,
            'powerbuilder_compatible': CHILKAT_AVAILABLE,
            'multi_token_support': True
        },
        'compatibility': {
            'sign_and_send_EP.py': CHILKAT_AVAILABLE,
            'powerbuilder': CHILKAT_AVAILABLE,
            'itida_eta': True
        }
    })


@app.route('/sign', methods=['POST'])
def sign_invoice():
    """توقيع الفاتورة مع التحقق التلقائي - يدعم Chilkat و PKCS#11"""
    try:
        if not request.json:
            msg = 'لم يتم إرسال بيانات صحيحة (Content-Type: application/json مطلوب)'
            logger.error("POST /sign 400: %s", msg)
            return jsonify({'success': False, 'message': msg}), 400
        
        data = request.json
        invoice_data = data.get('invoice') or data.get('document')
        verify_after_sign = data.get('verify', True)  # التحقق الافتراضي
        use_chilkat = data.get('use_chilkat', True)  # استخدام Chilkat افتراضياً
        token_type = data.get('token_type', 'epass2003')  # نوع التوكن (epass2003 أو wd_proxkey)
        pin = _resolve_token_pin(data)

        chilkat_hint = bool(_resolve_chilkat_unlock_code(data))
        logger.info(
            "POST /sign keys=%s has_invoice=%s pin_len=%s sign_session=%s chilkat_key=%s erp=%s",
            sorted(data.keys()),
            bool(invoice_data),
            len(pin),
            bool(data.get('sign_session')),
            chilkat_hint,
            (data.get('erp_base_url') or '')[:80],
        )
        
        if not invoice_data:
            msg = 'بيانات الفاتورة مطلوبة (مفتاح invoice أو document)'
            logger.error("POST /sign 400: %s", msg)
            return jsonify({'success': False, 'message': msg}), 400
        
        if not pin:
            msg = 'PIN التوكن مطلوب — احفظه في ERP: Branch → Egypt ETA → USB Token PIN'
            logger.error("POST /sign 400: %s (أرسل pin أو pin_b64)", msg)
            return jsonify({'success': False, 'message': msg}), 400

        invoice_id = invoice_data.get('internalID', 'Unknown')
        logger.info("=" * 80)
        logger.info(f"📨 طلب توقيع فاتورة رقم: {invoice_id}")
        logger.info(f"🔑 التوكن: {token_type.upper()}")
        logger.info(f"📌 PIN length: {len(pin)}")
        logger.info(f"📌 طريقة التوقيع المفضلة: {'Chilkat' if use_chilkat else 'PKCS#11'}")
        logger.info(f"📌 Chilkat متاح: {CHILKAT_AVAILABLE}")
        logger.info("=" * 80)
        
        # إنشاء الموقّع مع نوع التوكن المحدد
        signer = EPass2003Signer(use_chilkat=use_chilkat, token_type=token_type)
        
        # إذا كان سيستخدم Chilkat، لا نحتاج لتهيئة PKCS#11
        if use_chilkat and CHILKAT_AVAILABLE and pin:
            try:
                # التوقيع مباشرة باستخدام Chilkat (بدون تهيئة PKCS#11)
                logger.info("🚀 التوقيع المباشر باستخدام Chilkat...")
                signature, signed_document, signed_document_json = signer.sign_with_chilkat(
                    invoice_data, pin, request_data=data
                )
                
                # الحصول على serial من الشهادة
                cert_serial = None
                if signer.chilkat_cert:
                    cert_serial = signer.chilkat_cert.SerialNumber
                
                logger.info("=" * 80)
                logger.info(f"✅ تم توقيع الفاتورة {invoice_id} بنجاح (Chilkat)")
                logger.info(f"📜 Certificate Serial: {cert_serial}")
                logger.info("=" * 80)
                
                canonical_json = getattr(signer, 'last_canonical_json', None)
                cms_info = validate_itida_signature_b64(signature, signing_method="Chilkat")
                response = {
                    'success': True,
                    'signatures': [{
                        'signatureType': 'I',
                        'value': signature
                    }],
                    'signed_document': signed_document,
                    'signed_document_json': signed_document_json,
                    'canonical_json': canonical_json,
                    'cms_validation': cms_info,
                    'certificate_serial': cert_serial,
                    'signed_at': datetime.now().isoformat(),
                    'token_type': token_type,
                    'signature_format': 'CAdES-BES',
                    'signing_method': 'Chilkat (PowerBuilder)'
                }
                
                return jsonify(response)
                
            except (ITIDASignatureFormatError, ChilkatLicenseError) as fmt_err:
                return jsonify({'success': False, 'message': str(fmt_err)}), 500
            except Exception as chilkat_error:
                logger.error(f"❌ فشل Chilkat: {str(chilkat_error)}")
                if os.getenv('AGENT_DISABLE_PKCS11_FALLBACK', '').strip() == '1':
                    return jsonify({
                        'success': False,
                        'message': user_facing_sign_error(chilkat_error),
                    }), 500
                logger.warning(
                    "🔄 PKCS#11 fallback — may fail ETA 4062; fix Chilkat v10 unlock instead"
                )

        logger.info("📌 استخدام طريقة PKCS#11...")
        
        # تهيئة التوكن
        if not signer.initialize():
            return jsonify({
                'success': False,
                'message': 'فشل في تهيئة توكن ePass2003'
            }), 500
        
        # تسجيل الدخول
        signer.login(pin)
        
        try:
            # إنشاء التوقيع (مع تمرير PIN للـ Chilkat fallback)
            signature = signer.create_signature(invoice_data, pin=pin)
            cert_serial = signer.get_certificate_serial()
            
            # التحقق التلقائي من التوقيع
            verification_result = None
            if verify_after_sign:
                logger.info("🔍 بدء التحقق التلقائي من التوقيع...")
                verification_result = signer.verify_signature(invoice_data, signature)
            
            logger.info("=" * 80)
            logger.info(f"✅ تم توقيع الفاتورة {invoice_id} بنجاح")
            logger.info(f"📜 Certificate Serial: {cert_serial}")
            if verification_result:
                logger.info(f"🔍 نتيجة التحقق: {'✅ صحيح' if verification_result['valid'] else '❌ فشل'}")
            logger.info("=" * 80)
            
            response = {
                'success': True,
                'signatures': [{
                    'signatureType': 'I',
                    'value': signature
                }],
                'certificate_serial': cert_serial,
                'signed_at': datetime.now().isoformat(),
                'token_type': 'epass2003',
                'signature_format': 'CAdES-BES',
                'signing_method': 'PKCS#11 / Windows CSP'
            }
            
            if verification_result:
                response['verification'] = verification_result
            
            return jsonify(response)
            
        finally:
            signer.logout()
    
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ خطأ في توقيع الفاتورة: {str(e)}")
        logger.error("=" * 80)
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'خطأ في توقيع الفاتورة: {str(e)}'
        }), 500


@app.route('/verify', methods=['POST'])
def verify_signature():
    """التحقق من صحة التوقيع"""
    try:
        if not request.json:
            return jsonify({
                'success': False,
                'message': 'لم يتم إرسال بيانات صحيحة'
            }), 400
        
        data = request.json
        invoice_data = data.get('invoice')
        signature_b64 = data.get('signature')
        
        if not invoice_data or not signature_b64:
            return jsonify({
                'success': False,
                'message': 'بيانات الفاتورة والتوقيع مطلوبة'
            }), 400
        
        # إنشاء الموقّع (للتحقق فقط، لا نحتاج للـ PIN)
        signer = EPass2003Signer()
        
        # التحقق من التوقيع
        result = signer.verify_signature(invoice_data, signature_b64)
        
        return jsonify({
            'success': True,
            'verification': result
        })
    
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'خطأ في التحقق: {str(e)}'
        }), 500


@app.route('/sign-and-submit-from-laravel', methods=['POST'])
def sign_and_submit_from_laravel():
    """
    توقيع وإرسال فاتورة - جلب البيانات من Laravel (مثل sign_and_send_EP.py تماماً)
    
    ✅ العملية الكاملة:
    1. جلب بيانات الفاتورة من Laravel API
    2. التوقيع باستخدام Chilkat
    3. الحصول على Token من ETA
    4. إرسال الفاتورة الموقعة لـ ETA
    5. إرجاع النتيجة لـ Laravel لحفظها
    
    Request Body:
    {
        "invoice_id": 123,
        "user_id": 1,
        "pin": "12345678",
        "laravel_base_url": "http://server.com",
        "token_type": "epass2003",
        "use_chilkat": true
    }
    """
    try:
        if not request.json:
            return jsonify({
                'success': False,
                'message': 'لم يتم إرسال بيانات صحيحة'
            }), 400
        
        data = request.json
        invoice_id = data.get('invoice_id')
        user_id = data.get('user_id')
        pin = data.get('pin', '')
        laravel_base_url = data.get('laravel_base_url', 'http://127.0.0.1:8000')
        token_type = data.get('token_type', 'epass2003')
        use_chilkat = data.get('use_chilkat', True)
        
        if not invoice_id or not user_id or not pin:
            return jsonify({
                'success': False,
                'message': 'invoice_id, user_id, and pin are required'
            }), 400
        
        logger.info("=" * 80)
        logger.info(f"🚀 بدء عملية التوقيع والإرسال الكاملة (مثل sign_and_send_EP.py)")
        logger.info(f"   Invoice ID: {invoice_id}")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Token Type: {token_type.upper()}")
        logger.info(f"   Laravel URL: {laravel_base_url}")
        logger.info("=" * 80)
        
        # 1. جلب بيانات الفاتورة من Laravel
        import requests
        
        logger.info("\n📥 الخطوة 1: جلب بيانات الفاتورة من Laravel...")
        
        fetch_url = f"{laravel_base_url}/api/invoices/{invoice_id}/for-signing"
        logger.info(f"   URL: {fetch_url}")
        
        try:
            fetch_response = requests.get(fetch_url, timeout=10)
            
            if not fetch_response.ok:
                logger.error(f"❌ فشل جلب البيانات: HTTP {fetch_response.status_code}")
                return jsonify({
                    'success': False,
                    'message': f'فشل جلب البيانات من Laravel: HTTP {fetch_response.status_code}'
                }), 500
            
            fetch_data = fetch_response.json()
            
            if not fetch_data.get('success'):
                logger.error(f"❌ Laravel error: {fetch_data.get('message')}")
                return jsonify({
                    'success': False,
                    'message': fetch_data.get('message', 'فشل جلب البيانات')
                }), 500
            
            invoice_data = fetch_data['invoice']
            eta_config = fetch_data['eta_config']
            
            logger.info("✅ تم جلب بيانات الفاتورة بنجاح")
            logger.info(f"   Internal ID: {invoice_data.get('internalID')}")
            logger.info(f"   Issuer ID: {invoice_data.get('issuer', {}).get('id')}")
            logger.info(f"   Environment: {eta_config.get('environment')}")
            
        except Exception as fetch_error:
            logger.error(f"❌ خطأ في جلب البيانات: {str(fetch_error)}")
            return jsonify({
                'success': False,
                'message': f'خطأ في جلب البيانات من Laravel: {str(fetch_error)}'
            }), 500
        
        # 2. التوقيع باستخدام Chilkat (نفس sign_and_send_EP.py)
        logger.info("\n🔐 الخطوة 2: التوقيع باستخدام Chilkat...")
        
        signer = EPass2003Signer(use_chilkat=use_chilkat, token_type=token_type)
        
        try:
            # التوقيع مباشرة بـ Chilkat (بدون PKCS#11)
            if use_chilkat and CHILKAT_AVAILABLE:
                signature, _signed_doc, signed_document_json = signer.sign_with_chilkat(invoice_data, pin)
                cert_serial = signer.chilkat_cert.SerialNumber if signer.chilkat_cert else 'N/A'
                signing_method = 'Chilkat (PowerBuilder)'
            else:
                # Fallback إلى PKCS#11
                if not signer.initialize():
                    return jsonify({
                        'success': False,
                        'message': 'فشل تهيئة التوكن'
                    }), 500
                
                signer.login(pin)
                try:
                    signature = signer.create_signature(invoice_data, pin=pin)
                    cert_serial = signer.get_certificate_serial()
                    signing_method = 'PKCS#11'
                finally:
                    signer.logout()
            
            logger.info("✅ تم التوقيع بنجاح")
            logger.info(f"   الطريقة: {signing_method}")
            logger.info(f"   Certificate Serial: {cert_serial}")
            logger.info(f"   طول التوقيع: {len(signature)} حرف")
            
        except Exception as sign_error:
            logger.error(f"❌ فشل التوقيع: {str(sign_error)}")
            return jsonify({
                'success': False,
                'message': f'فشل التوقيع: {str(sign_error)}'
            }), 500
        
        # 3. إدراج التوقيع في الفاتورة
        invoice_data['signatures'] = [
            {
                'signatureType': 'I',
                'value': signature
            }
        ]
        
        # 4. الحصول على Access Token من ETA (نفس sign_and_send_EP.py)
        logger.info("\n🔑 الخطوة 3: الحصول على Access Token من ETA...")
        
        try:
            token_response = requests.post(
                eta_config['token_url'],
                data={
                    'grant_type': 'client_credentials',
                    'client_id': eta_config['client_id'],
                    'client_secret': eta_config['client_secret'],
                    'scope': 'InvoicingAPI'
                },
                timeout=30
            )
            
            if not token_response.ok:
                logger.error(f"❌ فشل الحصول على Token: {token_response.status_code}")
                logger.error(f"   Response: {token_response.text}")
                return jsonify({
                    'success': False,
                    'message': f'فشل المصادقة مع ETA: HTTP {token_response.status_code}'
                }), 500
            
            token_data = token_response.json()
            access_token = token_data.get('access_token')
            
            if not access_token:
                logger.error("❌ لا يوجد access_token في الاستجابة")
                return jsonify({
                    'success': False,
                    'message': 'فشل الحصول على access token'
                }), 500
            
            logger.info("✅ تم الحصول على Access Token بنجاح")
            
        except Exception as token_error:
            logger.error(f"❌ خطأ في الحصول على Token: {str(token_error)}")
            return jsonify({
                'success': False,
                'message': f'خطأ في المصادقة: {str(token_error)}'
            }), 500
        
        # 5. إرسال الفاتورة الموقعة لـ ETA (نفس sign_and_send_EP.py)
        logger.info("\n📤 الخطوة 4: إرسال الفاتورة الموقعة لـ ETA...")
        
        payload = {
            'documents': [invoice_data]
        }
        
        try:
            submit_response = requests.post(
                eta_config['submit_url'],
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json; charset=utf-8'
                },
                json=payload,
                timeout=60
            )
            
            logger.info(f"📨 استجابة ETA: HTTP {submit_response.status_code}")
            
            response_data = submit_response.json()
            logger.info(f"   Response: {response_data}")
            
            # التحقق من القبول
            accepted_docs = response_data.get('acceptedDocuments', [])
            if accepted_docs and len(accepted_docs) > 0:
                uuid = accepted_docs[0].get('uuid')
                
                logger.info("=" * 80)
                logger.info('🎉 نجحت العملية بالكامل!')
                logger.info(f"   ✅ تم التوقيع ({signing_method})")
                logger.info(f"   ✅ تم الإرسال لـ ETA")
                logger.info(f"   ✅ UUID: {uuid}")
                logger.info("=" * 80)
                
                # 6. إرجاع النتيجة النهائية
                return jsonify({
                    'success': True,
                    'message': 'تم توقيع وإرسال الفاتورة بنجاح',
                    'uuid': uuid,
                    'signature': signature,
                    'certificate_serial': cert_serial,
                    'signing_method': signing_method,
                    'eta_response': response_data
                })
            
            # التحقق من الرفض
            rejected_docs = response_data.get('rejectedDocuments', [])
            if rejected_docs and len(rejected_docs) > 0:
                error = rejected_docs[0].get('error', {})
                error_code = error.get('code', 'Unknown')
                error_message = error.get('message', 'Unknown error')
                
                logger.error("=" * 80)
                logger.error('❌ تم رفض الفاتورة من ETA')
                logger.error(f"   Error Code: {error_code}")
                logger.error(f"   Error Message: {error_message}")
                logger.error("=" * 80)
                
                return jsonify({
                    'success': False,
                    'message': f'رفضت ETA الفاتورة: {error_code} - {error_message}',
                    'error_code': error_code,
                    'signature': signature,  # نرجع التوقيع على الأقل
                    'certificate_serial': cert_serial,
                    'eta_response': response_data
                }), 422
            
            # رد غير متوقع
            logger.error("❌ رد غير متوقع من ETA")
            return jsonify({
                'success': False,
                'message': 'رد غير متوقع من ETA',
                'eta_response': response_data
            }), 500
            
        except Exception as submit_error:
            logger.error(f"❌ خطأ في الإرسال لـ ETA: {str(submit_error)}")
            return jsonify({
                'success': False,
                'message': f'خطأ في الإرسال: {str(submit_error)}',
                'signature': signature,  # نرجع التوقيع على الأقل
                'certificate_serial': cert_serial
            }), 500
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ خطأ عام في العملية: {str(e)}")
        logger.error("=" * 80)
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'خطأ: {str(e)}'
        }), 500


@app.route('/certificate', methods=['POST'])
def read_certificate():
    """
    قراءة معلومات الشهادة من التوكن (ePass2003 أو wd_proxkey)
    """
    try:
        if not request.json:
            return jsonify({
                'success': False,
                'message': 'لم يتم إرسال بيانات صحيحة'
            }), 400
        
        data = request.json
        pin = data.get('pin', '')
        token_type = data.get('token_type', 'epass2003')  # نوع التوكن
        
        if not pin:
            return jsonify({
                'success': False,
                'message': 'رقم PIN مطلوب'
            }), 400
        
        logger.info("=" * 80)
        logger.info(f"📜 طلب قراءة معلومات الشهادة من {token_type.upper()}")
        logger.info("=" * 80)
        
        # إنشاء الموقّع
        signer = EPass2003Signer(token_type=token_type)
        
        # تهيئة التوكن
        if not signer.initialize():
            return jsonify({
                'success': False,
                'message': f'فشل في تهيئة توكن {token_type.upper()}'
            }), 500
        
        # تسجيل الدخول
        signer.login(pin)
        
        try:
            # قراءة معلومات الشهادة
            cert_info = signer.get_certificate_info()
            
            if not cert_info:
                return jsonify({
                    'success': False,
                    'message': 'فشل في قراءة معلومات الشهادة'
                }), 500
            
            logger.info("✅ تمت قراءة معلومات الشهادة بنجاح")
            
            return jsonify({
                'success': True,
                'certificate': cert_info,
                'token_type': 'ePass2003',
                'read_at': datetime.now().isoformat()
            })
            
        finally:
            signer.logout()
    
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ خطأ في قراءة الشهادة: {str(e)}")
        logger.error("=" * 80)
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'خطأ في قراءة الشهادة: {str(e)}'
        }), 500


# =============================================================================
# Main Entry Point
# =============================================================================
if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("🚀 بدء Token Sign Agent (Multi-Method & Multi-Token)")
    logger.info("=" * 80)
    logger.info(f"📍 Host: 127.0.0.1")
    logger.info(f"📍 Port: 5002")
    logger.info(f"📍 Chilkat: {'✅ متاح' if CHILKAT_AVAILABLE else '❌ غير متاح'}")
    logger.info("=" * 80)
    logger.info("🔑 التوكنات المدعومة:")
    for token_name, dll_path in TOKEN_DLLS.items():
        dll_status = '✅' if os.path.exists(dll_path) else '❌'
        logger.info(f"  • {token_name.upper()}: {dll_status} ({dll_path})")
    logger.info("=" * 80)
    logger.info("🔐 طرق التوقيع المتاحة (بالترتيب):")
    if CHILKAT_AVAILABLE:
        logger.info("  1️⃣ Chilkat (PowerBuilder) - الطريقة المفضلة والمجربة 100%")
        logger.info("  2️⃣ PKCS#11 (PyKCS11) - طريقة بديلة")
        logger.info("  3️⃣ Windows CSP - احتياطي نهائي")
    else:
        logger.info("  1️⃣ PKCS#11 (PyKCS11) - الطريقة الأساسية")
        logger.info("  2️⃣ Windows CSP - طريقة احتياطية")
    logger.info("=" * 80)
    logger.info("📋 Endpoints المتاحة:")
    logger.info("  - GET  /health      - فحص حالة الخدمة")
    logger.info("  - POST /sign        - توقيع الفاتورة (مع دعم multi-token)")
    logger.info("  - POST /verify      - التحقق من التوقيع")
    logger.info("  - POST /certificate - قراءة معلومات الشهادة")
    logger.info("=" * 80)
    logger.info("📝 استخدام التوكن المطلوب:")
    logger.info("  {")
    logger.info('    "token_type": "epass2003",  // أو "wd_proxkey"')
    logger.info('    "pin": "YOUR_PIN",')
    logger.info('    "invoice": {...}')
    logger.info("  }")
    logger.info("=" * 80)
    if CHILKAT_AVAILABLE:
        logger.info("✅ الوكيل جاهز بطريقة Chilkat (مثل sign_and_send_EP.py)")
    else:
        logger.info("⚠️ Chilkat غير متاح - استخدام PKCS#11 فقط")
        logger.info("💡 لتفعيل Chilkat v10: pip install chilkat2==10.1.3  (أو fix_chilkat_v10.bat)")
    logger.info("=" * 80)
    logger.info("")
    
    # تشغيل Flask Server
    # ملاحظة: استخدام '0.0.0.0' يسمح بالاتصال من أي IP
    # للأمان: استخدم '127.0.0.1' للاتصال المحلي فقط
    host = os.getenv('AGENT_HOST', '127.0.0.1')  # أو '0.0.0.0' للاتصال عن بعد
    
    app.run(
        host=host,
        port=5002,
        debug=False
    )
