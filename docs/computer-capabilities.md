# Computer Hub — 50 lokal qobiliyat

Yon menyudagi **Computer Hub** yoki **Tools & Skills** bo‘limini oching. Qobiliyatni tanlang, maydonlarni to‘ldiring, **TASK YARATISH** tugmasini bosing. Fayl yo‘llarini `…` tugmasi bilan tanlash mumkin. Natija shu oynada va Tasks → BATAFSIL KO‘RISH orqali ko‘rinadi. Qidiruv va guruh filtri 50 vosita orasidan keraklisini topadi.

Chatdagi tabiiy so‘rovni faol AI `computer_action` JSON rejasiga aylantiradi; bajaruvchi faqat katalogdagi amal va tekshirilgan parametrlarni qabul qiladi, AI yaratgan shell/Python kodi bajarilmaydi. Yangi fayl mazmunini yozish, matn almashtirish, nusxalash/ko‘chirish, Recycle Bin, ilova ochish, MRT va clipboard o‘zgarishlari Tasks tasdig‘ini kutadi. Avvalgi argumentsiz Notepad/Calculator/Explorer/Settings tezkor ochish qoidalari saqlangan.

Aniq qisqa so‘rovlar AI yoki internet talab qilmasdan ishlaydi:

```text
faylni top: hisobot
hisobot.txt nomli faylni top
eng katta fayllarni top
dublikat fayllarni top
Chrome ilovasini och
mrt bilan virusni tekshir
MRT hisobotini ko‘rsat
```

Murakkab so‘rovlar uchun faol AI ulanishi kerak. Bir nomga bir nechta fayl/ilova mos kelsa JARVIS taxmin qilmaydi: aniq yo‘l yoki nomni tanlashni so‘raydi. “O‘shani o‘zgartir” kabi manbasi noaniq buyruqda Computer Hub’da faylni tanlang.

## Katalog

`Tasdiq` ustuni yangi Computer Hub amallariga tegishli. “Yo‘q” xavfsizlik kafolati emas: lokal tekshiruvlardan o‘tmasa amal baribir rad etiladi.

| № | Amal | Nima qiladi | Tasdiq |
|---|---|---|---|
| 1 | `file_find` | Nom bo‘yicha fayl qidiradi | Yo‘q |
| 2 | `text_search` | UTF-8 fayllar ichidan matn va qatorini topadi | Yo‘q |
| 3 | `file_info` | Hajm, tur, o‘zgarish vaqtini ko‘rsatadi | Yo‘q |
| 4 | `folder_list` | Papka tarkibini ko‘rsatadi | Yo‘q |
| 5 | `text_read` | Matnli faylni o‘qiydi | Yo‘q |
| 6 | `text_create` | Yangi matnli fayl yaratadi; ustiga yozmaydi | Ha |
| 7 | `text_append` | Zaxira olib, matn qo‘shadi | Ha |
| 8 | `text_replace` | Aniq eski matnni yangi matnga almashtiradi | Ha |
| 9 | `file_rename` | Fayl nomini o‘zgartiradi | Ha |
| 10 | `file_move` | Faylni shu diskdagi boshqa joyga ko‘chiradi | Ha |
| 11 | `file_copy` | Fayldan yangi nusxa oladi | Ha |
| 12 | `folder_create` | Yangi papka yaratadi | Ha |
| 13 | `folder_copy` | Tekshirilgan papka tarkibidan nusxa oladi | Ha |
| 14 | `folder_rename` | Papka nomini o‘zgartiradi | Ha |
| 15 | `folder_move` | Papkani shu disk ichida ko‘chiradi | Ha |
| 16 | `file_recycle` | Alohida faylni Recycle Bin’ga yuboradi | Ha |
| 17 | `file_checksum` | SHA256 nazorat summasini hisoblaydi | Yo‘q |
| 18 | `text_diff` | Ikki matnli fayl farqini ko‘rsatadi | Yo‘q |
| 19 | `file_compare` | Ikki fayl SHA256 qiymatini solishtiradi | Yo‘q |
| 20 | `duplicates` | Hajm va hash bo‘yicha dublikatlarni guruhlaydi | Yo‘q |
| 21 | `largest_files` | Eng katta indekslangan fayllarni topadi | Yo‘q |
| 22 | `recent_files` | Yaqinda o‘zgargan fayllarni ko‘rsatadi | Yo‘q |
| 23 | `folder_stats` | Chegaralangan fayl soni va hajmini hisoblaydi | Yo‘q |
| 24 | `zip_create` | Yangi ZIP yaratadi, bo‘sh papkalarni ham saqlaydi | Ha |
| 25 | `zip_inspect` | ZIP tarkibini ochmasdan tekshiradi | Yo‘q |
| 26 | `zip_extract` | Xavfsiz nomlarni yangi papkaga chiqaradi | Ha |
| 27 | `folder_snapshot` | Lokal xizmat hududiga ZIP zaxira saqlaydi | Ha |
| 28 | `backup_list` | Tahrir/ko‘chirish va snapshot tarixini ko‘rsatadi | Yo‘q |
| 29 | `backup_restore` | Mavjud matn tahririni yoki alohida fayl ko‘chishini qaytaradi | Ha |
| 30 | `organize_preview` | Fayllarni kengaytmasiga ko‘ra saralash rejasini ko‘rsatadi | Yo‘q |
| 31 | `organize_apply` | Haqiqiy reja ID bo‘yicha saralaydi | Ha |
| 32 | `inventory_export` | Indeks natijalarini lokal CSV’ga yozadi | Yo‘q |
| 33 | `folder_tree` | Papka ichidagi fayllar daraxtini ko‘rsatadi | Yo‘q |
| 34 | `file_open` | Matnni Notepad’da, ruxsatli hujjat/media turini mos ilovada ochadi | Yo‘q |
| 35 | `file_reveal` | Explorer’da faylni tanlab ko‘rsatadi | Yo‘q |
| 36 | `app_find` | O‘rnatilgan ilovalar katalogidan qidiradi | Yo‘q |
| 37 | `app_open` | Aniq topilgan ilovani argumentsiz ishga tushiradi | Ha |
| 38 | `store_search` | Microsoft Store qidiruvini ochadi, o‘rnatmaydi | Yo‘q |
| 39 | `app_inventory` | App Paths va argumentsiz Start Menu EXE yorliqlarini ko‘rsatadi | Yo‘q |
| 40 | `app_shortcut` | Topilgan EXE uchun yangi Desktop yorlig‘i yaratadi | Ha |
| 41 | `mrt_open` | Windows MRT oynasini foydalanuvchi boshqaruvi uchun ochadi | Ha |
| 42 | `mrt_report` | Mavjud MRT jurnalining oxirgi qismini o‘qiydi | Yo‘q |
| 43 | `security_status` | Defender’ning himoya, imzo va oxirgi skan holatini o‘qiydi | Yo‘q |
| 44 | `system_info` | Windows, CPU yadrolari va RAM ma’lumotini ko‘rsatadi | Yo‘q |
| 45 | `disk_info` | Disklar hajmi va bo‘sh joyini ko‘rsatadi | Yo‘q |
| 46 | `process_list` | Eng ko‘p RAM ishlatayotgan jarayonlarni ko‘rsatadi; yopmaydi | Yo‘q |
| 47 | `battery_info` | Batareya va quvvatga ulanishni ko‘rsatadi | Yo‘q |
| 48 | `network_info` | Lokal tarmoq interfeyslari va manzillarini ko‘rsatadi | Yo‘q |
| 49 | `clipboard_format` | `trim`, `sort`, `unique` bilan clipboard matnini o‘zgartiradi | Ha |
| 50 | `clipboard_copy_path` | Tekshirilgan fayl yo‘lini clipboardga oladi | Ha |

