import json
from pathlib import Path
from threading import RLock
from typing import Optional

from .theme import (
    DEFAULT_CUSTOM_THEME_BACKGROUND_TYPE,
    DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DATA,
    DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DARKEN,
    DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_LAYOUT,
    DEFAULT_CUSTOM_THEME_BASE_COLOR,
    DEFAULT_CUSTOM_THEME_COLOR_DEPTH,
    DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_DIRECTION,
    DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_END_COLOR,
    DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_START_COLOR,
    DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_TYPE,
    DEFAULT_CUSTOM_THEME_FOREGROUND_BLUR,
    DEFAULT_CUSTOM_THEME_FOREGROUND_TRANSPARENCY,
    DEFAULT_CUSTOM_THEME_LINE_CONTRAST_COLOR,
    DEFAULT_CUSTOM_THEME_LINE_COLOR,
    DEFAULT_CUSTOM_THEME_LIVEMAP_LINK_COLOR,
    DEFAULT_CUSTOM_THEME_PARTICLES_COLOR,
    DEFAULT_CUSTOM_THEME_PARTICLES_COUNT,
    DEFAULT_CUSTOM_THEME_PARTICLES_ENABLED,
    DEFAULT_CUSTOM_THEME_PARTICLES_LINK_COLOR,
    DEFAULT_CUSTOM_THEME_PARTICLES_LINKS,
    DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS,
    DEFAULT_CUSTOM_THEME_PARTICLES_OPACITY,
    DEFAULT_CUSTOM_THEME_PARTICLES_SIZE,
    DEFAULT_CUSTOM_THEME_PARTICLES_SPEED,
    DEFAULT_CUSTOM_THEME_TEXT_FONT,
    DEFAULT_THEME_BASE_COLOR,
    DEFAULT_THEME_COLOR_DEPTH,
    DEFAULT_THEME_LINE_CONTRAST_COLOR,
    DEFAULT_THEME_LINE_COLOR,
    DEFAULT_THEME_TEXT_FONT,
    build_palette_theme_preset,
    normalize_theme_background_type,
    normalize_theme_background_image_data,
    normalize_theme_background_image_darken,
    normalize_theme_background_image_layout,
    normalize_theme_base_color,
    normalize_theme_color_depth,
    normalize_theme_foreground_blur,
    normalize_theme_foreground_transparency,
    normalize_theme_gradient_direction,
    normalize_theme_gradient_type,
    normalize_theme_line_contrast_color,
    normalize_theme_line_color,
    normalize_theme_particles_color,
    normalize_theme_particles_count,
    normalize_theme_particles_enabled,
    normalize_theme_livemap_layers,
    normalize_theme_particles_opacity,
    normalize_theme_particles_size,
    normalize_theme_particles_speed,
    normalize_theme_text_font,
)
from .theme_presets import (
    ThemePreset,
    ThemePresetMap,
    default_theme_preset_custom_settings,
    default_theme_presets,
    select_theme_preset,
)


def _default_custom_theme_settings() -> dict[str, object]:
    return {
        "base_color": DEFAULT_CUSTOM_THEME_BASE_COLOR,
        "line_color": DEFAULT_CUSTOM_THEME_LINE_COLOR,
        "line_contrast_color": DEFAULT_CUSTOM_THEME_LINE_CONTRAST_COLOR,
        "color_depth": DEFAULT_CUSTOM_THEME_COLOR_DEPTH,
        "text_font": DEFAULT_CUSTOM_THEME_TEXT_FONT,
        "gradient_primary_start_color": DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_START_COLOR,
        "gradient_primary_end_color": DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_END_COLOR,
        "gradient_primary_type": DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_TYPE,
        "gradient_primary_direction": DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_DIRECTION,
        "foreground_transparency": DEFAULT_CUSTOM_THEME_FOREGROUND_TRANSPARENCY,
        "foreground_blur": DEFAULT_CUSTOM_THEME_FOREGROUND_BLUR,
        "background_type": DEFAULT_CUSTOM_THEME_BACKGROUND_TYPE,
        "background_image_data": DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DATA,
        "background_image_layout": DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_LAYOUT,
        "background_image_darken": DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DARKEN,
        "particles_enabled": DEFAULT_CUSTOM_THEME_PARTICLES_ENABLED,
        "particles_color": DEFAULT_CUSTOM_THEME_PARTICLES_COLOR,
        "particles_link_color": DEFAULT_CUSTOM_THEME_PARTICLES_LINK_COLOR,
        "livemap_link_color": DEFAULT_CUSTOM_THEME_LIVEMAP_LINK_COLOR,
        "particles_count": DEFAULT_CUSTOM_THEME_PARTICLES_COUNT,
        "particles_speed": DEFAULT_CUSTOM_THEME_PARTICLES_SPEED,
        "particles_size": DEFAULT_CUSTOM_THEME_PARTICLES_SIZE,
        "particles_opacity": DEFAULT_CUSTOM_THEME_PARTICLES_OPACITY,
        "particles_links": DEFAULT_CUSTOM_THEME_PARTICLES_LINKS,
        "livemap_layers": dict(DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS),
    }


