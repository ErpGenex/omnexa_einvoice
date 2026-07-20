Omnexa — وكيل توقيع USB (E-Invoice)
====================================

1) ثبّت تعريف توكن ePass2003 (DLL في System32).
2) انسخ chilkat_config.json.example إلى chilkat_config.json وضع مفتاح Chilkat v10
   (أو استخدم Branch → Chilkat Unlock Code في ERP).
3) شغّل Start_Omnexa_ESigning_Agent.bat
4) في ERP: Branch → Signing Agent URL = http://127.0.0.1:5002
5) من متصفح Windows على نفس الجهاز: Sign / Send E-Invoice

لا يحتاج Python أو pip على جهاز التشغيل — كل المكتبات داخل المجلد.
