from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    key: str
    title: str
    group: str
    schema: str
    approval: bool = False

    @property
    def fields(self):
        return tuple(field.strip("?") for field in self.schema.split(",") if field)

    @property
    def required(self):
        return tuple(field for field in self.schema.split(",") if field and not field.endswith("?"))


_ROWS = [
    ("file_find", "Faylni nomi bilan tez qidirish", "Fayllar", "query,root?,limit?"),
    ("text_search", "Fayllar ichidagi matnni qidirish", "Fayllar", "query,root?,limit?"),
    ("file_info", "Fayl metama'lumotlarini ko'rish", "Fayllar", "path"),
    ("folder_list", "Papka tarkibini ko'rish", "Papkalar", "path"),
    ("text_read", "Matnli faylni o'qish", "Fayllar", "path"),
    ("text_create", "Yangi matnli fayl yaratish", "Fayllar", "path,text", True),
    ("text_append", "Zaxira bilan matn qo'shish", "Fayllar", "path,text", True),
    ("text_replace", "Aniq matnni zaxira bilan almashtirish", "Fayllar", "path,old,new", True),
    ("file_rename", "Fayl nomini o'zgartirish", "Fayllar", "path,name", True),
    ("file_move", "Faylni boshqa papkaga ko'chirish", "Fayllar", "path,destination", True),
    ("file_copy", "Fayldan nusxa olish", "Fayllar", "path,destination", True),
    ("folder_create", "Yangi papka yaratish", "Papkalar", "path", True),
    ("folder_copy", "Papkadan chegaralangan nusxa olish", "Papkalar", "path,destination", True),
    ("folder_rename", "Papka nomini o'zgartirish", "Papkalar", "path,name", True),
    ("folder_move", "Papkani ko'chirish", "Papkalar", "path,destination", True),
    ("file_recycle", "Faylni Recycle Bin'ga yuborish", "Fayllar", "path", True),
    ("file_checksum", "SHA256 nazorat summasi", "Fayllar", "path"),
    ("text_diff", "Ikki matnli fayl farqi", "Fayllar", "path,other"),
    ("file_compare", "Ikki fayl bir xilligini tekshirish", "Fayllar", "path,other"),
    ("duplicates", "Bir xil fayllarni hash bilan topish", "Tahlil", "root?"),
    ("largest_files", "Eng katta fayllar", "Tahlil", "root?,limit?"),
    ("recent_files", "Yaqinda o'zgargan fayllar", "Tahlil", "root?,limit?"),
    ("folder_stats", "Papka hajmi va fayl soni", "Tahlil", "path"),
    ("zip_create", "Yangi ZIP arxiv yaratish", "Arxiv", "path,destination", True),
    ("zip_inspect", "ZIP tarkibini ochmasdan ko'rish", "Arxiv", "path"),
    ("zip_extract", "ZIP'ni xavfsiz yangi papkaga ochish", "Arxiv", "path,destination", True),
    ("folder_snapshot", "Papka holatidan ZIP zaxira", "Zaxira", "path", True),
    ("backup_list", "Tahrir va ko'chirish tarixini ko'rish", "Zaxira", ""),
    ("backup_restore", "O'zgarmagan oxirgi holatni qaytarish", "Zaxira", "id", True),
    ("organize_preview", "Tur bo'yicha saralash rejasi", "Papkalar", "path"),
    ("organize_apply", "Tekshirilgan saralash rejasini bajarish", "Papkalar", "id", True),
    ("inventory_export", "Fayl inventarini CSV'ga eksport", "Tahlil", "root?"),
    ("folder_tree", "Papka daraxtini ko'rsatish", "Papkalar", "path"),
    ("file_open", "Hujjatni mos ilovada ochish", "Fayllar", "path"),
    ("file_reveal", "Faylni Explorer'da ko'rsatish", "Fayllar", "path"),
    ("app_find", "O'rnatilgan ilovani topish", "Ilovalar", "name"),
    ("app_open", "O'rnatilgan ilovani ochish", "Ilovalar", "name", True),
    ("store_search", "Microsoft Store'da ilova qidirish", "Ilovalar", "name"),
    ("app_inventory", "O'rnatilgan ilovalar katalogi", "Ilovalar", ""),
    ("app_shortcut", "Topilgan ilovaga Desktop yorlig'i", "Ilovalar", "name", True),
    ("mrt_open", "MRT tekshiruv oynasini ochish", "Xavfsizlik", "", True),
    ("mrt_report", "MRT mavjud jurnalini o'qish", "Xavfsizlik", ""),
    ("security_status", "Defender holatini faqat o'qish", "Xavfsizlik", ""),
    ("system_info", "Windows va qurilma ma'lumoti", "Tizim", ""),
    ("disk_info", "Disk bo'sh joylari", "Tizim", ""),
    ("process_list", "Jarayonlar va RAM sarfi", "Tizim", ""),
    ("battery_info", "Batareya va quvvat holati", "Tizim", ""),
    ("network_info", "Lokal tarmoq interfeyslari", "Tizim", ""),
    ("clipboard_format", "Clipboard matnini tozalash/saralash", "Clipboard", "mode", True),
    ("clipboard_copy_path", "Fayl yo'lini clipboardga olish", "Clipboard", "path", True),
]
SKILLS = {row[0]: Skill(*row) for row in _ROWS}
assert len(SKILLS) == 50


def validate_action(data):
    if not isinstance(data, dict) or set(data)-{"skill", "args"}:
        raise ValueError("computer_action uchun skill va args kerak.")
    key = data.get("skill")
    if not isinstance(key, str) or key not in SKILLS:
        raise ValueError("Noma'lum kompyuter qobiliyati.")
    skill = SKILLS[key]
    args = data.get("args", {})
    if not isinstance(args, dict) or set(args)-set(skill.fields):
        raise ValueError("Qobiliyat parametrlari noto'g'ri: " + skill.schema)
    if any(not isinstance(value, str) or len(value) > 1_000_000 or "\x00" in value for value in args.values()):
        raise ValueError("Parametrlar chegaralangan oddiy matn bo'lsin.")
    if any(field not in args or (not args[field].strip() and field not in {"text", "new"}) for field in skill.required):
        raise ValueError("Majburiy parametrlar: " + ", ".join(skill.required))
    if args.get('limit') and (not args['limit'].isascii() or not args['limit'].isdigit() or not 1 <= int(args['limit']) <= 100):
        raise ValueError('limit 1 dan 100 gacha butun son bo‘lsin.')
    return skill, dict(args)


def router_catalog():
    return "\n".join(f"{skill.key}({skill.schema}) — {skill.title}" for skill in SKILLS.values())
