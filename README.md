# JARVIS

Python’da yoziladigan, kengaytiriladigan shaxsiy yordamchi. U lokal buyruqlar, xotira (eslatmalar), Gemini AI bilan tabiiy suhbat va xavfsiz amallarni tasdiqlash modelini beradi.

## Hozir ishlaydigan buyruqlar

- `yordam`
- `soat nechchi`
- `eslatma ol: Sut sotib olish`
- `eslatmalarim`
- Boshqa har qanday savol — Gemini AI javob beradi.
- `chiqish`
- Grafik oynada: promptdan Word/Excel/PowerPoint yaratish va lokal konvertatsiya (**Office Studio**).

## Ishga tushirish

Avval Python 3.11 yoki undan yangi versiyasini o‘rnating va terminalni qayta oching. So‘ng:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
jarvis
```

## Desktop Command Center

Asosiy grafik oyna quyidagi buyruq bilan ochiladi:

```powershell
python -m jarvis.ui.app
```

Yoki editable o‘rnatishdan keyin `jarvis-ui` buyrug‘idan foydalaning. Oyna markazida haqiqiy GLB modelini chizadigan, OpenGL orqali ishlaydigan JARVIS 3D yadrosi bor. Halqalar va yadro kutish, AI so‘rovini tahlil qilish va javob berish holatlarida turlicha aylanadi va pulsatsiya qiladi. Sichqoncha bilan ushlab aylantiring, g'ildirak bilan yaqinlashtiring, ikki marta bosib boshlang'ich ko'rinishga qayting. Buning uchun alohida brauzer yoki preview server talab qilinmaydi. OpenGL mavjud bo'lmasa oddiy 2D yadro avtomatik ishlaydi. Pastdagi kiritish satri Gemini AI va lokal JARVIS funksiyalariga bevosita ulangan.

Yangi 3D versiyaga o'tishda `python -m pip install -e ".[dev]"` buyrug'i bilan bog'liqliklarni yangilang. NumPy, Pillow, PyOpenGL va pyopengltk asosiy o'rnatishga kiritilgan. Model oddiy wheel paketiga ham qo'shiladi. Hozir pulsatsiya ilova holatiga bog'langan; haqiqiy mikrofon va audio amplitudasi hali ulanmagan.

Yangilangan loyiha bilan `yt-dlp`, `selenium`, `PyAutoGUI` va `pyperclip` ham o'rnatiladi: `python -m pip install -e ".[dev]"`. Music Agent YouTube qidiruvidan aniq video ID oladi va oddiy `youtube.com/watch` sahifasini JARVISga tegishli minimallashtirilgan Chrome profilida ochadi. U video vaqtining yurayotganini tekshiradi; bu eski `/embed` playeridagi `Error 153` xatosini chetlab o'tadi. `Musiqani to'xtat` ijroni pauzaga qo'yadi, `davom ettir` o'sha videoni davom ettiradi, `musiqani o'chir` esa JARVISning fon Chrome oynasini yopadi. JARVIS yopilganda uning musiqa playeri ham yopiladi.

Testlar alohida `pytest` orqali bajariladi:

```powershell
python -m pytest -q
```

## Office Studio: Word, Excel va PowerPoint

Yon menyudagi **Office Studio** bo'limida hujjat turini tanlang, to'liq topshiriq yozing va **HUJJATNI YARATISH**ni bosing. Yoki asosiy chatga shunday yozing:

```text
Sun'iy intellekt haqida o'zbekcha 8 slaydli PowerPoint taqdimoti tayyorla
Oylik shaxsiy budjet uchun formulali Excel jadvali yarat, summalar namuna ekanini belgilab qo'y
Maktab direktoriga ariza uchun Word hujjati tayyorla
```

JARVIS mos Office agentiga topshiriq beradi. AI strukturali JSON mazmun yaratadi, lokal Python modullari esa haqiqiy, tahrirlanadigan `.docx`, `.xlsx`, `.pptx` fayl yaratadi. Word bo'lim/jadval/ro'yxatlari, Excel varaqlari/formulalari/grafiklari hamda PowerPoint slaydlari/jadvallari/izohlari qo'llanadi. Slaydlar soni aniq so'ralsa, AI natijasi tekshiriladi. Noto'g'ri tuzilma bir marta AI orqali qayta tuzatiladi; yana xato bo'lsa, task xato holati bilan tugaydi, yarim tayyor fayl berilmaydi. Bu imkoniyat ishlashi uchun Agentlar bo'limida ishlaydigan API/model ulangan bo'lishi kerak. **Assignments → Office Agent** orqali unga boshqa AI tayinlash mumkin; default Chat AI ishlatiladi.

**TAYYOR FAYLLAR** kutubxonasidan natijani Microsoft Office yoki mos boshqa dasturda oching. Fayllar lokal `data/office/outputs/` papkasiga noyob nom bilan saqlanadi; asl fayl hech qachon ustidan yozilmaydi. Yaratilgan faylni **MANBA SIFATIDA TANLASH** orqali keyingi topshiriqda ishlatish mumkin. Makroslar va AI yozgan dastur kodi bajarilmaydi. Excel formulalari lokal havolalar va ruxsat etilgan funksiyalar bilan cheklanadi; ularning qiymatlari Excel faylni ochib qayta hisoblaganda paydo bo'ladi. Formulaga o'xshash oddiy katak matni avtomatik kodga aylanmaydi. Dizayn hozircha lokal shablonlarga asoslanadi; internetdan rasm qidirish yoki foydalanuvchi shablonini aynan nusxalash bu modulda yo'q.

### Manbadan yangi hujjat

**MANBA FAYL → TANLASH** orqali DOCX, XLSX, PPTX, PDF, CSV yoki TXT tanlang va uni qanday qayta ishlashni yozing. Natija yangi hujjat bo'ladi; manbaning dastlabki bezaklari yoki Word tahrirlari aynan saqlanishi kafolatlanmaydi. Manba fayldan **24000 belgigacha matn** Office agentiga ulangan AI xizmatiga yuboriladi. Bunday task avtomatik boshlanmaydi: **Tasks → BATAFSIL KO'RISH** orqali fayl yo'lini ko'rib, yuborishni tasdiqlang. Tasdiqlamasangiz manba matni AI'ga yuborilmaydi. Oddiy yangi hujjat yaratishda faqat yozgan promptingiz yuboriladi.

### Konvertatsiya

AI kalitisiz ham ishlaydi. Manbani tanlang, formatni belgilang va **KONVERTATSIYA QILISH**ni bosing:

- DOCX / XLSX / PPTX → PDF (Windows va o'rnatilgan Microsoft Office kerak).
- CSV ↔ XLSX. XLSX bir nechta varaqdan iborat bo'lsa, CSV uchun varaq nomini yozing. Hisoblangan formula qiymati keshda yo'q bo'lsa, faylni Excel'da hisoblab saqlash so'raladi.
- TXT ↔ DOCX; DOCX / PPTX / PDF → TXT (matn olinadi, sahifa bezaklari saqlanmaydi).

PDF eksportida alohida Office jarayoni ishlaydi; manba faqat o'qish uchun ochiladi, makroslar va xavfli tashqi bog'lanishlar bloklanadi. Foydalanuvchining ochiq Office jarayoniga qo'shilish xavfsiz bo'lmasa, konvertatsiya xatolik bilan to'xtaydi. Office aktivatsiyasi yoki ochish oynasi to'sqinlik qilsa, uni foydalanuvchi hal qilishi kerak; avtomatik chetlab o'tilmaydi.

XLSX → PDF eksportida mahalliy katak havolalari va ruxsat etilgan funksiyalar qayta hisoblanadi; manba faylga saqlanmaydi. Tashqi, foydalanuvchi yozgan funksiya yoki qo'llanmaydigan dinamik formulalar topilsa, eski hisoblangan qiymatlar bilan PDF berish o'rniga aniq xato qaytariladi.

Manba chegarasi 20 MB; makrosli DOCM/XLSM/PPTM, eski DOC/XLS/PPT va parollangan fayllar qabul qilinmaydi. PDF → Word/Excel, skanerdan OCR, murakkab mavjud hujjatni in-place tahrirlash va barcha formatlarni istalgan formatga o'girish hozircha yo'q. Natijani ishlatishdan oldin mazmuni, hisob-kitoblari va bezaklarini tekshiring: AI xato yoki taxminiy ma'lumot berishi mumkin. Office fayllari `data/` ichida qoladi va GitHub'ga qo'shilmaydi.

Office oqimini bulutga ulanmasdan tekshirish: `python scripts/check_office_integration.py`. Bu vaqtinchalik test bazasi, fake AI va test fayllaridan foydalanadi; sizning task tarixingizni tozalamaydi va haqiqiy AI so'rovi yubormaydi.

### Interfeys effektlari

Hover/bosish animatsiyalari, harakatlanuvchi panel chiziqlari, holat to'lqini, RAM/Disk doiraviy indikatorlari va yangi xabar yoritilishi bor. Pastdagi **FX** yoki `Ctrl+Shift+E` dekorativ animatsiyalarni yoqadi/o'chiradi. To'lqin ovoz balandligini o'lchamaydi, ilova holatini tasvirlaydi; CPU'dagi ACTIVE ham foizli CPU o'lchovi emas. 2D interfeys effektlari bitta umumiy taymerda ishlaydi va oyna yashirilganda chizilmaydi.

`tests\\test_agent.py` faylini bevosita ishga tushirish testlarni bajarish usuli emas: `src` tuzilmasidagi `jarvis` paketi u holda avtomatik topilmaydi.

## Gemini API kaliti

1. [Google AI Studio](https://aistudio.google.com/app/apikey) sahifasida bepul API kaliti yarating.
2. `.env.example` faylidan `.env` nusxa oling.
3. `.env` ichidagi `GEMINI_API_KEY` qiymatiga kalitingizni qo‘ying.
4. `jarvis`ni qayta ishga tushiring.

Kalit `.gitignore` orqali himoyalangan; uni chatga, GitHub'ga yoki boshqa odamlarga yubormang. Dastur rasmiy Gemini REST API'sidan foydalanadi, shuning uchun qo‘shimcha Python kutubxonasi talab qilinmaydi.

Kalitni oynaning o'zida ham ulash mumkin: **Agents** bo'limini oching, AI provayderi va modelni tanlang, API kalitini kiriting. Tanlov lokal `data/connections.json` faylida saqlanadi.

Hozir ilova ichidan ulanadigan provayderlar:

- Google Gemini — `gemini-3.6-flash` standart tanlov bilan
- OpenAI — `gpt-6-astra` standart tanlov bilan
- Groq — `openai/gpt-oss-20b` standart tanlov bilan
- OpenRouter — `~openai/gpt-latest` standart tanlov bilan

Model maydonini qo'lda istalgan hisobingizda mavjud model nomiga almashtirish mumkin. Bitta provayder JARVISning faol AI yadrosi bo'ladi; boshqasini tanlab ulash esa faol provayderni almashtiradi.

## AI Connections va Agent Assignments

Yon menyudagi **Agents** bo'limi API ulanishlarini qo'shish va agentlar holatini alohida boshqaradi. Bir provayderga bir nechta API kalit qo'shish mumkin; ular lokal `data/connections.json` faylida saqlanadi. Yangi Gemini kaliti qo'shilganda u default Chat AI bo'ladi.

**Assignments** bo'limi esa har bir agentni (Browser, File, Automation va boshqalar) kerakli AI ulanishiga biriktiradi. Gemini foydalanuvchi xabarini avval `browser`, `computer`, `question` yoki `other` turiga ajratadi. Browser/computer taski mos agentga biriktiriladi; dastur amal xavfini tekshirib, oddiy ishni avtomatik bajaradi yoki Tasks panelida tasdiq kutadi.

API 401 yoki 403 xatosi qaytarsa, JARVIS uni yaroqsiz yoki muddati tugagan deb belgilaydi va lokal kalit ro'yxatidan o'chirishga ruxsat so'raydi.

## Agentlar va Tasks paneli

JARVIS ichida AI Core, Memory va System Agent doim ulangan. Browser, File va Automation agentlari esa bajariladigan vazifaga qarab ishga tushadi; oynada ularning ulangan, ulanmagan yoki ishlayotgan holati ko'rinadi.

Barcha amallar **Tasks / approval queue** tarixiga yoziladi, lekin har biriga tasdiq so'ralmaydi. Sayt ochish, qidirish, musiqa ijrosi/boshqaruvi, sahifani o'qish, mavzuni almashtirish, scroll, skrinshot, oyna almashtirish, oddiy bir qatorli matn yozish hamda ro'yxatdagi Notepad/Calculator/Explorer/Settings ilovalarini argumentsiz ochish avtomatik bajariladi.

Yuborish, o'chirish, xarid/to'lov, parol maydonlari, noma'lum dastur/terminal, saqlash yoki yuborishga olib kelishi mumkin bo'lgan klavishlar tasdiq kutadi. Koordinata, drag yoki ta'siri noma'lum CSS/tugmani xavfsiz deb taxmin qilmaydi — ular ham tekshirish uchun qoladi. Bu qoidalar AI aytgan "xavfsiz" belgisiga emas, lokal amal va parametrlariga tayanadi; ular butun kompyuter uchun to'liq xavfsizlik kafolati emas. Workflow'dagi barcha qadamlar oldindan tekshiriladi: bittasi muhim bo'lsa, hech biri tasdiqsiz boshlanmaydi. Tasdiq sababi panelda va **BATAFSIL KO'RISH** oynasida ko'rinadi.

Tasdiq kutayotgan va bajarilayotgan tasklar ro'yxat boshida turadi. **BAJARILGANLARNI TOZALASH** barcha muvaffaqiyatli tugagan task yozuvlarini (faqat ko'rinayotgan 30 tasini emas) lokal bazadan o'chiradi; bu tarix yozuvlarini ilova orqali qaytarib bo'lmaydi. Kutilayotgan, bajarilayotgan, rad etilgan va xato tugagan tasklar saqlanadi; kompyuterdagi fayllar o'chirilmaydi. Ilova qayta ochilganda eski tasdiq kutayotgan tasklar o'z-o'zidan bajarilmaydi.

Quyidagi buyruqlarni sinab ko'ring:

```text
vazifa qo'sh: Ertaga loyiha rejasini ko'rib chiqish
brauzerda och: https://example.com
loyiha papkasini och
```

Gemini ulangan bo'lsa, buyruq qat'iy kalit so'zga bog'lanmaydi. Masalan, `example.com saytini och`, `Python bo'yicha maqolalarni qidir` yoki `kalkulyatorni ishga tushir` kabi tabiiy jumlalar AI tomonidan tahlil qilinadi. Model faqat quyidagi tekshiriladigan JSON shaklida kompyuter amali taklif qila oladi:

