# 공정 최적화 프로젝트

## 개요
이 프로젝트는 반도체 제조 공정에서 **공정 순서**, **설비 배치**, **AMR 대수**를 최적화하여 **Profit을 최대화**하는 시스템입니다.

## 문제 정의
- **목표**: Profit = [100×min(A완성품, B완성품) - 5×총출고수] / [설비비용 + AMR비용] 최대화
- **제약조건**:
  - AMR: 최대 30대
  - 설비 설치 가능 위치: 30개 고정 좌표
  - 공정: A(산화), B(노광), C(식각), D(증착), E(계측)

## 설치 방법

### 1. 필요한 패키지 설치
```powershell
pip install matplotlib
```

### 2. 파일 구조
```
teamProject-main - 복사본1/
├── config.py              # 시뮬레이션 설정
├── data_structures.py     # 데이터 구조
├── sim_core.py           # 시뮬레이션 코어
├── kpi.py                # KPI 계산
├── logger.py             # 로깅
├── visualization.py      # AMR 애니메이션
├── optimizer.py          # 최적화 알고리즘 (새로 생성)
├── visualize_results.py  # 결과 시각화 (새로 생성)
└── run_optimization.py   # 실행 스크립트 (새로 생성)
```

## 사용 방법

### 빠른 테스트 (작은 규모)
```powershell
python run_optimization.py --quick
```
- 개체군 10개, 5세대로 빠르게 테스트
- 약 5-10분 소요

### 기본 실행
```powershell
python run_optimization.py
```
- 개체군 20개, 30세대
- 약 30-60분 소요

### 고급 설정
```powershell
python run_optimization.py --population 50 --generations 100 --sim_time 1296000
```
- 개체군 크기, 세대 수, 시뮬레이션 시간 커스터마이즈
- 더 정밀한 결과, 더 오래 걸림

## 출력 파일

실행 후 다음 파일들이 생성됩니다:

1. **optimization_results.json**: 최적화 결과 데이터 (JSON)
2. **optimization_history.png**: 세대별 fitness 변화 그래프
3. **best_solution.png**: 최적 솔루션 시각화 (공정순서, 설비배치, 성능지표)
4. **optimization_report.txt**: 상세 텍스트 리포트

## 알고리즘 설명

### 유전 알고리즘 (Genetic Algorithm)
1. **염색체 구조**:
   - 공정 순서: [A, B, C, D, E]의 순열
   - 설비 배치: 30개 위치 중 선택
   - AMR 대수: 1~30

2. **진화 과정**:
   - 초기 개체군 생성
   - 평가: 각 염색체를 시뮬레이션하여 profit 계산
   - 선택: 토너먼트 방식
   - 교차: 부모 염색체 조합
   - 변이: 랜덤 변경
   - 엘리트 보존: 최고 개체 유지

3. **최적화 변수**:
   - 공정 순서: 5! = 120가지 조합
   - 설비 개수: 각 공정당 1~6대
   - 설비 위치: 30개 위치에서 선택
   - AMR 대수: 1~30대

## 예상 결과

최적화 후 다음과 같은 정보를 얻을 수 있습니다:
- 최적 공정 순서 (예: C → A → D → B → E)
- 각 공정별 설비 대수 및 위치
- 최적 AMR 대수
- 예상 완성품 수 (A, B)
- 최대 Profit 값

## 문제 해결

### "No module named 'matplotlib'" 오류
```powershell
pip install matplotlib
```

### 한글 폰트 깨짐
`visualize_results.py`에서 폰트 설정을 다른 한글 폰트로 변경:
```python
plt.rcParams['font.family'] = 'Malgun Gothic'  # 또는 'NanumGothic', 'AppleGothic'
```

### 시뮬레이션 시간 초과
- `--quick` 옵션으로 테스트
- `--population`과 `--generations`를 줄여서 실행

## 추가 분석

결과 파일(`optimization_results.json`)을 사용하여 추가 분석 가능:
```python
import json

with open('optimization_results.json', 'r', encoding='utf-8') as f:
    results = json.load(f)

best = results['best_solution']
print(f"최적 공정 순서: {best['route']}")
print(f"최적 AMR: {best['amr_count']}대")
print(f"Profit: {best['profit']}")
```

## 성능 개선 팁

1. **더 많은 세대**: `--generations 100` 이상
2. **더 큰 개체군**: `--population 50` 이상
3. **다양한 시드**: `--seed`를 바꿔가며 여러 번 실행
4. **병렬 처리**: 코드 수정으로 다중 프로세싱 추가 가능

## 라이선스
이 프로젝트는 교육 목적으로 사용됩니다.