def _int_setting(value: object, default: int) -> int:
    try:
        return int(default if value is None else value)
    except (TypeError, ValueError):
        return int(default)


def _float_setting(value: object, default: float) -> float:
    try:
        return float(default if value is None else value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_custom_theme_settings(
    raw_settings: object,
    *,
    fallback: Optional[dict[str, object]] = None,
) -> dict[str, object]:
    base = fallback if isinstance(fallback, dict) else _default_custom_theme_settings()
    payload = raw_settings if isinstance(raw_settings, dict) else {}
    normalized_base_color = normalize_theme_base_color(
        payload.get("base_color"),
        fallback=str(base.get("base_color") or DEFAULT_THEME_BASE_COLOR),
    )
    raw_line_color = payload.get("line_color")
    raw_line_contrast_color = payload.get("line_contrast_color")
    normalized_line_color = normalize_theme_line_color(
        raw_line_color,
        fallback=(
            normalized_base_color
            if raw_line_color is None
            else str(base.get("line_color") or normalized_base_color or DEFAULT_THEME_LINE_COLOR)
        ),
    )
    normalized_line_contrast_color = normalize_theme_line_contrast_color(
        raw_line_contrast_color,
        fallback=str(base.get("line_contrast_color") or DEFAULT_THEME_LINE_CONTRAST_COLOR),
    )
    return {
        "base_color": normalized_base_color,
        "line_color": normalized_line_color,
        "line_contrast_color": normalized_line_contrast_color,
        "color_depth": normalize_theme_color_depth(
            payload.get("color_depth"),
            fallback=_int_setting(base.get("color_depth"), DEFAULT_THEME_COLOR_DEPTH),
        ),
        "text_font": normalize_theme_text_font(
            payload.get("text_font"),
            fallback=str(base.get("text_font") or DEFAULT_THEME_TEXT_FONT),
        ),
        "foreground_transparency": normalize_theme_foreground_transparency(
            payload.get("foreground_transparency"),
            fallback=_int_setting(base.get("foreground_transparency"), DEFAULT_CUSTOM_THEME_FOREGROUND_TRANSPARENCY),
        ),
        "foreground_blur": normalize_theme_foreground_blur(
            payload.get("foreground_blur"),
            fallback=_int_setting(base.get("foreground_blur"), DEFAULT_CUSTOM_THEME_FOREGROUND_BLUR),
        ),
        "gradient_primary_start_color": normalize_theme_base_color(
            payload.get("gradient_primary_start_color"),
            fallback=str(base.get("gradient_primary_start_color") or normalized_base_color),
        ),
        "gradient_primary_end_color": normalize_theme_base_color(
            payload.get("gradient_primary_end_color"),
            fallback=str(base.get("gradient_primary_end_color") or normalized_line_color),
        ),
        "gradient_primary_type": normalize_theme_gradient_type(
            payload.get("gradient_primary_type"),
            fallback=str(base.get("gradient_primary_type") or DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_TYPE),
        ),
        "gradient_primary_direction": normalize_theme_gradient_direction(
            payload.get("gradient_primary_direction"),
            fallback=str(base.get("gradient_primary_direction") or DEFAULT_CUSTOM_THEME_GRADIENT_PRIMARY_DIRECTION),
        ),
        "background_type": normalize_theme_background_type(
            payload.get("background_type"),
            fallback=str(base.get("background_type") or DEFAULT_CUSTOM_THEME_BACKGROUND_TYPE),
        ),
        "background_image_data": normalize_theme_background_image_data(
            payload.get("background_image_data"),
            fallback=str(base.get("background_image_data") or DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DATA),
        ),
        "background_image_layout": normalize_theme_background_image_layout(
            payload.get("background_image_layout"),
            fallback=str(base.get("background_image_layout") or DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_LAYOUT),
        ),
        "background_image_darken": normalize_theme_background_image_darken(
            payload.get("background_image_darken"),
            fallback=_int_setting(base.get("background_image_darken"), DEFAULT_CUSTOM_THEME_BACKGROUND_IMAGE_DARKEN),
        ),
        "particles_enabled": normalize_theme_particles_enabled(
            payload.get("particles_enabled"),
            fallback=bool(base.get("particles_enabled", DEFAULT_CUSTOM_THEME_PARTICLES_ENABLED)),
        ),
        "particles_color": normalize_theme_particles_color(
            payload.get("particles_color"),
            fallback=str(base.get("particles_color") or normalized_line_contrast_color),
        ),
        "particles_link_color": normalize_theme_particles_color(
            payload.get("particles_link_color"),
            fallback=str(base.get("particles_link_color") or normalized_line_contrast_color),
        ),
        "livemap_link_color": normalize_theme_particles_color(
            payload.get("livemap_link_color"),
            fallback=str(
                base.get("livemap_link_color")
                or payload.get("particles_link_color")
                or base.get("particles_link_color")
                or normalized_line_contrast_color
            ),
        ),
        "particles_count": normalize_theme_particles_count(
            payload.get("particles_count"),
            fallback=_int_setting(base.get("particles_count"), DEFAULT_CUSTOM_THEME_PARTICLES_COUNT),
        ),
        "particles_speed": normalize_theme_particles_speed(
            payload.get("particles_speed"),
            fallback=_float_setting(base.get("particles_speed"), DEFAULT_CUSTOM_THEME_PARTICLES_SPEED),
        ),
        "particles_size": normalize_theme_particles_size(
            payload.get("particles_size"),
            fallback=_int_setting(base.get("particles_size"), DEFAULT_CUSTOM_THEME_PARTICLES_SIZE),
        ),
        "particles_opacity": normalize_theme_particles_opacity(
            payload.get("particles_opacity"),
            fallback=_int_setting(base.get("particles_opacity"), DEFAULT_CUSTOM_THEME_PARTICLES_OPACITY),
        ),
        "particles_links": normalize_theme_particles_enabled(
            payload.get("particles_links"),
            fallback=bool(base.get("particles_links", DEFAULT_CUSTOM_THEME_PARTICLES_LINKS)),
        ),
        "livemap_layers": normalize_theme_livemap_layers(
            payload.get("livemap_layers"),
            fallback=base.get("livemap_layers", DEFAULT_CUSTOM_THEME_LIVEMAP_LAYERS),
        ),
    }


def _normalize_custom_presets_map(raw: object) -> dict[str, dict[str, object]]:
    normalized: dict[str, dict[str, object]] = {}
    if isinstance(raw, dict):
        for name, settings in raw.items():
            clean_name = str(name or "").strip()
            if not clean_name:
                continue
            normalized[clean_name] = _normalize_custom_theme_settings(settings)
    return normalized


def _load_persisted_theme_settings(settings_path: Optional[str]) -> dict[str, object]:
    payload = {
        "selected_preset": None,
        "custom_theme": _default_custom_theme_settings(),
        "custom_presets": {},
    }
    if not settings_path:
        return payload
    try:
        stored = json.loads(Path(settings_path).read_text(encoding="utf-8"))
    except Exception:
        return payload
    if not isinstance(stored, dict):
        return payload

    selected = stored.get("selected_preset")
    if selected is not None:
        clean = str(selected).strip()
        payload["selected_preset"] = clean or None
    payload["custom_theme"] = _normalize_custom_theme_settings(stored.get("custom_theme"))
    payload["custom_presets"] = _normalize_custom_presets_map(stored.get("custom_presets"))
    return payload


def _save_persisted_theme_settings(
    settings_path: Optional[str],
    *,
    selected_preset: str,
    custom_theme: dict[str, object],
    custom_presets: dict[str, dict[str, object]],
) -> Optional[str]:
    if not settings_path:
        return None
    path = Path(settings_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(
                {
                    "selected_preset": str(selected_preset),
                    "custom_theme": _normalize_custom_theme_settings(custom_theme),
                    "custom_presets": {
                        str(name): _normalize_custom_theme_settings(settings)
                        for name, settings in (custom_presets or {}).items()
                    },
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temp_path.replace(path)
    except Exception as exc:
        return str(exc)
    return None


class ThemePresetSettings:
    def __init__(
        self,
        *,
        presets: ThemePresetMap,
        selected_preset: Optional[str],
        settings_path: Optional[str],
    ) -> None:
        base_presets = dict(presets) if isinstance(presets, dict) else {}
        if "default" not in base_presets:
            base_presets.update(default_theme_presets())

        self._presets = base_presets
        self._settings_path = settings_path
        self._lock = RLock()
        self._custom_theme = _default_custom_theme_settings()
        self._custom_presets: dict[str, dict[str, object]] = {}
        default_presets = default_theme_presets()
        self._preset_custom_settings = {
            str(name): _normalize_custom_theme_settings(settings)
            for name, settings in default_theme_preset_custom_settings().items()
            if base_presets.get(str(name)) == default_presets.get(str(name))
        }

        persisted = _load_persisted_theme_settings(settings_path)
        self._custom_presets = dict(persisted.get("custom_presets") or {})
        initial = self._normalize_preset_name(selected_preset)
        persisted_selected = persisted.get("selected_preset")
        if persisted_selected:
            initial = self._normalize_preset_name(str(persisted_selected))
        self._custom_theme = _normalize_custom_theme_settings(persisted.get("custom_theme"))
        self._selected_preset = initial

    def _normalize_preset_name(self, preset_name: Optional[str]) -> str:
        clean = str(preset_name or "").strip()
        if clean == "custom":
            return "custom"
        if clean and (clean in self._presets or clean in self._custom_presets):
            return clean
        if clean == "blue" and "default" in self._presets:
            return "default"
        if not clean:
            if "default" in self._presets:
                return "default"
            return "custom"
        if "default" in self._presets:
            return "default"
        return next(iter(self._presets.keys()), "custom")

    def _is_reserved_preset_name(self, name: str) -> bool:
        return name == "custom" or name in self._presets

    def available_presets(self) -> list[str]:
        names = [str(name) for name in self.preset_catalog().keys() if str(name) != "default"]
        names.sort()
        return ["default", *names] if "default" in self._presets else names

    def _build_theme_preset_from_settings(self, custom_theme: dict[str, object]) -> ThemePreset:
        return build_palette_theme_preset(
            custom_theme.get("base_color"),
            line_color=custom_theme.get("line_color"),
            line_contrast_color=custom_theme.get("line_contrast_color"),
            color_depth=_int_setting(custom_theme.get("color_depth"), DEFAULT_THEME_COLOR_DEPTH),
            text_font=custom_theme.get("text_font"),
            gradient_primary_start_color=custom_theme.get("gradient_primary_start_color"),
            gradient_primary_end_color=custom_theme.get("gradient_primary_end_color"),
            gradient_primary_type=custom_theme.get("gradient_primary_type"),
            gradient_primary_direction=custom_theme.get("gradient_primary_direction"),
            foreground_transparency=_int_setting(
                custom_theme.get("foreground_transparency"),
                DEFAULT_CUSTOM_THEME_FOREGROUND_TRANSPARENCY,
            ),
            foreground_blur=_int_setting(
                custom_theme.get("foreground_blur"),
                DEFAULT_CUSTOM_THEME_FOREGROUND_BLUR,
            ),
        )

    def _preset_catalog_for_custom_theme(
        self,
        custom_theme: dict[str, object],
        custom_presets: Optional[dict[str, dict[str, object]]] = None,
    ) -> ThemePresetMap:
        saved_presets = self._custom_presets if custom_presets is None else custom_presets
        catalog = {name: preset for name, preset in self._presets.items()}
        for name, settings in saved_presets.items():
            catalog[str(name)] = self._build_theme_preset_from_settings(settings)
        catalog["custom"] = self._build_theme_preset_from_settings(custom_theme)
        return catalog

    def _available_preset_names_for_catalog(self, catalog: ThemePresetMap) -> list[str]:
        names = [str(name) for name in catalog.keys() if str(name) != "default"]
        names.sort()
        return ["default", *names] if "default" in self._presets else names

    def _build_settings_payload(
        self,
        *,
        selected_preset: str,
        custom_theme: dict[str, object],
        custom_presets: Optional[dict[str, dict[str, object]]] = None,
    ) -> dict[str, object]:
        saved_presets = self._custom_presets if custom_presets is None else custom_presets
        catalog = self._preset_catalog_for_custom_theme(custom_theme, saved_presets)
        preset_custom_settings = dict(self._preset_custom_settings)
        preset_custom_settings.update(saved_presets)
        return {
            "ok": True,
            "selected_preset": selected_preset,
            "available_presets": self._available_preset_names_for_catalog(catalog),
            "presets": catalog,
            "preset_custom_settings": {
                name: dict(settings)
                for name, settings in preset_custom_settings.items()
                if name in catalog
            },
            "custom_theme": dict(custom_theme),
            "custom_preset_names": sorted(str(name) for name in saved_presets.keys()),
        }

    def selected_preset_name(self) -> str:
        with self._lock:
            return self._selected_preset

    def selected_preset_tokens(self) -> ThemePreset:
        with self._lock:
            selected = self._selected_preset
            custom_theme = dict(self._custom_theme)
            custom_presets = dict(self._custom_presets)
        if selected == "custom":
            return self._build_theme_preset_from_settings(custom_theme)
        if selected in custom_presets:
            return self._build_theme_preset_from_settings(custom_presets[selected])
        return select_theme_preset(self._presets, selected)

    def preset_catalog(self) -> ThemePresetMap:
        with self._lock:
            custom_theme = dict(self._custom_theme)
            custom_presets = dict(self._custom_presets)
        return self._preset_catalog_for_custom_theme(custom_theme, custom_presets)

    def custom_theme_settings(self) -> dict[str, object]:
        with self._lock:
            return dict(self._custom_theme)

    def get_settings_payload(self) -> dict[str, object]:
        with self._lock:
            selected = self._selected_preset
            custom_theme = dict(self._custom_theme)
            custom_presets = dict(self._custom_presets)
        return self._build_settings_payload(
            selected_preset=selected,
            custom_theme=custom_theme,
            custom_presets=custom_presets,
        )

    def set_selected_preset(self, preset_name: object) -> dict[str, object]:
        return self.apply_settings({"preset_name": preset_name})

    def _persist_locked(self) -> Optional[str]:
        return _save_persisted_theme_settings(
            self._settings_path,
            selected_preset=self._selected_preset,
            custom_theme=self._custom_theme,
            custom_presets=self._custom_presets,
        )

    def _payload_locked(self) -> dict[str, object]:
        return self._build_settings_payload(
            selected_preset=self._selected_preset,
            custom_theme=dict(self._custom_theme),
            custom_presets=dict(self._custom_presets),
        )

    def _save_named_preset(self, name: Optional[str], raw_custom_theme: object) -> dict[str, object]:
        clean = str(name or "").strip()
        with self._lock:
            if not clean:
                payload = self._payload_locked()
                payload["ok"] = False
                payload["error"] = "Theme name is required"
                return payload
            if self._is_reserved_preset_name(clean):
                payload = self._payload_locked()
                payload["ok"] = False
                payload["error"] = f'"{clean}" is a reserved theme name'
                return payload

            next_custom_theme = _normalize_custom_theme_settings(
                raw_custom_theme,
                fallback=self._custom_theme,
            )
            self._custom_presets[clean] = next_custom_theme
            self._custom_theme = next_custom_theme
            self._selected_preset = clean
            persist_error = self._persist_locked()
            payload = self._payload_locked()

        if persist_error:
            payload["persist_error"] = persist_error
        return payload

    def _rename_named_preset(self, old_name: Optional[str], new_name: Optional[str]) -> dict[str, object]:
        clean_old = str(old_name or "").strip()
        clean_new = str(new_name or "").strip()
        with self._lock:
            error = None
            if not clean_old or clean_old not in self._custom_presets:
                error = f"Unknown saved theme: {clean_old}" if clean_old else "Theme name is required"
            elif not clean_new:
                error = "New theme name is required"
            elif clean_new != clean_old and (
                self._is_reserved_preset_name(clean_new) or clean_new in self._custom_presets
            ):
                error = f'A theme named "{clean_new}" already exists'

            if error:
                payload = self._payload_locked()
                payload["ok"] = False
                payload["error"] = error
                return payload

            settings = self._custom_presets.pop(clean_old)
            self._custom_presets[clean_new] = settings
            if self._selected_preset == clean_old:
                self._selected_preset = clean_new
            persist_error = self._persist_locked()
            payload = self._payload_locked()

        if persist_error:
            payload["persist_error"] = persist_error
        return payload

    def _delete_named_preset(self, name: Optional[str]) -> dict[str, object]:
        clean = str(name or "").strip()
        with self._lock:
            if not clean or clean not in self._custom_presets:
                payload = self._payload_locked()
                payload["ok"] = False
                payload["error"] = f"Unknown saved theme: {clean}" if clean else "Theme name is required"
                return payload

            del self._custom_presets[clean]
            if self._selected_preset == clean:
                if "default" in self._presets:
                    self._selected_preset = "default"
                else:
                    self._selected_preset = next(iter(self._presets.keys()), "custom")
            persist_error = self._persist_locked()
            payload = self._payload_locked()

        if persist_error:
            payload["persist_error"] = persist_error
        return payload

    def apply_settings(self, request: object) -> dict[str, object]:
        payload_obj = request if isinstance(request, dict) else {}
        raw_preset = None
        raw_custom_theme = payload_obj.get("custom_theme") if payload_obj else getattr(request, "custom_theme", None)
        preview_only = bool(payload_obj.get("preview_only")) if payload_obj else bool(
            getattr(request, "preview_only", False)
        )
        if payload_obj:
            raw_preset = payload_obj.get("preset_name")
            raw_action = payload_obj.get("action")
            raw_new_label = payload_obj.get("new_preset_label")
        else:
            raw_preset = getattr(request, "preset_name", None)
            raw_action = getattr(request, "action", None)
            raw_new_label = getattr(request, "new_preset_label", None)

        action = str(raw_action or "select").strip().lower() or "select"
        if action not in {"select", "save", "rename", "delete"}:
            action = "select"

        clean = None if raw_preset is None else str(raw_preset or "").strip()

        if action == "save":
            return self._save_named_preset(clean, raw_custom_theme)
        if action == "rename":
            new_label = None if raw_new_label is None else str(raw_new_label or "").strip()
            return self._rename_named_preset(clean, new_label)
        if action == "delete":
            return self._delete_named_preset(clean)

        if clean == "":
            payload = self.get_settings_payload()
            payload["ok"] = False
            payload["error"] = "Theme preset name is required"
            return payload

        with self._lock:
            next_custom_theme = _normalize_custom_theme_settings(
                raw_custom_theme,
                fallback=self._custom_theme,
            )
            selected = self._selected_preset
            if clean is not None:
                available = set(
                    self._preset_catalog_for_custom_theme(next_custom_theme, self._custom_presets).keys()
                )
                if clean == "blue" and clean not in available and "default" in available:
                    clean = "default"
                if clean not in available:
                    payload = self._payload_locked()
                    payload["ok"] = False
                    payload["error"] = f"Unknown theme preset: {clean}"
                    return payload
                selected = clean
            if preview_only:
                persist_error = None
                payload = self._build_settings_payload(
                    selected_preset=selected,
                    custom_theme=next_custom_theme,
                    custom_presets=self._custom_presets,
                )
            else:
                self._selected_preset = selected
                self._custom_theme = next_custom_theme
                persist_error = self._persist_locked()
                payload = self._payload_locked()

        if persist_error:
            payload["persist_error"] = persist_error
        return payload