## Hudud va xavfsizlik

Standart hudud: loyiha papkasi va mavjud Desktop/Documents/Downloads/Pictures/Music/Videos papkalari. **+ ISH PAPKASI** orqali boshqa diskdagi alohida ish papkasini o‘zingiz tanlab, hududga qo‘shishga rozilik berishingiz mumkin. AI bunday ruxsatni o‘zi kengaytira olmaydi. Qo‘shimcha yo‘llar lokal `data/computer/roots.json` faylida saqlanadi; ruxsatni bekor qilish uchun ilova yopiq paytda kerakli yo‘lni shu ro‘yxatdan olib tashlang.

Butun disk/foydalanuvchi ildizini qo‘shimcha hudud sifatida qo‘shish, tizim papkalari, AppData, `.git`, `.venv`, `.ssh`, `.aws`, `.codex`, `.agents`, `.env*`, ulanish/ovoz kaliti fayllari va PEM/KEY/PFX/P12 fayllari yopiq. JARVIS’ning `data/` xizmat hududi ham umumiy qidiruvdan tashqarida. Symlink/junction orqali fayl amali rad etiladi. Butun papkani ko‘chirish/nusxalash/arxivlashda himoyalangan yoki yashirin tarkib topilsa uni sezdirmay tashlab ketish o‘rniga amal to‘xtaydi.

Matn tahriridan oldin asl nusxa `data/computer/backups/` ga saqlanadi. UTF-8 BOM va Windows CRLF qatorlari saqlanadi. UTF-8 bo‘lmagan yoki Office/binar faylga matn tahriri qo‘llanmaydi; Word/Excel/PowerPoint uchun Office Studio saqlangan. `backup_restore` faqat kutilgan oxirgi hash mos bo‘lsa ishlaydi: tashqaridan o‘zgargan yangi ishning ustiga yozmaydi. Folder rename/move avtomatik undo’ga kirmaydi; snapshot ZIP alohida arxiv sifatida saqlanadi. Recycle Bin amali Windows orqali qaytariladi.

