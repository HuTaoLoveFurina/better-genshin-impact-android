"""配置加载：默认值 + YAML 覆盖。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields
from pathlib import Path

log = logging.getLogger(__name__)

# BetterGI 内置的优先选择关键词（包含即优先点击）
DEFAULT_SELECT_KEYWORDS: list[str] = [
    "进入秘境", "领取奖励", "接受", "确认", "继续", "好的",
]

# 默认不自动点击的选项（涉及消耗/不可逆操作），命中则暂停等待人工处理
DEFAULT_PAUSE_KEYWORDS: list[str] = [
    "退出秘境", "秘境退出", "结束秘境", "放弃", "离开", "结算",
    "购买", "消耗", "兑换", "商店", "传送",
]


@dataclass
class Config:
    # 连接
    serial: str | None = None
    wireless: str | None = None
    adb_path: str = "adb"
    local: bool = False             # True=在已 root 的安卓 shell 本地运行（无需 adb）
    package: str | None = None

    # 循环
    interval: float = 0.6            # 主循环间隔（秒）
    click_delay: float = 0.15        # 点击后等待（秒）

    # 剧情选项
    choose_option: bool = True
    option_mode: str = "first"       # first / second / last / random / none
    before_choose_delay: float = 0.0 # 点击选项前额外等待（秒），留出语音时间
    custom_priority: list[str] = field(default_factory=list)
    select_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_SELECT_KEYWORDS))
    pause_keywords: list[str] = field(default_factory=lambda: list(DEFAULT_PAUSE_KEYWORDS))
    prefer_orange: bool = False      # 橙色（关键剧情）选项优先；颜色检测在串流下易误判，默认关

    # 行为开关
    quick_skip: bool = True          # 快速点击推进对话
    click_black_screen: bool = True  # 黑屏演出期间点击
    auto_hangout_skip: bool = True   # 邀约自动点跳过
    close_popup: bool = True         # 关闭弹出页面
    click_continue: bool = True       # 枫丹主线等「点击任意处继续」提示自动推进

    # 阈值
    template_threshold: float = 0.80
    # 黑屏判定：只有接近全黑才视为「黑屏演出」并点击推进。
    # 注意云原神/原神暗色剧情界面背景也可能偏暗，阈值过低会误触，
    # 故默认要求画面 92% 以上为近黑色才算黑屏。
    black_ratio_min: float = 0.92
    black_ratio_max: float = 0.999
    orange_ratio: float = 0.06

    # 调试
    debug: bool = False
    debug_dir: str = "debug"

    @classmethod
    def load(cls, path: str | Path | None) -> "Config":
        cfg = cls()
        if not path:
            return cfg
        p = Path(path)
        if not p.exists():
            log.warning("配置文件不存在，使用默认配置: %s", p)
            return cfg

        import yaml

        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        valid = {f.name for f in fields(cls)}
        for k, v in data.items():
            if k in valid:
                setattr(cfg, k, v)
            else:
                log.warning("忽略未知配置项: %s", k)
        log.info("已加载配置: %s", p)
        return cfg

    @classmethod
    def _apply_env(cls, cfg: "Config") -> "Config":
        """环境变量覆盖：便于容器/CI 中无需改配置文件即可切换策略。"""
        env_mode = __import__("os").environ.get("BGIA_OPTION_MODE")
        if env_mode:
            valid = {"first", "second", "last", "random", "none"}
            if env_mode in valid:
                cfg.option_mode = env_mode
                log.info("环境变量 BGIA_OPTION_MODE=%s -> 生效", env_mode)
            else:
                log.warning("环境变量 BGIA_OPTION_MODE=%r 无效，忽略（可选: %s）",
                            env_mode, "/".join(sorted(valid)))

        env_choose = __import__("os").environ.get("BGIA_CHOOSE_OPTION")
        if env_choose is not None:
            cfg.choose_option = env_choose.strip().lower() in ("1", "true", "yes", "on")
            log.info("环境变量 BGIA_CHOOSE_OPTION=%s -> choose_option=%s",
                     env_choose, cfg.choose_option)
        return cfg
