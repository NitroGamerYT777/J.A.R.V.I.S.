# JARVIS 3D core

Foydalanuvchi yuborgan olti rakursdagi rasmlar asosida Python orqali qayta qurilgan 3D model. Bu Meshy modelining asl eksporti emas; umumiy shakl va tuzilma referensga mos qayta modellashtirilgan. Mayda metall detallari va sxema chiziqlari protseduraviy yaratilgan.

## Fayllar

- `jarvis-core.glb` — animatsiyasiz, barcha kerakli teksturalari ichiga joylangan model.
- `jarvis-core-animated.glb` — 24 soniyalik aylanish va pulsatsiya sikli bilan.
- `core-base-color.png`, `core-emissive.png` — tahrirlash uchun teksturalar; GLB ularni alohida talab qilmaydi.
- `previews/` — haqiqiy WebGL rendererda olingan old, qiya, yon va orqa ko'rinishlar.

`OuterRing`, `InnerRing`, `Core` obyektlarining aylanish markazi `[0, 0, 0]`. Shaffof `GlassShell` yadroning bolasi bo'lib, u bilan birga harakatlanadi. Old tomoni `+Z`, yuqori tomoni `+Y`. Tashqi diametr taxminan 4,2 birlik; ilovada modelni umumiy masshtablash mumkin.

## Lokal ko'rish

Loyiha ildizidan:

```powershell
python scripts/preview_jarvis_core.py
```

Brauzerda `http://127.0.0.1:8766` manzilini oching; server tashqi tarmoqqa ochilmaydi. Modelni sichqoncha bilan aylantirish, yaqinlashtirish, to'r ko'rinishini tekshirish va holat animatsiyalarini almashtirish mumkin. `index.html` faylini bevosita ikki marta bosish o'rniga shu serverdan foydalaning.

Ko'rish oynasidagi eshitish va gapirish holatlari hozircha animatsiya namoyishi. Mikrofon yoki ovozli AI ulanishi yo'q. Model JARVISning mavjud Tkinter oynasiga hali ulanmagan.

GLB fayllarda ko'k qismlar emissive materialga ega. Ko'rish oynasi qo'shimcha bloom, yoritish va akslanish beradi; boshqa 3D dasturda shu effektlar boshqacha ko'rinishi mumkin. Ikki GLB ham haqiqiy, barcha tomonlardan ko'riladigan geometriyaga ega.

## Qayta yaratish va tekshirish

```powershell
python -m pip install -e ".[assets]"
python scripts/build_jarvis_core.py
python scripts/check_jarvis_core.py
python scripts/validate_jarvis_core.py
```

`check_jarvis_core.py` uchun preview serveri ishlab turishi va Selenium/Chrome o'rnatilgan bo'lishi kerak. `validate_jarvis_core.py` Khronos glTF Validator paketini bir marta yuklaydi va Node.js talab qiladi. `model-info.json` geometriya haqida ma'lumot beradi.

Preview uchun MIT litsenziyali three.js 0.180.0 lokal nusxasi `vendor/three/` ichida, uning litsenziyasi ham saqlangan. Uni qayta olish uchun `python scripts/vendor_three.py` ishlatiladi; yuklangan npm paketi SHA-512 orqali tekshiriladi.