```json
{"type": "command", "command": "open_url", "target": "example.com", "reply": "Saytni ochish uchun task yaratdim."}
```

Selenium Browser Agent sayt ochish, element bosish, maydonga matn kiritish, Enter va boshqa tugmalarni bosish, tablarni boshqarish, sahifani o'qish, scroll, oldinga/ortga yurish va skrinshot olishni biladi. RoboContest uchun `browser_set_theme` amali joriy mavzuni tekshirib `dark` yoki `light` holatiga qo'yadi — CSS selektorini taxmin qilmaydi. PyAutoGUI Desktop Agent oyna fokusini almashtirish, ilova ishga tushirish, koordinatani bosish, matn yozish, klavish kombinatsiyasi, scroll va ekran suratini olishni biladi. AI bir nechta qadam kerakligini aniqlasa `workflow` task yaratadi (ko'pi bilan 8 qadam). **BATAFSIL KO'RISH** tugmasi orqali butun amal ro'yxatini ko'rib, so'ng tasdiqlang.

Misollar:

```text
example.com saytini och
RoboContestda ochgan sahifangni mavzusini to'q ko'k qil
Sahifadagi Search tugmasini bos
Search maydoniga Python yoz
Notepadni ishga tushirib, unga Salom yoz
Menga ekran rasmini saqla
Blinding Lights qo'shig'ini qo'y
Musiqani pauzaga qo'y / davom ettir / keyingi qo'shiq / oldingi qo'shiq
Musiqani o'chir (fon Chrome oynasini yop)
Musiqa ovozini ko'tar / pasaytir
```

Browser Agent o'zining alohida Chrome profilini ishlatadi. Selenium Manager birinchi ishga tushishda mos ChromeDriver'ni yuklab olishi mumkin. Desktop Agent ekranning faol oynasiga ta'sir qiladi; PyAutoGUI favqulodda to'xtatish uchun sichqonchani ekranning yuqori chap burchagiga olib borish imkonini saqlaydi.

## Yo‘l xaritasi

Rasmlar asosida qayta qurilgan **JARVIS 3D modeli** asosiy Tkinter oynasiga ulangan. Alohida brauzer preview'i ham `assets/3d/` ichida mavjud: `python scripts/preview_jarvis_core.py` ni ishga tushirib, `http://127.0.0.1:8766` manzilini oching. Statik va animatsiyali GLB fayllari, teksturalar hamda qayta yaratish yo'riqnomasi [3D model hujjati](assets/3d/README.md)da.

1. Matnli buyruqlar va lokal xotira — tayyor.
2. Ovozli kirish/chiqish (STT/TTS) — Azure Speech bilan ulangan.
3. Kalendar, fayllar, brauzer, aqlli uy va bildirishnomalar uchun alohida modullar.
4. LLM orqali tabiiy suhbat va rejalashtirish — Gemini bilan tayyor.
5. Muhim yoki ta'siri noma'lum amallar uchun ruxsat; barcha amallar uchun jurnal.

JARVIS o'chirish, yuborish, xarid va boshqa xavfli yoki ta'siri noma'lum amallarni bajarishdan oldin aniq tasdiq so'raydi; oddiy kompyuter ishlari avtomatik bajariladi.

## Azure orqali ovozli suhbat

1. Virtual muhitda `python -m pip install -e ".[dev]"` buyrug'ini bajaring va `python -m jarvis.ui.app` bilan ilovani oching.
2. [Azure portal](https://portal.azure.com/)da Azure AI Speech resursini yarating. Uning **Keys and Endpoint** bo'limidan Key va Region qiymatlarini oling. Kalitni chat yoki GitHub'ga yubormang.
3. JARVIS chap panelidagi **AZURE SOZLAMALARI** orqali kalit, region (masalan `eastus`) va Sardor yoki Madina ovozini tanlab saqlang. **OVOZNI SINASH** haqiqiy ulanishni tekshiradi; shunchaki saqlash kalitni tekshirmaydi.
4. Pastdagi **TINGLASH** tugmasini bosib o'zbekcha gapiring. Matn mavjud AI va task tasdiqlash tizimiga yuboriladi. Avtomatik yuborishni o'chirsangiz, matn faqat yozish maydoniga tushadi.

Standart rejim bitta gapdan keyin mikrofonni to'xtatadi (25 soniyada gap eshitilmasa ham to'xtaydi). Doimiy suhbatni sozlamalarda yoqish mumkin; u ham faqat mikrofon tugmasi bosilganda boshlanadi. JARVIS javob tayyorlayotganda/gapirganda mikrofon vaqtincha to'xtaydi va keyin tiklanadi. **MIKROFONNI O'CHIR** tinglashni, **GAPIRISHNI TO'XTAT** joriy ovozni to'xtatadi; yuqoridagi **OVOZ** javoblarni ovozlashtirishni boshqaradi. 3D yadro tinglash/gapirish holatini ko'rsatadi.

Ovoz tili `uz-UZ`, ovozlar `uz-UZ-SardorNeural` va `uz-UZ-MadinaNeural`. Windows standart mikrofon/karnayi ishlatiladi; Windows Settings → Privacy & security → Microphone orqali desktop ilovalarga mikrofon ruxsatini bering. Quloqchin tashqi musiqa mikrofon orqali buyruq sifatida eshitilishining oldini olishga yordam beradi.

Kalit Windows foydalanuvchisiga bog'langan DPAPI bilan shifrlanib, Git e'tiborsiz qoldiradigan `data/voice.json` fayliga saqlanadi. Muqobil ravishda lokal `.env` ichida `AZURE_SPEECH_KEY` va `AZURE_SPEECH_REGION` berish mumkin. Mikrofon faol bo'lganda audio Azure xizmatiga yuboriladi, dastur audio fayllarni saqlamaydi. Internet va haqiqiy Azure Speech resursi kerak; Azure tarif/kvota cheklovlari amal qiladi. 401/403 xatoda kalit va region bir resursga tegishli ekanini tekshiring; audio qurilma xatosida standart mikrofon va ruxsatlarini tekshiring.
