from __future__ import annotations

import json

from .catalog import validate_action
from .files import FileEngine
from .platform import applications

PLATFORM_SKILLS = frozenset({'app_find', 'app_inventory', 'app_open', 'app_shortcut', 'store_search',
    'mrt_open', 'mrt_report', 'security_status', 'system_info', 'disk_info', 'process_list',
    'battery_info', 'network_info', 'clipboard_format'})


class ComputerService:
    def __init__(self, *, roots=None, storage=None, platform=None):
        self.files = FileEngine(roots=roots, **({'storage': storage} if storage else {}))
        self.platform = platform or applications

    def run(self, data, *, approved=False):
        skill, args = validate_action(data)
        if skill.approval and not approved:
            raise PermissionError('Bu amal Tasks panelida tasdiqlanishi kerak: '+skill.title)
        result = self.platform.execute(skill.key, args) if skill.key in PLATFORM_SKILLS else self.files.execute(skill.key, args)
        result = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=2)
        return result if len(result) <= 24000 else result[:24000]+'\n… Natija uzunligi chegaralandi.'
