# bgia — Android용 원신 자동 스토리 스킵

> [BetterGI](https://github.com/babalae/better-genshin-impact)의 `AutoSkip` 모듈 이식판이며, **GPL-3.0** 오픈소스 라이선스로 공개합니다.

언어 / Language：
[简体中文](./README.md) · [English](./README/readme_en.md) · [繁體中文](./README/readme_tc.md) · [日本語](./README/readme_ja.md) · [한국어](./README/readme_ko.md) · [Русский](./README/readme_ru.md)

Telegram 그룹：[@bettergi_for_android](https://t.me/bettergi_for_android)

**ADB 화면 인식 + 가상 탭** 기반의 원신 자동 스토리 스킵 스크립트로, 로직은 [BetterGI](https://github.com/babalae/better-genshin-impact)의 `AutoSkip` 모듈에서 이식했습니다.

루팅 불필요, 게임 주입 불필요, 게임 메모리 읽기/쓰기 불필요. "스크린샷 → 인식 → `input tap`"만 수행하며 사람이 화면을 탭하는 것과 동일합니다.

지원: 원신 **공식 / Bilibili / 각종 해외 서버**, 그리고 **클라우드 원신**(중국·해외판).

## 작동 원리

```
adb screencap  ──►  16:9 렌더 영역 크롭  ──►  템플릿 매칭 + OCR  ──►  판단  ──►  adb input tap
```

각 프레임은 다음 우선순위로 처리됩니다(BetterGI와 동일):

| # | 상황 | 동작 |
|---|---|---|
| 1 | 교룡(데이트) 화면 | "건너뛰기" 버튼 탭 |
| 2 | 대화 선택지 | 느낌표 우선; 아니면 OCR로 선택지 텍스트를 읽어 규칙으로 판단 |
| 3 | 재생 중 | 안전 영역을 탭해 대화 빠르게 진행 |
| 4 | 검은 화면 연출 | 초당 1회 탭하여 진행 |
| 5 | 팝업 | 우상단 닫기 버튼 탭 |
| 6 | 아무 곳이나 탭하여 계속 | "아무 곳이나 탭하여 계속" 프롬프트 등장 시 자동 탭(`click_continue` 참조, 폰타인 메인 스토리 등) |

선택지 판단은 5단계 우선순위 체인입니다:
**사용자 지정 우선어 → 내장 우선어 → 민감어(일시정지) → 주황색 핵심 선택지 → 폴백 전략(처음/마지막/무작위)**

## 설치

```bash
# 1. Android Platform Tools (adb 제공) 설치
sudo apt install android-tools-adb        # Debian/Ubuntu/Kali
# macOS: brew install android-platform-tools

# 2. 가상환경 생성 후 의존성 설치
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> **Kali / Debian 12+ 사용자**: 이들 시스템은 PEP 668 보호를 활성화합니다. 직접 `pip install`은
> `externally-managed-environment` 오류가 됩니다. **위의 가상환경 방식을 사용하세요**;
> `--break-system-packages`는 추가하지 마세요(시스템 Python을 오염시키고 apt를 망가뜨릴 수 있습니다).
> venv가 없으면 먼저 `sudo apt install python3-full python3-venv`를 실행하세요.

이후 모든 명령은 `.venv/bin/python`으로 실행하거나, 먼저 `source .venv/bin/activate`
(그 후 `python` 바로 사용), 종료는 `deactivate`입니다.

## 크로스 플랫폼

본 프로젝트는 **Linux / macOS / Windows**, 그리고 **루팅된 Android 기기 로컬 실행**(PC 불필요)을 지원합니다.

### Windows

1. Python 3.10+ 설치("Add to PATH" 체크).
2. [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) 다운로드 후,
   `adb.exe`가 있는 디렉터리를 시스템 `PATH`에 추가하거나 `adb.exe`를 프로젝트 루트 / `platform-tools/`에 배치
   (스크립트가 자동 탐지).
3. `bgia.bat` 사용(`bgia.sh`와 동일 메뉴):
   ```bat
   bgia.bat
   ```
   또는 명령줄에서 직접:
   ```bat
   .venv\Scripts\python.exe -m bgia.cli run
   ```

### 루팅된 Android 기기 (로컬 셸 모드)

기기의 **Termux (루팅) / Magisk 터미널**에서 직접 실행. 스크린샷과 탭은
`/system/bin/screencap`과 `/system/bin/input` 경유 — **PC 불필요, adb 포워딩 불필요**.

1. Termux에서 Python과 의존성 설치(Termux는 `clang`/`libc++` 동봉):
   ```bash
   pkg update && pkg install python clang libc++ make
   python -m venv .venv && .venv/bin/pip install -r requirements.txt
   ```
2. root로 실행(그렇지 않으면 `screencap` / `input`이 화면에 접근 불가):
   ```bash
   su
   cd /data/data/com.termux/files/home/bgia   # 프로젝트 경로
   .venv/bin/python -m bgia.cli run --local
   ```

> 로컬 모드는 adb 연결을 생략하고 시스템 `screencap -p` / `input tap`을 직접 호출합니다.
> 스크린샷이 실패하면 `su`를 실행했는지, `/system/bin/screencap`이 존재하는지 확인하세요.

## 휴대전화 연결

**USB:** "개발자 옵션 → USB 디버깅" 활성화 후 연결, 기기에서 "허용" 탭.

**무선 (Android 11+):** "개발자 옵션 → 무선 디버깅" 활성화 후 코드로 페어링:

```bash
adb pair 192.168.1.20:37xxx      # 기기에 표시된 페어링 코드 입력
adb connect 192.168.1.20:5555
```

**무선 (Android 10 이하):** 먼저 USB로 한 번 `adb tcpip 5555` 실행 후 `adb connect <IP>:5555`.

연결 확인:

```bash
python -m bgia.cli devices
```

## 템플릿 에셋 준비

스크립트는 몇 가지 UI 템플릿 이미지에 의존합니다. 원본 템플릿은 이 저장소에 포함되지 않으므로,
**본인 기기 스크린샷에서 한 번만 캡처**하세요(서버 간 UI 차이에도 적응).

게임 내 아무 대화 씬에 들어간 후:

```bash
# 프레임 캡처
.venv/bin/python tools/grab_template.py shot        # shot.png 생성

# 영역을 대화형으로 선택해 저장 (GUI + opencv-python 필요, 헤드리스 불가)
.venv/bin/python tools/grab_template.py pick --name icon_option.png

# 또는 이미지 뷰어로 픽셀 좌표를 잰 뒤 바로 크롭 (GUI 불필요, 권장)
.venv/bin/python tools/grab_template.py crop --rect 1150,470,36,36 --name icon_option.png
```

도구는 크롭을 저장 전 **1920×1080 기준**으로 자동 정규화하므로, 기기나 해상도를 바꿔도 재캡처 불필요합니다.

필요한 템플릿(누락 시 그레이스풀하게退化, 크래시 없음):

| 파일 | 내용 | 누락 시 영향 |
|---|---|---|
| `icon_option.png` | 선택지 좌측 말풍선 아이콘 | 선택지 위치 파악 불가; 재생 진행으로退化 |
| `icon_exclamation.png` | 핵심 퀘스트 선택지의 느낌표 아이콘 | 느낌표 우선순위 상실 |
| `stop_auto.png` | 좌상단 "자동 재생" 버튼 | 재생 상태는 OCR로 폴백 |
| `hangout_skip.png` | 교룡 화면의 건너뛰기 버튼 | 교룡 자동 스킵 안 됨 |
| `page_close.png` | 팝업 우상단 닫기 버튼 | 팝업 자동 닫힘 안 됨 |
| `icon_click_continue.png` | 하단 "아무 곳이나 탭하여 계속" 삼각형/화살표 | 픽셀 형태 검출로退化(아래 "스크린샷 전용 모드" 참조) |

## 사용법

```bash
# 자가 점검: 해상도, 패키지, 렌더 영역, 템플릿, OCR
.venv/bin/python -m bgia.cli check

# 실행
.venv/bin/python -m bgia.cli run

# 자주 쓰는 조합
.venv/bin/python -m bgia.cli run -c config.yaml          # 설정 파일 사용
.venv/bin/python -m bgia.cli run -w 192.168.1.20:5555    # 무선 연결 + 실행
.venv/bin/python -m bgia.cli run -m last                 # 마지막 선택지 우선
.venv/bin/python -m bgia.cli run --debug -v              # 디버그 스크린샷 + 상세 로그
```

중지는 `Ctrl+C`.

## 설정

`config.example.yaml`을 `config.yaml`로 복사해 편집. 주요 항목:

```yaml
option_mode: first          # 선택지 전략 first/last/random/none
before_choose_delay: 0.0    # 보이스를 듣고 싶으면 2~3초 설정
custom_priority:            # 사용자 지정 우선 선택지
  - "계속하기"
pause_keywords:             # 히트 시 일시정지(소비형 선택지 오탭 방지)
  - 비밀의 문 나가기
  - 구매
interval: 0.6               # 클라우드 원신 스트리밍: 0.8~1.0 권장
```

## 서버 참고

| 서버 | 패키지 |
|---|---|
| 공식 | `com.miHoYo.Yuanshen` |
| Bilibili | `com.miHoYo.ys.bilibili` |
| 해외 | `com.miHoYo.GenshinImpact` |
| 클라우드(중국) | `com.miHoYo.cloudgames.ys` |
| 클라우드(해외) | `com.miHoYo.cloudgames.genshinimpact` |

패키지는 자동 감지, 또는 `-p`로 강제 지정.

**클라우드 원신 참고:** 화면은 비디오 스트리밍으로 인코딩 열화와 지연이 있습니다.
`interval`을 `0.8~1.0`으로 높이고 `template_threshold`를 `0.72~0.75`로 낮추세요. 스트리밍 레터박스는 자동 크롭됩니다.

**노치/풀스크린 대응:** 20:9 등 비 16:9 화면에서는 게임이 중앙 정렬되어 좌우 안전 영역이 생깁니다.
스크립트는 실제 16:9 렌더 영역을 자동 찾아 모든 좌표를 매핑하므로 수동 설정 불필요.

**해상도 / DPI / 스케일 대응:** 스크립트는 모든 기기 특성에 자동 적응, 수동 설정 불필요:
- **해상도:** 모든 템플릿/ROI는 실행 시 "렌더 너비 ÷ 1920"으로 스케일; 1920×1080 기준 템플릿은
  720p/1080p/2K에서 동작; 렌더 영역은 프레임마다 자동 검출(흑변 트림 + 16:9 수렴), 하드코딩 없음.
- **DPI / 스케일(`wm density`, `wm size` 오버라이드):** `screencap`은 실제 표시 해상도(물리 픽셀)를 반환하고,
  `input tap`은 `wm size` 논리 픽셀을 씁니다. DPI 스케일로 차이가 있으면 스크립트가
  "스크린샷 크기 ÷ 표시 크기" 비율을 캐시해 탭 좌표를 자동 변환, 체계적 어긋남 해소.
- 따라서 기기 교체, 표시 스케일 변경, 게임 내 해상도 전환도 템플릿 재캡처나 설정 변경 불필요.

## FAQ

**선택지가 인식되지 않음** — `check`를 실행해 템플릿 준비 확인; `template_threshold`를 `0.72`로 낮춤;
그래도 안 되면 `--debug`로 `debug/`에 스크린샷을 출력해 본인 기기 UI와 일치하는지 확인
(서버마다 약간 다름; 재캡처 필요).

**탭 위치가 어긋남** — 렌더 영역 검출이 틀림; `check`를 실행해 실제 화면과 일치하는지 확인;
게임이 가로이고 전면에 있는지 확인. 시스템 표시 스케일(`wm size` / `wm density`)을 바꿨다면
스크립트가 물리/논리 비율로 자동 변환; 그래도 어긋나면 `adb shell wm size reset`과
`adb shell wm density reset`으로 스케일 복원.

**스크린샷이 느림** — 일부 기기는 `screencap`이 느림; 스크립트는 이미 원시 픽셀 파이프라인
(PNG보다 빠름)을 우선함. `interval`을 약간 높이세요.

**OCR 사용 불가** — `.venv/bin/pip install rapidocr onnxruntime` 실행. 없어도 스크립트 동작하며,
선택지는 위치 기반 탭으로退化.

**스크린샷 전용 모드(순픽셀 폴백)** — 템플릿 미캡처나 OCR 미설치여도 순픽셀 분석으로 선택지와
계속 프롬프트를 인식:
- **선택지 검출:** 화면에서 "주변보다 어두운 둥근 막대"(원신 선택지 UI의 공통 시각 특징)를 스캔해
  최상단을 자동 탭하여 하나씩 진행. 일반 말풍선, 톱니 아이콘 선택지, 사건 기록 목록 등에서 동작.
- **아무 곳이나 탭하여 계속:** 하단 중앙 삼각형/화살표 형태 검출(순 형태 검출, 템플릿 불필요).
- 이는 템플릿/OCR 누락 시 최종 폴백으로, 어떤 환경에서도 데드락을 방지합니다.

**pip `externally-managed-environment`** — Kali/Debian 12+의 PEP 668; 설치 절의 가상환경 사용.
오류의 `python3-xyz`는 단순한 플레이스홀더 이름이며 실제 패키지가 아님.

**`rapidocr-onnxruntime` 설치 안 됨** — 그 구버전 패키지는 Python `<3.13` 필요. Python 3.13+에서는
`rapidocr>=2.0`(이미 requirements.txt에 있음) 사용; 코드는 두 세대와 호환. 첫 실행 시 약 20MB의
ONNX 모델을 자동 다운로드.

## 면책 조항

본 프로젝트는 기술 학습 및 교류만을 목적으로 합니다. 스크립트는 ADB 가상 탭으로 동작하며 게임 파일을
수정하지 않고, 게임 메모리 읽기/쓰기를 하지 않으며, 네트워크 통신에 개입하지 않습니다. 이용자는 자동화
도구 사용으로 인한 모든 결과(계정 리스크 포함하되 이에 국한되지 않음)를 부담합니다. 해당 게임의 이용약관을
준수하세요.

## 감사의 글

본 프로젝트의 모든 것은 [**BetterGI · Better Genshin Impact**](https://github.com/babalae/better-genshin-impact)의
어깨 위에 있습니다.

- [babalae](https://github.com/babalae)님과 BetterGI의 모든 개발자·기여자에게 감사합니다.
  `AutoSkip` 모듈의 핵심 — 자동 진행, 선택지 인식, 재생 상태 검출 — 은 이 Android 이식판의 직접적인
  설계 청사진입니다. 그들의 오랜 기술 실천과 개방적 공유 없이는 본 프로젝트는 존재하지 않았습니다.
- 이슈를 제출하고, 템플릿 자산을 기여하며, 경계 사례를 보고해 준 BetterGI 커뮤니티 여러분께 감사합니다.
  그 어려운 과정에서 얻은 디테일은 이 이식이 수많은 우회를 피하게 해주었습니다.
- BetterGI가 **GPL-3.0** 오픈소스를 유지해 준 것에 감사합니다. 그 개방성이 지식을 새로운 플랫폼으로
  옮겼습니다. 본 프로젝트도 동일하게 GPL-3.0으로 공개하며 그 개방성을 다음으로 이어갑니다.

원본 프로젝트의 모든 코드와 모든 개발자에게 경의를 표합니다.

## Star History

<a href="https://www.star-history.com/?repos=HuTaoLoveFurina%2Fbetter-genshin-impact-android&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=HuTaoLoveFurina/better-genshin-impact-android&type=date&theme=dark&legend=top-left&sealed_token=PsfqI2ssPFXeokK1J0nVWKxzFeC7L0jkn1aBG6wKASZieIrXpIAYYjlx6Jlg-ISBs6Y5l5fy42HWD1q-pchInjMblwOz12D6fbw6q9dL06YWsUZYOOFxt_-leWNY1l8rPheUnBUOIyfqvxPHfbUIG1T_QzNd8vj1g1IktGO4DdjeJ1F0u_9XW2tm7383" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=HuTaoLoveFurina/better-genshin-impact-android&type=date&legend=top-left&sealed_token=PsfqI2ssPFXeokK1J0nVWKxzFeC7L0jkn1aBG6wKASZieIrXpIAYYjlx6Jlg-ISBs6Y5l5fy42HWD1q-pchInjMblwOz12D6fbw6q9dL06YWsUZYOOFxt_-leWNY1l8rPheUnBUOIyfqvxPHfbUIG1T_QzNd8vj1g1IktGO4DdjeJ1F0u_9XW2tm7383" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=HuTaoLoveFurina/better-genshin-impact-android&type=date&legend=top-left&sealed_token=PsfqI2ssPFXeokK1J0nVWKxzFeC7L0jkn1aBG6wKASZieIrXpIAYYjlx6Jlg-ISBs6Y5l5fy42HWD1q-pchInjMblwOz12D6fbw6q9dL06YWsUZYOOFxt_-leWNY1l8rPheUnBUOIyfqvxPHfbUIG1T_QzNd8vj1g1IktGO4DdjeJ1F0u_9XW2tm7383" />
 </picture>
</a>
