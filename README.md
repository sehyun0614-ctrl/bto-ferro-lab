# BTO Ferro Lab

졸-겔 **BaTiO₃ 강유전 커패시터**(Pt/BTO/Pt vs Pt/TiO₂/BTO/Pt)의 공정, 측정, 데이터 분석, 차세대 통신용 메모리 응용을 한곳에서 다루는 Streamlit 웹앱입니다.

국민대학교 UROP · 지도교수 심인보 · 박세현, 김지우, 병욱

## 페이지 구성

| 페이지 | 내용 |
|---|---|
| 개요 | 연구 목적, 두 구조, 8개 시편 요약 |
| 공정 레시피 · XRD | `data/recipe.json`의 공정 단계, 두께 계산기, 700 °C/750 °C XRD 비교와 BaCO₃·TiO₂ 후보 피크 표시 |
| 소자 설계값 | 물성값으로 계산한 두께·Vmax·예상 C·Vc, TiO₂ 전압 분담, MFM vs MFBM 예상 P–E 루프 |
| 측정 진단 시뮬레이터 | 시편·접촉 상태·장비 세팅을 고르면 HRSMU I–V, 4284A C–V, WGFMU P–E 결과를 계산하고 자동 판정. 11/19 실측을 겹쳐 비교, 측정 순서 점검표 |
| 11/19 측정 데이터 | B1500A EasyEXPERT CSV 자동 파싱·분류(정상/Open/Short/바닥신호), 판정 매트릭스, I–V 상한 분석, 새 CSV 업로드 |
| 차세대 통신 메모리 | 1T1C FeRAM 셀로 축소했을 때 읽기 ΔV, 스위칭 속도(NLS/KAI + Merz), 에너지, 피로·보존, 통신 응용별 적합성 |
| 레퍼런스 | 가정값과 판정 기준의 근거 논문 |
| AI 활용 · 검증 기록 | AI에게 맡긴 일과 팀이 직접 검증한 일, AI 판단을 바로잡은 사례 |

## 값의 출처 표시

- **실측**: 우리가 측정한 값 (SEM 두께 43.8 nm/회, TiO₂ 32.69 nm, 패드 Ø750 µm, 11/19 CSV)
- **가정**: 문헌 범위에서 고른 값 (εr, Ps, Ec 등) → 사이드바에서 바꿀 수 있음
- **모델**: 위 값으로 계산한 투영값 (메모리 성능 등)
- **경험값**: 11/17·11/19 측정에서 관찰한 장비 동작 (`core/instruments.py`의 `EMPIRICAL`, 출처 문구 포함)

## 폴더 구조

```
app.py                 # 진입점, 사이드바 물성값, 페이지 목록
views/                 # 페이지 8개
core/
  physics.py           # 직렬 스택 P–E 모델, 설계값
  instruments.py       # 장비 시뮬레이터 + 자동 판정
  b1500.py             # EasyEXPERT CSV 파서 + 판정
  dataset.py           # data/1119 로딩, 시편 매핑
  memory.py            # FeRAM 투영 모델
  plotting.py          # 그래프 스타일, 한글 폰트
data/
  recipe.json          # 공정 레시피 (null = 미기입, 채워 주세요)
  references.json
  1119/*.csv           # 11/19 원본 측정 파일 + sample_map.json
  xrd/*.TXT            # 11/11, 11/13 XRD
```

## 로컬 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 웹 배포 (Streamlit Community Cloud, 무료)

1. 이 폴더를 GitHub 저장소로 올립니다 (Public 또는 Private).
2. https://share.streamlit.io 에 GitHub 계정으로 로그인 → **Create app**.
3. 저장소, 브랜치(`main`), Main file path에 `app.py`를 선택 → **Deploy**.
4. 몇 분 뒤 `https://<이름>.streamlit.app` 주소가 생깁니다. `packages.txt`가 한글 폰트(fonts-nanum)를 설치합니다.

## 새 측정 데이터 추가

- 앱에서: "11/19 측정 데이터" 페이지의 업로드 칸에 CSV를 올리면 바로 판정합니다 (세션 동안만 유지).
- 영구 반영: `data/1119/`(또는 날짜별 새 폴더)에 CSV를 넣고 커밋합니다. 시편을 파일명/Remarks로 못 찾으면 `sample_map.json`에 추가하세요.
- 시편 규칙: Remarks나 파일명의 `1-4`, `2_6` 같은 표기에서 앞자리 1 = MFM, 2 = MFBM, 뒷자리 = 코팅 횟수.

## AI 활용

이 앱의 코드 초안과 분석 아이디어는 Anthropic Claude와 함께 작성했습니다. 측정, 시편 제작, 조건 확정, 결과 해석의 최종 판단은 팀이 했고, AI의 판단을 원본 데이터로 다시 검증해 바로잡은 기록은 앱의 "AI 활용 · 검증 기록" 페이지에 있습니다.

## 한계

- 메모리 페이지 숫자는 모델 투영값입니다. Pr, Ec, 스위칭 시간, 피로를 실측하면 갱신해야 합니다.
- 11/19 데이터에는 정상 C–V·P–E가 아직 없습니다. 측정 순서 점검표의 규칙(같은 패드에서 4284A로 nF 확인 → P–E)을 따라 재측정이 필요합니다.
- XRD 2차상 표시는 후보입니다. JCPDS/ICDD 카드로 최종 확인하세요.
