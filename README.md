# JARVIS

Python’da yoziladigan, kengaytiriladigan shaxsiy yordamchi. U lokal buyruqlar, xotira (eslatmalar), Gemini AI bilan tabiiy suhbat va xavfsiz amallarni tasdiqlash modelini beradi.

## Hozir ishlaydigan buyruqlar

- `yordam`
- `soat nechchi`
- `eslatma ol: Sut sotib olish`
- `eslatmalarim`
- Boshqa har qanday savol — Gemini AI javob beradi.
- `chiqish`

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

**Assignments** bo'limi esa har bir agentni (Browser, File, Automation va boshqalar) kerakli AI ulanishiga biriktiradi. Gemini foydalanuvchi xabarini avval `browser`, `computer`, `question` yoki `other` turiga ajratadi. Browser/computer taski mos agentga biriktiriladi va u Tasks panelidagi tasdiqdan keyin bajariladi.

API 401 yoki 403 xatosi qaytarsa, JARVIS uni yaroqsiz yoki muddati tugagan deb belgilaydi va lokal kalit ro'yxatidan o'chirishga ruxsat so'raydi.

## Agentlar va Tasks paneli

JARVIS ichida AI Core, Memory va System Agent doim ulangan. Browser, File va Automation agentlari esa bajariladigan vazifaga qarab ishga tushadi; oynada ularning ulangan, ulanmagan yoki ishlayotgan holati ko'rinadi.

Brauzer, kompyuter va yangi musiqa ijrosi amallari **Tasks / approval queue** ga yozilib, **Tasdiqlash** tugmasidan keyin bajariladi. JARVISning o'z playeridagi pauza/davom ettirish, keyingi/oldingi trek va ovoz boshqaruvi esa darhol bajariladi; ularning natijasi ham Tasks tarixida saqlanadi. Rad etilgan, bajarilgan va xato tugagan vazifalar ham tarixda qoladi.

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
5. Har bir tashqi yoki xavfli amal uchun ruxsat, jurnal va cheklovlar.

JARVIS foydalanuvchi nomidan o‘chirishi, yuborishi, sotib olishi yoki qurilmani boshqarishi mumkin bo‘lgan har qanday amalni bajarishdan oldin aniq tasdiq so‘rashi kerak.

## Azure orqali ovozli suhbat

1. Virtual muhitda `python -m pip install -e ".[dev]"` buyrug'ini bajaring va `python -m jarvis.ui.app` bilan ilovani oching.
2. [Azure portal](https://portal.azure.com/)da Azure AI Speech resursini yarating. Uning **Keys and Endpoint** bo'limidan Key va Region qiymatlarini oling. Kalitni chat yoki GitHub'ga yubormang.
3. JARVIS chap panelidagi **AZURE SOZLAMALARI** orqali kalit, region (masalan `eastus`) va Sardor yoki Madina ovozini tanlab saqlang. **OVOZNI SINASH** haqiqiy ulanishni tekshiradi; shunchaki saqlash kalitni tekshirmaydi.
4. Pastdagi **TINGLASH** tugmasini bosib o'zbekcha gapiring. Matn mavjud AI va task tasdiqlash tizimiga yuboriladi. Avtomatik yuborishni o'chirsangiz, matn faqat yozish maydoniga tushadi.

Standart rejim bitta gapdan keyin mikrofonni to'xtatadi (25 soniyada gap eshitilmasa ham to'xtaydi). Doimiy suhbatni sozlamalarda yoqish mumkin; u ham faqat mikrofon tugmasi bosilganda boshlanadi. JARVIS javob tayyorlayotganda/gapirganda mikrofon vaqtincha to'xtaydi va keyin tiklanadi. **MIKROFONNI O'CHIR** tinglashni, **GAPIRISHNI TO'XTAT** joriy ovozni to'xtatadi; yuqoridagi **OVOZ** javoblarni ovozlashtirishni boshqaradi. 3D yadro tinglash/gapirish holatini ko'rsatadi.

Ovoz tili `uz-UZ`, ovozlar `uz-UZ-SardorNeural` va `uz-UZ-MadinaNeural`. Windows standart mikrofon/karnayi ishlatiladi; Windows Settings → Privacy & security → Microphone orqali desktop ilovalarga mikrofon ruxsatini bering. Quloqchin tashqi musiqa mikrofon orqali buyruq sifatida eshitilishining oldini olishga yordam beradi.

Kalit Windows foydalanuvchisiga bog'langan DPAPI bilan shifrlanib, Git e'tiborsiz qoldiradigan `data/voice.json` fayliga saqlanadi. Muqobil ravishda lokal `.env` ichida `AZURE_SPEECH_KEY` va `AZURE_SPEECH_REGION` berish mumkin. Mikrofon faol bo'lganda audio Azure xizmatiga yuboriladi, dastur audio fayllarni saqlamaydi. Internet va haqiqiy Azure Speech resursi kerak; Azure tarif/kvota cheklovlari amal qiladi. 401/403 xatoda kalit va region bir resursga tegishli ekanini tekshiring; audio qurilma xatosida standart mikrofon va ruxsatlarini tekshiring.
