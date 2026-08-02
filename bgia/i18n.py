"""Internationalization support: game-language codes -> OCR engine language + keyword tables.

Genshin Impact's officially supported languages fall into two groups:
  Asia: Simplified Chinese (zh-CN), Traditional Chinese (zh-TW), Japanese (ja), Korean (ko),
        Thai (th), Indonesian (id), Vietnamese (vi)
  Europe & others: English (en), French (fr), German (de), Russian (ru),
        Spanish (es), Portuguese (pt), Italian (it), Turkish (tr)

The OCR engine (RapidOCR) uses these model codes:
  ch / chinese_cht / japan / korean / en / latin / cyrillic
where latin covers fr/de/es/pt/it/tr/id/vi and cyrillic covers ru.
Thai (th) has no native RapidOCR model and is degraded to latin (structure kept but recognition
unreliable); a warning is emitted when the engine initializes.
"""

from __future__ import annotations

# Game-language code (Genshin client) -> RapidOCR recognition model code
GAME_LANG_TO_OCR: dict[str, str] = {
    "zh-CN": "ch",
    "zh-TW": "chinese_cht",
    "ja": "japan",
    "ko": "korean",
    "en": "en",
    "fr": "latin",
    "de": "latin",
    "ru": "cyrillic",
    "es": "latin",
    "pt": "latin",
    "it": "latin",
    "tr": "latin",
    "id": "latin",
    "vi": "latin",
    "th": "latin",  # degraded: RapidOCR has no Thai model; structure only
}

# Selectable Genshin client languages (used for config validation/hints)
SUPPORTED_GAME_LANGS: list[str] = list(GAME_LANG_TO_OCR.keys())

# Story keywords per language. Each language provides:
#   continue_: phrases like "tap to continue / tap anywhere / skip"
#   playing:   the "now playing" story indicator phrases
#   option:    dialogue-option phrases (give up / choose / confirm / accept ...)
#   pause:     pause/exit-story phrases
KEYWORDS: dict[str, dict[str, list[str]]] = {
    "zh-CN": {
        "continue_": ["继续", "点击", "任意处", "轻触", "触摸", "跳过", "点击空白处"],
        "playing": ["播放中"],
        "option": ["放弃", "选择", "确认", "采纳", "接受", "决定", "前往"],
        "pause": ["退出", "结束", "暂停", "停止"],
    },
    "zh-TW": {
        "continue_": ["繼續", "點擊", "任意處", "輕觸", "觸摸", "跳過", "點擊空白處"],
        "playing": ["播放中"],
        "option": ["放棄", "選擇", "確認", "採納", "接受", "決定", "前往"],
        "pause": ["退出", "結束", "暫停", "停止"],
    },
    "ja": {
        "continue_": ["続き", "タップ", "次へ", "スキップ", "どこか", "タッチ"],
        "playing": ["再生中"],
        "option": ["放棄", "選択", "確認", "採用", "受け入れ", "決定", "移動"],
        "pause": ["終了", "一時停止", "停止"],
    },
    "ko": {
        "continue_": ["계속", "탭", "다음", "스킵", "어디든", "터치"],
        "playing": ["재생 중", "재생중"],
        "option": ["포기", "선택", "확인", "수락", "결정", "이동"],
        "pause": ["종료", "일시정지", "정지"],
    },
    "en": {
        "continue_": ["continue", "tap", "skip", "anywhere", "touch", "next"],
        "playing": ["playing"],
        "option": ["abandon", "select", "confirm", "accept", "decide", "choose", "go to"],
        "pause": ["exit", "end", "pause", "stop"],
    },
    "fr": {
        "continue_": ["continuer", "appuyer", "passer", "partout", "touche", "suivant"],
        "playing": ["lecture"],
        "option": ["abandonner", "sélectionner", "confirmer", "accepter", "décider", "choisir"],
        "pause": ["quitter", "fin", "pause", "arrêter"],
    },
    "de": {
        "continue_": ["weiter", "tippen", "überspringen", "überall", "berühren", "nächste"],
        "playing": ["wiedergabe"],
        "option": ["ablehnen", "auswählen", "bestätigen", "annehmen", "entscheiden", "wählen"],
        "pause": ["beenden", "ende", "pause", "stoppen"],
    },
    "ru": {
        "continue_": ["продолжить", "нажмите", "пропустить", "где", "коснитесь", "далее"],
        "playing": ["воспроизведение"],
        "option": ["отказаться", "выбрать", "подтвердить", "принять", "решить"],
        "pause": ["выход", "завершить", "пауза", "стоп"],
    },
    "es": {
        "continue_": ["continuar", "tocar", "saltar", "en cualquier", "toca", "siguiente"],
        "playing": ["reproduciendo"],
        "option": ["abandonar", "seleccionar", "confirmar", "aceptar", "decidir", "elegir"],
        "pause": ["salir", "fin", "pausa", "detener"],
    },
    "pt": {
        "continue_": ["continuar", "toque", "pular", "em qualquer", "tocar", "próximo"],
        "playing": ["reproduzindo"],
        "option": ["abandonar", "selecionar", "confirmar", "aceitar", "decidir", "escolher"],
        "pause": ["sair", "fim", "pausa", "parar"],
    },
    "it": {
        "continue_": ["continua", "tocca", "salta", "ovunque", "tocco", "avanti"],
        "playing": ["riproduzione"],
        "option": ["abbandonare", "selezionare", "confermare", "accettare", "decidere", "scegliere"],
        "pause": ["esci", "fine", "pausa", "ferma"],
    },
    "tr": {
        "continue_": ["devam", "dokun", "geç", "herhangi", "dokunma", "ileri"],
        "playing": ["oynatılıyor"],
        "option": ["vazgeç", "seç", "onayla", "kabul", "karar", "git"],
        "pause": ["çık", "bitir", "duraklat", "durdur"],
    },
    "id": {
        "continue_": ["lanjut", "ketuk", "lewati", "di mana saja", "sentuh", "berikutnya"],
        "playing": ["memutar"],
        "option": ["tinggalkan", "pilih", "konfirmasi", "terima", "putuskan", "pergi"],
        "pause": ["keluar", "akhiri", "jeda", "berhenti"],
    },
    "vi": {
        "continue_": ["tiếp tục", "chạm", "bỏ qua", "bất kỳ", "chạm vào", "tiếp"],
        "playing": ["đang phát"],
        "option": ["từ bỏ", "chọn", "xác nhận", "chấp nhận", "quyết định", "đi đến"],
        "pause": ["thoát", "kết thúc", "tạm dừng", "dừng"],
    },
    "th": {
        "continue_": ["ดำเนินการต่อ", "แตะ", "ข้าม", "ที่ใดก็ได้", "สัมผัส", "ถัดไป"],
        "playing": ["กำลังเล่น"],
        "option": ["ยอม放弃", "เลือก", "ยืนยัน", "ยอมรับ", "ตัดสินใจ", "ไปที่"],
        "pause": ["ออก", "สิ้นสุด", "หยุดชั่วคราว", "หยุด"],
    },
}


def get_ocr_lang(game_lang: str) -> str:
    """Return the RapidOCR recognition model code; fall back to ch for unknown languages."""
    return GAME_LANG_TO_OCR.get(game_lang, "ch")


def get_keywords(game_lang: str) -> dict[str, list[str]]:
    """Return the story-keyword table for the given language; fall back to zh-CN for unknown languages."""
    return KEYWORDS.get(game_lang, KEYWORDS["zh-CN"])


def is_thai_degraded(game_lang: str) -> bool:
    """Thai has no native RapidOCR model; returning True means recognition is unreliable."""
    return game_lang == "th"