Mavjud natija fayli ustiga yozilmaydi. Move bitta disk ichidagi rename bilan bajariladi; boshqa diskka avval copy qiling, natijani tekshiring va kerak bo‘lsa asl faylni tasdiq bilan Recycle Bin’ga yuboring. Saralash bir nechta alohida ko‘chirishdan iborat: tashqi o‘zgarish/disk xatosida bir qismi bajarilgan bo‘lishi mumkin, bajarilgan fayl ko‘chishlari tarixga yoziladi. Arxiv/nusxa chiqarishda disk yoki ruxsat xatosi qisman yangi natija qoldirishi mumkin; mavjud foydalanuvchi fayllari ustiga yozilmaydi.

ZIP’da `../`, mutlaq yo‘l, ADS/drive nomi, Windows rezerv nomlari, symlink, shifrlangan element, katta ochilgan hajm va case-insensitive nom to‘qnashuvlari rad etiladi. EXE, BAT, PS1, LNK va makroli Office fayllari `file_open` orqali bajarilmaydi. Bu tekshiruvlar OS sandbox yoki antivirus o‘rnini bosmaydi.

Fayldan o‘qilgan mazmun avtomatik AI provayderiga yuborilmaydi. Natija lokal Tasks tarixida ko‘rinadi. Chatga yozilgan so‘rov esa odatdagi AI ulanishi orqali yuborilishi mumkin; Office manba matnini yuborish uchun oldingi alohida tasdiq qoidasi saqlangan. Clipboard mazmuni `clipboard_format` natijasiga yoki task tarixiga qo‘shilmaydi.

## MRT va Store

Ilova katalogda topilmasa JARVIS **Store qidiruvini ochaymi?** deb so‘raydi. “Ha” faqat qidiruv URI’sini ochadi; yuklash, litsenziya, to‘lov yoki o‘rnatishni foydalanuvchi o‘zi bajaradi. Katalog barcha UWP/portable ilovalarni qamrab olmaydi: topilmagani o‘rnatilmaganini isbotlamaydi. [Microsoft Store URI hujjati](https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-store-app).

MRT taski bajarilishi **oyna ochish so‘rovi yuborildi** degani, virus skani tugadi degani emas. UAC va skan rejimini o‘zingiz tanlaysiz. JARVIS xavfsizlik oynasini avtomatik bosmaydi yoki himoyani o‘chirmaydi. `mrt_report` `%windir%/debug/mrt.log` mavjud jurnalini o‘qiydi; u eski bo‘lishi mumkin. MRT to‘liq antivirus o‘rnini bosmaydi. [Microsoft MRT izohi](https://support.microsoft.com/en-au/servicing/os/windows/2021/01/remove-specific-prevalent-malware-with-windows-malicious-software-removal-tool-kb890830).

## Tezlik, UI va chegaralar

Fayl indeksi SQLite’da lokal keshlanadi (60 soniya), ilovalar katalogi 120 soniya keshlanadi. Yangilash tugmasi qayta skan qiladi. Skan: 8 soniya yoki 50000 faylgacha; umumiy tahlil natijasi ko‘pincha 10000 faylgacha. Bu **butun diskda fayl yo‘q** degan xulosa emas. Fayl ko‘rinmasa torroq ish papkasini tanlang va indeksni yangilang. Matn qidiruvi 10 soniya/30 MB o‘qish bilan chegaralanadi. Alohida nusxa/hash fayli 100 MB, papka/arxiv ochilgan hajmi 300 MB/10000 yozuvgacha. Matn tahriri UTF-8’da 2 MB gacha. Hash SHA256; matn farqi jami 200000 belgigacha.

Og‘ir fayl amallari, indekslash, ilovalar katalogi va tizim metrikalari Tk’dan tashqari worker’da ishlaydi. Dekorativ Canvas elementlari qayta ishlatiladi; ranglar keshi va o‘zgarmagan chizmalarni qayta sozlamaslik Tk yukini kamaytiradi. 3D yadroning bloom/aylanishiga fon to‘ri, yulduzlar, HUD halqasi va sweep qo‘shilgan; oqimli neural ribbon, hover easing, pulsatsiya va scan chiziqlari ham bor. Bular haqiqiy tarmoq/mikrofon o‘lchovi emas. **FX / Ctrl+Shift+E** animatsiyalarni to‘xtatadi; yashirilgan oynaning dekorativ sikli dam oladi. CPU indikatori haqiqiy qisqa o‘lchovni ko‘rsatadi.

Bu 50 ta aniq, chegaralangan lokal vosita; boshqa AI’larda bo‘lmaydi yoki har qanday ishni xatosiz bajaradi degan da’vo emas.

## Tekshirish

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/check_computer_integration.py
python scripts/check_office_integration.py
python -m jarvis.ui.app
```

Integration sinovi vaqtinchalik fayllarda 50 forma, tasdiq, real tahrir/zaxiradan tiklash, kichik oynalar, 3D va FX boshqaruvini tekshiradi. Store/MRT/clipboard mutatsiyalari mock bilan tekshiriladi; haqiqiy o‘rnatish yoki virus skani ishga tushirilmaydi. Sinovga AI kaliti kerak emas.
