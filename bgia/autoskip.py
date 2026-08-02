"""Auto story-skip task, ported from BetterGI's AutoSkipTrigger.

Per-frame decision chain:
  1. Date/invitation screen -> click the skip button
  2. Dialogue options       -> prefer the exclamation mark, otherwise decide via bubble OCR then click
  3. Playing/cutscene       -> rapid tapping to advance
  4. Black-screen cinematic  -> timed tapping
  5. Pop-up pages           -> click close
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from .adb import AdbDevice
from .config import Config
from .game import GameWindow, resolve_window
from .i18n import get_keywords
from .vision import (
    Match,
    OcrEngine,
    black_ratio,
    frame_diff_ratio,
    is_orange_option,
    match_template,
    match_template_multi,
)

log = logging.getLogger(__name__)

# Grace period (seconds) after the playing indicator disappears before we treat playback as stopped; kept in line with BetterGI.
PLAYING_FLAG_GRACE = 10.0


class AutoSkipTask:
    def __init__(self, device: AdbDevice, config: Config):
        self.device = device
        self.config = config
        self.ocr = OcrEngine(lang=config.lang)
        # Load the story keywords for the configured language (continue / playing / option / pause).
        self._kw = get_keywords(config.lang)
        self.window: GameWindow | None = None

        self._last_playing_at = 0.0
        self._last_black_click = 0.0
        self._last_option_click = 0.0
        self._last_frame: np.ndarray | None = None
        self._paused_reason: str | None = None
        self._frame_index = 0

    # ------------------------------------------------------------- utilities

    def _scale(self) -> float:
        assert self.window is not None
        return self.window.scale

    def _tap_in_window(self, x: float, y: float) -> None:
        """Tap a coordinate inside the render region (auto-converted to physical screen coordinates)."""
        assert self.window is not None
        sx, sy = self.window.to_screen(x, y)
        self.device.tap(sx, sy)
        time.sleep(self.config.click_delay)

    def _tap_match(self, m: Match, offset_x: int = 0, offset_y: int = 0) -> None:
        cx, cy = m.center
        self._tap_in_window(cx + offset_x, cy + offset_y)

    def _find(self, frame, name, threshold=None, roi=None):
        return match_template(
            frame, name, self._scale(),
            threshold if threshold is not None else self.config.template_threshold,
            roi,
        )

    def _dump_debug(self, frame: np.ndarray, tag: str) -> None:
        if not self.config.debug:
            return
        d = Path(self.config.debug_dir)
        d.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%H%M%S_%f")[:-3]
        cv2.imwrite(str(d / f"{ts}_{tag}.png"), frame)

    # ------------------------------------------------------------- state detection

    def _is_playing(self, frame: np.ndarray) -> bool:
        """Detect the auto-play marker at the top-left (stop_auto button / "playing" text)."""
        h, w = frame.shape[:2]
        roi = (0, 0, w // 5, h // 8)

        if self._find(frame, "stop_auto.png", roi=roi):
            return True

        # OCR fallback: look for "auto-playing / playing" text in the top-left corner.
        s = self._scale()
        tx, ty = int(60 * s), int(25 * s)
        tw, th = int(180 * s), int(50 * s)
        crop = frame[ty : ty + th, tx : tx + tw]
        playing_words = self._kw.get("playing", [])
        for r in self.ocr.recognize(crop):
            txt = r.text
            if not txt:
                continue
            # Hitting any "playing"-class keyword marks the playback state.
            if any(w and w in txt for w in playing_words):
                return True
        return False

    # ------------------------------------------------------------- hangout

    def _handle_hangout(self, frame: np.ndarray) -> bool:
        if not self.config.auto_hangout_skip:
            return False
        h, w = frame.shape[:2]
        skip = self._find(frame, "hangout_skip.png", roi=(0, 0, w // 5, h // 8))
        if skip:
            log.info("hangout skip button -> tap")
            self._tap_match(skip)
            return True
        return False

    # ------------------------------------------------------------- options

    def _option_roi(self, frame: np.ndarray) -> tuple[int, int, int, int]:
        """Option search region covering most of the lower-middle of the screen.

        The region spans the full width (left case-book / investigation panel + right dialogue bubbles).
        An earlier version only scanned the right half and missed left-side multi-option list UIs such as
        the Fontaine case-book; the full-width lower-middle region supports both layouts.
        """
        h, w = frame.shape[:2]
        # Margins on every side avoid UI decorations (left/right) and the top title bar / bottom buttons.
        return (int(w * 0.08), int(h * 0.12), int(w * 0.84), int(h * 0.82))

    def _handle_options(self, frame: np.ndarray) -> bool:
        if not self.config.choose_option or self.config.option_mode == "none":
            return False

        roi = self._option_roi(frame)

        # Exclamation mark = a mission-critical option; always take it first.
        excl = self._find(frame, "icon_exclamation.png", roi=roi)
        if excl:
            log.info("exclamation option found -> tap")
            self._tap_match(excl, offset_x=int(120 * self._scale()))
            self._last_option_click = time.time()
            return True

        # --- OCR-first strategy ---
        # Always OCR the option ROI and cluster results by y to extract candidate options.
        # Icon template matching is now only an auxiliary signal (logging / confidence weighting),
        # not a hard gate.
        texts = self._read_options(frame, roi)

        # Use the icon match count to gauge whether we are really on an option screen
        # (>=1 icon hit makes it more trustworthy).
        bubbles = match_template_multi(
            frame, "icon_option.png", self._scale(), self.config.template_threshold, roi
        )
        icon_count = len(bubbles)
        if icon_count > 0:
            log.debug("option-icon match count: %d", icon_count)

        if not texts:
            # No OCR text but icons present -> fall back to tapping by icon position.
            if icon_count > 0:
                bubbles.sort(key=lambda m: m.y)
                target = bubbles[0] if self.config.option_mode != "last" else bubbles[-1]
                log.info("option text unreadable (%d icons) -> tap item #%d by position", icon_count, bubbles.index(target) + 1)
                self._tap_match(target, offset_x=int(80 * self._scale()))
                self._last_option_click = time.time()
                return True

            # --- Fallback: special option UIs (gear / case-book) without a standard icon ---
            # When OCR is unavailable and no icon matches, try clicking a dark rounded bubble in the
            # lower-middle area (the typical option-background feature) to advance.
            if self._guess_option_bubble(frame):
                return True

            return False

        choice = self._decide_option(texts)
        if choice is None:
            return False

        if self.config.before_choose_delay > 0:
            time.sleep(self.config.before_choose_delay)

        idx, m = choice
        log.info("selected option [%d]: %s", idx + 1, m.text or "(no text)")
        self._tap_in_window(m.center[0], m.center[1])
        self._last_option_click = time.time()
        return True

    def _read_options(self, frame: np.ndarray, roi: tuple[int, int, int, int]) -> list[Match]:
        """Run OCR on the whole option ROI, cluster into multiple options by y, and return text-bearing clickable regions.

