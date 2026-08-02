"""多语言支持：游戏语言 → OCR 引擎语言 + 关键词表。

原神官方支持的语言分两组：
  亚洲：简体中文(zh-CN)、繁体中文(zh-TW)、日语(ja)、韩语(ko)、
        泰语(th)、印尼语(id)、越南语(vi)
  欧洲及其他：英语(en)、法语(fr)、德语(de)、俄语(ru)、
        西班牙语(es)、葡萄牙语(pt)、意大利语(it)、土耳其语(tr)

OCR 引擎(RapidOCR)的识别模型对应当前可用代码：
  ch / chinese_cht / japan / korean / en / latin / cyrillic
其中 latin 覆盖法/德/西/葡/意/土/印尼/越南；cyrillic 覆盖俄语。
泰语(th)在 RapidOCR 中无原生模型，退化为 latin（仅保留结构，识别不可靠），
会在引擎初始化时给出警告。
"""

from __future__ import annotations

# 游戏语言代码(原神客户端) → RapidOCR 识别模型代码
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
    "th": "latin",  # 退化：RapidOCR 无泰语模型，仅结构可用
}

# 原神客户端可选语言(供配置校验/提示)
SUPPORTED_GAME_LANGS: list[str] = list(GAME_LANG_TO_OCR.keys())

# 各语言的剧情关键词。每个语言提供：
#   continue_: 提示"点击继续 / 轻触任意处 / 跳过"等词组
#   playing:   剧情"播放中"标识词组
#   option:    选项界面相关词组(放弃/选择/确认/采纳 等)
#   pause:     暂停/退出剧情相关词组
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
    """返回 RapidOCR 识别模型代码；未知语言回退到 ch。"""
    return GAME_LANG_TO_OCR.get(game_lang, "ch")


def get_keywords(game_lang: str) -> dict[str, list[str]]:
    """返回对应语言的剧情关键词表；未知语言回退到 zh-CN。"""
    return KEYWORDS.get(game_lang, KEYWORDS["zh-CN"])


def is_thai_degraded(game_lang: str) -> bool:
    """泰语在 RapidOCR 无原生模型，返回 True 表示识别不可靠。"""
    return game_lang == "th"
