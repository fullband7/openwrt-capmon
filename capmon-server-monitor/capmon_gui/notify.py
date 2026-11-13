import json
import os

from .model import LOW_PERCENT, fmt_bytes, plan_label


def plan_level(plan):
    if not plan.enabled or plan.limit <= 0:
        return 0
    if plan.exceeded:
        return 2
    return 1 if 100.0 - plan.percent <= LOW_PERCENT else 0


class Notifier:
    def __init__(self, path):
        self.path = path
        self.state = self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {
            key: [str(value[0]), int(value[1])]
            for key, value in data.items()
            if isinstance(value, list) and len(value) == 2 and isinstance(value[1], int)
        }

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
            temporary = self.path + ".tmp"
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(self.state, handle)
            os.replace(temporary, self.path)
        except OSError:
            pass

    def check(self, snapshots):
        events = []
        seen = set()
        changed = False
        multiple = len(snapshots) > 1
        for router, snapshot in snapshots.items():
            for plan in snapshot.plans:
                key = router + "/" + plan.mac
                seen.add(key)
                level = plan_level(plan)
                old = self.state.get(key)
                before = old[1] if old and old[0] == plan.pkey else 0
                if old != [plan.pkey, level]:
                    self.state[key] = [plan.pkey, level]
                    changed = True
                if level > before:
                    events.append(self._message(router if multiple else "", snapshot, plan, level))
        for key in list(self.state):
            if key.split("/", 1)[0] in snapshots and key not in seen:
                del self.state[key]
                changed = True
        if changed:
            self._save()
        return events

    @staticmethod
    def _message(router, snapshot, plan, level):
        label = plan_label(snapshot, plan)
        prefix = "[%s] " % router if router else ""
        if level == 2:
            return (
                "Data plan used up",
                "%s%s has used all of its %s. Internet access is blocked."
                % (prefix, label, fmt_bytes(plan.limit)),
            )
        left = max(0, plan.limit - plan.used)
        return (
            "Data plan is running low",
            "%s%s has %d%% of its data left (%s of %s)."
            % (prefix, label, round(100.0 - plan.percent), fmt_bytes(left), fmt_bytes(plan.limit)),
        )