Filtering strategy:
          - NPC dialogue text usually sits in the bottom third of the ROI, starts at x=0, and is long
          - option text usually sits in the upper-middle of the ROI, to the right (right of the bubble icon), and is moderate in length
        """
        x0, y0, w, h = roi
        crop = frame[y0 : y0 + h, x0 : x0 + w]
        if crop.size == 0:
            return []

        # Upscale 3x to improve recognition of small / clipped option text (the default 2x still
        # misses small fonts).
        results = self.ocr.recognize(crop, upscale=3)
        if not results:
            return []

        # Cluster text blocks by their center-y: blocks within `line_gap` belong to the same option.
        items = []
        for r in results:
            cx = float(r.x + r.width / 2) + x0
            cy = float(r.y + r.height / 2) + y0
            items.append((cx, cy, r.text, r.score, r.x, r.y, r.width, r.height))

        items.sort(key=lambda t: t[1])
        groups: list[list] = []
        line_gap = int(40 * self._scale())
        for cx, cy, text, score, rx, ry, rw, rh in items:
            if groups and cy - groups[-1][-1][1] <= line_gap:
                groups[-1].append((cx, cy, text, score, rx, ry, rw, rh))
            else:
                groups.append([(cx, cy, text, score, rx, ry, rw, rh)])

        out: list[Match] = []
        # NPC-dialogue filtering thresholds:
        #   - bottom 25% of the ROI AND x hugging the left edge (< 8% of ROI width) -> bottom NPC
        #     dialogue / name
        #   - left-side option lists (e.g. case-book) are also left-aligned but sit in the upper-middle
        #     and do not hug the very left edge
        npc_y_threshold = y0 + h * 0.75
        npc_x_threshold = w * 0.08

        for g in groups:
            xs = [t[0] for t in g]
            ys = [t[1] for t in g]
            texts_ = " ".join(t[2] for t in g).strip()
            if not texts_:
                continue
            gx = min(t[4] for t in g)  # leftmost x in the group (relative to crop)
            gy = min(t[5] for t in g)  # topmost y in the group (relative to crop)

            # --- NPC dialogue / name filter ---
            avg_cy = sum(ys) / len(ys)
            abs_gy = gy + y0  # absolute y (relative to frame)
            is_npc_like = (
                abs_gy > npc_y_threshold   # in the bottom region
                and gx < npc_x_threshold    # left-aligned (NPC names/dialogue start at the left)
                and len(texts_) > 8         # longer text (dialogue is longer than option text)
            )
            # Single characters / very short text are usually not valid options (debris or a 1-char NPC name)
            is_trivial = len(texts_) <= 2
            if is_npc_like or is_trivial:
                log.debug("filtered non-option text: %r (y=%.0f, x=%.0f, len=%d, npc=%s trivial=%s)",
                          texts_, abs_gy, gx, len(texts_), is_npc_like, is_trivial)
                continue

            x = int(min(xs))
            y = int(min(ys))
            cx = int(sum(xs) / len(xs))
            cy_int = int(sum(ys) / len(ys))
            # Detect the orange tint on the option's source pixels (key-story options are tinted orange-yellow).
            sub = frame[max(0, y - 8): y + 40, max(0, x - 8): x + 400]
            orange = is_orange_option(sub)
            out.append(
                Match(
                    x=x, y=y,
                    width=int(max(xs) - x), height=int(max(ys) - y),
                    text=texts_,
                    score=1.0 if orange else 0.0,
                    click=(cx, cy_int),
                )
            )
        return out

    def _decide_option(self, options: list[Match]) -> tuple[int, Match] | None:
        """Decide which option to click, following BetterGI's priority rules."""
        # 1. Custom priority words (user-defined).
        for i, o in enumerate(options):
            for kw in self.config.custom_priority:
                if kw and kw in o.text:
                    log.debug("matched custom priority word '%s'", kw)
                    return i, o

        # 2. Built-in priority words.
        for i, o in enumerate(options):
            for kw in self.config.select_keywords:
                if kw and kw in o.text:
                    log.debug("matched built-in priority word '%s'", kw)
                    return i, o

        # 3. Sensitive words -> pause and hand control to the user.
        for o in options:
            for kw in self.config.pause_keywords:
                if kw and kw in o.text:
                    if self._paused_reason != kw:
                        log.warning("option contains sensitive word '%s' (%s); pausing auto-tap, handle manually", kw, o.text)
                        self._paused_reason = kw
                    return None
        self._paused_reason = None

        # 4. Orange key-story options.
        if self.config.prefer_orange:
            for i, o in enumerate(options):
                if o.score > 0:
                    log.debug("matched orange option")
                    return i, o

        # 5. Fallback strategy.
        mode = self.config.option_mode
        if mode == "none":
            log.info("option mode=none; skip auto-selection, leave to manual control")
            return None
        if mode == "last":
            return len(options) - 1, options[-1]
        if mode == "random":
            i = random.randrange(len(options))
            return i, options[i]
        if mode == "second":
            # The 2nd option; fall back to the 1st when fewer than 2 exist, so we always click something.
            i = 1 if len(options) > 1 else 0
            return i, options[i]
        # first (default)
        return 0, options[0]

    # ------------------------------------------------------------- advance / black-screen / popup

    def _handle_playing(self, frame: np.ndarray) -> bool:
        """While playing: tap a safe area of the screen to advance dialogue (avoiding the top-left button and right-side option area)."""
        if not self.config.quick_skip:
            return False
        h, w = frame.shape[:2]
        self._tap_in_window(w * 0.5, h * 0.75)
        return True

    def _handle_black_screen(self, frame: np.ndarray) -> bool:
        if not self.config.click_black_screen:
            return False
        ratio = black_ratio(frame)
        if not (self.config.black_ratio_min <= ratio <= self.config.black_ratio_max):
            return False
        now = time.time()
        if now - self._last_black_click < 1.0:
            return False
        self._last_black_click = now
        h, w = frame.shape[:2]
        log.debug("black-screen cinematic (ratio %.2f) -> tap to advance", ratio)
        self._tap_in_window(w * 0.5, h * 0.5)
        return True

    def _handle_popup(self, frame: np.ndarray) -> bool:
        if not self.config.close_popup:
            return False
        h, w = frame.shape[:2]
        close = self._find(frame, "page_close.png", roi=(w - w // 8, 0, w // 8, h // 8))
        if close:
            log.info("pop-up page detected -> close")
            self._tap_match(close)
            return True
        return False

    # ------------------------------------------------------------- click anywhere to continue (Fontaine main story, etc.)

    def _find_option_bands(self, frame: np.ndarray) -> list[tuple[int, int, int]]:
        """Pure-pixel "option dark-band" detection: no templates or OCR.

Whatever form the Genshin option UI takes (plain dialogue bubble, gear options, case-book list rows,
investigation-panel entries ...), they share one visual feature -- a rounded dark band **darker than
the surrounding scene**, whose top/bottom edges show up as a pair of "enter dark zone / exit dark zone"
jumps in the per-row average brightness.

This scans the whole option_roi and returns every qualifying dark band as
(absolute_y_center, absolute_x_tap, height), sorted by y ascending so they can be advanced one by one
(tap the topmost each frame, detect the next one on the following frame).

An empty list means no recognizable option dark band on the current screen.
        """
        h, w = frame.shape[:2]
        roi = self._option_roi(frame)
        x0, y0, rw, rh = roi

        # Scan the entire ROI (the top title bar / bottom buttons are already excluded by the ROI margins)
        # instead of only the lower-middle 60%.
        scan_y_start = y0
        scan_y_end = y0 + rh
        scan_x_start = x0
        scan_x_end = x0 + rw

        crop = frame[scan_y_start:scan_y_end, scan_x_start:scan_x_end]
        if crop.size == 0:
            return []

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        ch, cw = crop.shape[:2]

        # Gaussian blur to suppress single noisy rows being mistaken for band edges.
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Mean brightness of each row.
        row_means = blurred.mean(axis=1)

        # Option bands span nearly the full width, so the per-row mean already captures their edges well;
        # a per-column variance filter is intentionally NOT used: Genshin's option bands are uniformly
        # semi-transparent dark, and short options (e.g. "yes/no") have almost no bright text/icon area,
        # so their column variance can fall below threshold and get wrongly dropped as a fake band.

        # First-order difference between adjacent rows (a vertical-gradient proxy) to locate brightness jumps
        # (the band's top/bottom edges).
        row_diff = np.abs(np.diff(row_means))

        # Locally adaptive threshold: mean diff + 0.8*std marks an edge.
        diff_mean = row_diff.mean()
        diff_std = row_diff.std()
        edge_threshold = diff_mean + diff_std * 0.8

        # Find notable "top-edge + bottom-edge" pairs.
        edges: list[tuple[int, str]] = []
        for i in range(1, len(row_diff)):
            if row_diff[i] > edge_threshold:
                if i + 1 < len(row_means) and row_means[i + 1] < row_means[i - 1]:
                    edges.append((i, "top"))
                elif i + 1 < len(row_means) and row_means[i + 1] > row_means[i - 1]:
                    edges.append((i, "bottom"))

        # Match each top edge with the next bottom edge, keeping dark bands 35~120px tall.
        # (upper cap 120 covers larger case-book list rows / section titles; lower cap 35 drops the
        # short bars of option-panel headers / dividers.)
        bands: list[tuple[int, int, int]] = []
        for idx in range(len(edges)):
            ey, etype = edges[idx]
            if etype != "top":
                continue
            for jdx in range(idx + 1, min(idx + 40, len(edges))):
                jy, jtype = edges[jdx]
                if jtype == "bottom":
                    band_h = jy - ey
                    if 35 <= band_h <= 120:
                        band_brightness = row_means[ey:jy].mean()
                        before_brightness = (
                            row_means[max(0, ey - 10):ey].mean()
                            if ey >= 10 else row_means[0:ey].mean()
                        )
                        after_brightness = (
                            row_means[jy:min(ch, jy + 10)].mean()
                            if jy + 10 <= ch else row_means[jy:].mean()
                        )
                        contrast = max(before_brightness - band_brightness,
                                       after_brightness - band_brightness)
                        # A band must be at least 12 gray levels darker than one side (to separate option
                        # bars from the surrounding scene). Note: we no longer use a column-variance filter
                        # for solid-color bars -- Genshin option bands are uniformly semi-transparent dark,
                        # and short options (e.g. "yes/no") have almost no text, so their column variance
                        # can fall below threshold and get wrongly dropped as a fake band, missing real
                        # dialogue options. Instead we only exclude near-pure-black bands: option bands are
                        # dark but not pure black (semi-transparent with a light stroke), whereas pure-black
                        # rows are the noise to drop.
                        if contrast > 12:
                            band_gray = blurred[ey:jy, :]
                            if band_gray.size == 0:
                                continue
                            band_mean = float(band_gray.mean())
                            if band_mean < 8:
                                continue  # near pure black -> most likely a black screen / background, not an option
                            abs_y = scan_y_start + ey + band_h // 2
                            # Tap point: center-right of the band (avoiding the left icon/index); for narrow
                            # list rows the 60% point still lands on the readable area.
                            abs_x = scan_x_start + int(cw * 0.6)
                            bands.append((abs_y, abs_x, band_h))
                    break

        # Sort by y and de-duplicate (bands < 15px apart are the same band).
        bands.sort(key=lambda b: b[0])
        dedup: list[tuple[int, int, int]] = []
        for b in bands:
            if dedup and b[0] - dedup[-1][0] < 15:
                continue
            dedup.append(b)
        return dedup

    def _guess_option_bubble(self, frame: np.ndarray) -> bool:
        """Fallback detection entry (pure pixel, no template/OCR).

Recognizes special option UIs without a standard icon (gear options, case-book, etc.), and taps the
topmost option band to advance the story. Multi-option lists advance one item per frame.
        """
        bands = self._find_option_bands(frame)
        if not bands:
            return False
        # Tap only the topmost item this frame; the next frame handles the next one (supports multi-option lists).
        abs_y, abs_x, band_h = bands[0]
        log.info("pure-pixel detected %d option band(s); tap topmost @y=%d, height=%dpx",
                 len(bands), abs_y, band_h)
        self._tap_in_window(abs_x, abs_y)
        self._last_option_click = time.time()
        return True

    def _has_continue_indicator(self, frame: np.ndarray) -> bool:
        """Pure-pixel detection of the bottom-center "tap anywhere to continue" indicator (downward arrow / inverted triangle).

No templates or OCR: look for a small bright patch noticeably brighter than its surroundings inside the
bottom-center ROI (a white inverted triangle stands out strongly against the dark story background).
This is the visual signature of the "tap anywhere to continue" prompt, distinct enough from a real
dialogue-option screen.
        """
        h, w = frame.shape[:2]
        # Bottom-center region, about half the width and one-sixth the height.
        rx, ry = int(w * 0.25), int(h * (1 - 1 / 6))
        rw, rh = int(w * 0.5), int(h / 6)
        if rw <= 0 or rh <= 0:
            return False
        crop = frame[ry : ry + rh, rx : rx + rw]
        if crop.size == 0:
            return False

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        # The indicator is usually white / light gray, far brighter than the dark background.
        _, binarized = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binarized, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            if area < 80 or area > 6000:
                continue
            x, y, cw, ch = cv2.boundingRect(c)
            # The indicator is small and near square/triangle, so its aspect ratio is not extreme.
            if cw <= 0 or ch <= 0:
                continue
            aspect = max(cw, ch) / min(cw, ch)
            if aspect > 4:
                continue
            # Its centroid should sit near the ROI's horizontal center (the inverted triangle is centered).
            cx = x + cw / 2
            if abs(cx - rw / 2) > rw * 0.25:
                continue
            return True
        return False

    def _is_click_continue(self, frame: np.ndarray) -> bool:
        """Detect "tap anywhere to continue / tap screen to continue" prompts.

Hit when any of the following holds:
          1. template icon_click_continue.png matches (if captured);
          2. OCR hits a "tap ... to continue / anywhere" phrase;
          3. pure-pixel detection of a bottom-center arrow/inverted-triangle indicator AND no option dark band on screen.
The 3rd rule keeps advancement working even when the template is missing or OCR is not installed;
the "no option dark band" joint check avoids false triggers on normal dialogue/option screens."""
        h, w = frame.shape[:2]

        # --- 1) Bottom inverted-triangle / arrow template (if captured) ---
        arrow = self._find(frame, "icon_click_continue.png",
                           roi=(w // 4, h - h // 6, w // 2, h // 6))
        if arrow:
            return True

        # --- 2) OCR fallback: hit a "tap ... to continue" phrase in the bottom area ---
        # (when OCR is unavailable, recognize() returns empty and this branch is skipped)
        tx, ty = int(w * 0.20), int(h * 0.78)
        tw, th = int(w * 0.60), int(h * 0.20)
        crop = frame[ty : ty + th, tx : tx + tw]
        if crop.size:
            cont_words = self._kw.get("continue_", [])
            for r in self.ocr.recognize(crop, upscale=3):
                txt = r.text
                if not txt:
                    continue
                # Hitting any "continue / tap anywhere" class word counts as the prompt.
                if any(w and w in txt for w in cont_words):
                    return True

        # --- 3) Pure-pixel fallback: bottom-center arrow / inverted-triangle indicator ---
        #     skipped when option dark bands are present (to avoid false triggers on normal dialogue screens)
        if self._has_continue_indicator(frame):
            bands = self._find_option_bands(frame)
            return len(bands) == 0
        return False

    def _handle_click_continue(self, frame: np.ndarray) -> bool:
        """Advance "tap anywhere to continue" style story. Tap the lower-center of the screen (safe zone)."""
        if not self.config.click_continue:
            return False
        if not self._is_click_continue(frame):
            return False
        h, w = frame.shape[:2]
        log.info("'tap anywhere to continue' prompt detected -> tap to advance")
        self._tap_in_window(w * 0.5, h * 0.6)
        return True

    # ------------------------------------------------------------- main loop

    def tick(self) -> None:
        frame_full = self.device.screencap()

        # Re-localize the window on the first frame or when the resolution may have changed.
        if self.window is None:
            self.window = resolve_window(self.device, frame_full, self.config.package)

        frame = self.window.crop(frame_full)
        if frame.size == 0:
            log.warning("cropped frame is empty; re-localizing window")
            self.window = None
            return

        self._frame_index += 1
        if self.config.debug and self._frame_index % 20 == 0:
            self._dump_debug(frame, "frame")

        now = time.time()
        playing = self._is_playing(frame)
        if playing:
            self._last_playing_at = now
        in_grace = (now - self._last_playing_at) <= PLAYING_FLAG_GRACE

        # Hangout skip (independent of playing state)
        if self._handle_hangout(frame):
            return

        # Options take priority over advancing, to avoid mis-tapping away an option
        if self._handle_options(frame):
            return

        if playing and self._handle_playing(frame):
            self._last_frame = frame
            return

        if self._handle_black_screen(frame):
            return

        if in_grace and self._handle_popup(frame):
            return

        # "Tap anywhere to continue" (e.g. Fontaine main story) -- lower priority than options / popups.
        if self._handle_click_continue(frame):
            return

        # The screen is idle and not playing -> the story has ended; just stand by silently.
        if not in_grace:
            diff = frame_diff_ratio(self._last_frame, frame)
            if diff < 0.01:
                log.debug("screen idle and not playing; standing by")

        self._last_frame = frame

    def run(self) -> None:
        log.info("auto story-skip started; press Ctrl+C to stop")
        errors = 0
        while True:
            start = time.time()
            try:
                self.tick()
                errors = 0
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                errors += 1
                log.error("loop exception (accumulated %d, ignored): %s", errors, exc)
                # Do not auto-exit: keep retrying so a long run is not killed by a transient error.
                time.sleep(min(1.0 + errors * 0.5, 10.0))

            elapsed = time.time() - start
            if elapsed < self.config.interval:
                time.sleep(self.config.interval - elapsed)
