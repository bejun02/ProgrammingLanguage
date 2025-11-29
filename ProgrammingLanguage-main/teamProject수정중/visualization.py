"""
================================================================================
visualization.py - 시뮬레이션 시각화 모듈
================================================================================
이 파일은 AMR 이동 경로를 애니메이션으로 시각화하는 기능을 제공합니다.

주요 함수:
- animate_from_amr_runs(): AMR 이동 애니메이션 생성 및 표시
- build_blocks_by_unit(): 설비 블록 데이터 구조 생성
- draw_units(): 설비 블록 그리기
- draw_unit_outlines(): 설비 외곽선 그리기

시각화 요소:
- 그리드: 공장 바닥 (60m × 20m)
- 설비: 색상으로 구분된 직사각형 (A~E 공정)
- Warehouse: 흰색 사각형 (왼쪽)
- Stocker: 흰색 사각형 (오른쪽)
- AMR: 원형 마커 (빨강=적재, 파랑=공차)
- Trail: AMR 이동 경로 선

색상 코드:
- A공정(산화): 연한 빨강
- B공정(노광): 연한 파랑
- C공정(식각): 연한 녹색
- D공정(증착): 연한 노랑
- E공정(계측): 연한 분홍

사용법:
    animate_from_amr_runs(
        global_variable.amr_runs,
        interval_ms=100,    # 프레임 간격 (ms)
        frames=1000,        # 총 프레임 수
        trail=True,         # 이동 경로 표시
        machine_positions=machine_positions
    )
================================================================================
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from dataclasses import dataclass
from typing import Dict, List, Tuple, Set
from config import global_variable

# 타입 별칭
Grid = Tuple[int, int]

# ================================================================================
# 색상 정의
# ================================================================================
# 공정별 설비 색상
MACHINE_COLORS = {
    "A": "#f4cccc",  # 연한 빨강 (산화)
    "B": "#c9daf8",  # 연한 파랑 (노광)
    "C": "#d9ead3",  # 연한 녹색 (식각)
    "D": "#fff2cc",  # 연한 노랑 (증착)
    "E": "#ead1dc",  # 연한 분홍 (계측)
}


# ================================================================================
# 데이터 구조
# ================================================================================
@dataclass(frozen=True)
class Bounds:
    """그리드 경계 정보"""
    min_x: int
    max_x: int
    min_y: int
    max_y: int


# 부동소수점 비교용 허용 오차
EPS = 1e-6


# ================================================================================
# 유틸리티 함수
# ================================================================================
def _segment_state(runs, t: float):
    """
    특정 시간 t에서 AMR의 세그먼트 상태 확인
    
    Args:
        runs: AMR 이동 기록 리스트
        t (float): 확인할 시뮬레이션 시간
    
    Returns:
        tuple: (세그먼트 내 여부, 마지막 종료 시간, 마지막 적재 상태)
    """
    in_seg = False
    last_e = -np.inf
    last_ld = False
    for s, e, *_rest, ld in runs:
        s = float(s)
        e = float(e)
        if s - EPS <= t <= e + EPS:
            in_seg = True
        if e <= t + EPS and e > last_e:
            last_e = e
            last_ld = bool(ld)
    return in_seg, last_e, last_ld


def build_blocks_by_unit(machine_positions: Dict[str, List[Tuple[int, int]]], radius: int = 1):
    """
    설비 위치 정보로부터 블록 데이터 구조 생성
    
    Args:
        machine_positions: 공정별 설비 위치 딕셔너리
        radius: 설비 반경 (미사용, 호환성용)
    
    Returns:
        list: 설비 유닛 정보 리스트
            - group: 공정 이름 (A~E)
            - idx: 설비 번호
            - center: 중심 좌표
            - cells: 차지하는 셀 집합
            - color: 표시 색상
    
    설비 크기: 4×2 셀 (x방향 4, y방향 2)
    """
    units = []
    for group, centers in machine_positions.items():
        color = MACHINE_COLORS.get(group, "mistyrose")
        for i, (x, y) in enumerate(centers, start=1):
            cells = set()
            # 설비 크기: 4×2 (중심에서 x방향 -2~+2, y방향 -1~+1)
            for xx in range(x - 2, x + 2):
                for yy in range(y - 1, y + 1):
                    cells.add((xx, yy))
            units.append({
                "group": group,
                "idx": i,
                "center": (x, y),
                "cells": cells,
                "color": color,
            })
    return units


def infer_bounds_from_runs_and_blocks(amr_runs, blocks: Set[Grid], margin: int = 2) -> Bounds:
    """AMR 이동 기록과 블록 정보로부터 그리드 경계 추론"""
    xs, ys = set(), set()
    for runs in amr_runs.values():
        for s, e, job_id, frm, to, loaded in runs:
            xs.update([int(frm[0]), int(to[0])])
            ys.update([int(frm[1]), int(to[1])])
    for (x, y) in blocks:
        xs.add(int(x))
        ys.add(int(y))
    if not xs:
        xs = {0}
    if not ys:
        ys = {0}
    return Bounds(min(xs) - margin, max(xs) + margin, min(ys) - margin, max(ys) + margin)


def _unify_timeline_from_runs(amr_runs, frames=300):
    """
    모든 AMR의 이동 기록으로부터 통합 타임라인 생성
    
    Args:
        amr_runs: AMR별 이동 기록
        frames: 총 프레임 수
    
    Returns:
        np.array: 균일 간격의 시간 배열
    """
    t0, t1 = float("inf"), float("-inf")
    for runs in amr_runs.values():
        for s, e, *_ in runs:
            t0 = min(t0, float(s))
            t1 = max(t1, float(e))
    if not np.isfinite(t0) or not np.isfinite(t1) or t1 <= t0:
        return np.array([])
    return np.linspace(t0, t1, num=frames)


def draw_blocks(ax, group_blocks):
    """그룹별 블록 그리기 (레거시 함수)"""
    for group, blocks in group_blocks.items():
        for (x, y), color in blocks:
            ax.fill_between([x, x + 1], y, y + 1, color=color, edgecolor='k', linewidth=0.2)


def _pos_loaded_at_t(runs, t):
    """
    특정 시간 t에서 AMR의 위치와 적재 상태 계산
    
    Args:
        runs: AMR 이동 기록
        t: 시뮬레이션 시간
    
    Returns:
        tuple: ((x, y), loaded) - 위치와 적재 여부
    
    동작:
        - 이동 중: 선형 보간으로 중간 위치 계산
        - 정지 중: 마지막 도착 위치 반환
    """
    last_xy = (0.0, 0.0)
    last_loaded = False
    for s, e, _job, xy0, xy1, loaded in runs:
        s, e = float(s), float(e)
        if t < s:
            return last_xy, last_loaded
        if s <= t <= e:
            if e == s:
                return xy1, loaded
            # 선형 보간: 이동 중인 위치 계산
            r = (t - s) / (e - s)
            x = xy0[0] + (xy1[0] - xy0[0]) * r
            y = xy0[1] + (xy1[1] - xy0[1]) * r
            return (x, y), loaded
        last_xy, last_loaded = xy1, loaded
    return last_xy, last_loaded


def infer_bounds_from_runs_blocks_and_points(amr_runs, blocks, extra_points=(), margin=2):
    """추가 포인트를 포함한 그리드 경계 추론"""
    xs, ys = set(), set()
    for runs in amr_runs.values():
        for _s, _e, _job, frm, to, _ld in runs:
            xs.update([int(frm[0]), int(to[0])])
            ys.update([int(frm[1]), int(to[1])])
    for (x, y) in blocks:
        xs.add(int(x))
        ys.add(int(y))
    for (x, y) in extra_points:
        xs.add(int(x))
        ys.add(int(y))
    if not xs:
        xs = {0}
    if not ys:
        ys = {0}
    return Bounds(min(xs) - margin, max(xs) + margin, min(ys) - margin, max(ys) + margin)


# ================================================================================
# 메인 애니메이션 함수
# ================================================================================
def animate_from_amr_runs(amr_runs,
                          interval_ms: int = 400,
                          frames: int = 400,
                          trail: bool = True,
                          machine_positions: Dict[str, List[Grid]] | None = None):
    """
    AMR 이동 경로 애니메이션 생성 및 표시
    
    Args:
        amr_runs: AMR별 이동 기록 딕셔너리
            - 키: AMR 이름 (예: "AMR-01")
            - 값: [(시작시간, 종료시간, job_id, 출발좌표, 도착좌표, 적재여부), ...]
        interval_ms (int): 프레임 간격 (밀리초)
        frames (int): 총 프레임 수
        trail (bool): 이동 경로 표시 여부
        machine_positions: 공정별 설비 위치 딕셔너리
    
    시각화 요소:
        - 그리드: 0~60 × 0~20 범위
        - 설비: 색상으로 구분된 블록
        - Warehouse: 왼쪽 흰색 사각형 (4, 10)
        - Stocker: 오른쪽 흰색 사각형 (56, 10)
        - AMR: 원형 마커
            - 빨강: 제품 적재 중
            - 파랑: 공차 이동
        - Trail: AMR 이동 경로 선
    """
    # 타임라인 생성
    timeline = _unify_timeline_from_runs(amr_runs, frames=frames)
    if timeline.size == 0:
        print("빈 타임라인입니다.")
        return
    
    # 그리드 범위 (고정)
    X_MIN, X_MAX = 0, 60
    Y_MIN, Y_MAX = 0, 20

    # Warehouse, Stocker 위치
    wh_xy = getattr(global_variable.WAREHOUSE, "xy", None)
    stk_xy = getattr(global_variable.STOCKERS.get("STK-01", None), "xy", None) if hasattr(global_variable, "STOCKERS") else None

    # 그래프 설정
    fig, ax = plt.subplots(figsize=(12, 6))

    # 그리드 라인 그리기
    for x in range(X_MIN, X_MAX + 1):
        ax.plot([x, x], [Y_MIN, Y_MAX], linewidth=0.3, color="lightgray", zorder=1)
    for y in range(Y_MIN, Y_MAX + 1):
        ax.plot([X_MIN, X_MAX], [y, y], linewidth=0.3, color="lightgray", zorder=1)

    # 설비 블록 그리기
    units = build_blocks_by_unit(machine_positions)
    draw_units(ax, units)                                # 설비 내부 색상
    draw_unit_outlines(ax, units, lw=2.0, color='k')     # 설비 외곽선
    draw_unit_seams(ax, units, lw=1.2, color='dimgray')  # 설비 간 경계선

    # Warehouse 표시
    if wh_xy:
        ax.scatter([wh_xy[0] - 1], [wh_xy[1]], s=140, marker='s',
                   edgecolors='k', facecolors='white', zorder=5, label="Warehouse")
        ax.text(wh_xy[0] - 1, wh_xy[1] + 1, "WH", ha='center', va='bottom', fontsize=9, zorder=6)

    # Stocker 표시
    if stk_xy:
        ax.scatter([stk_xy[0] + 1], [stk_xy[1]], s=160, marker='s',
                   edgecolors='k', facecolors='white', zorder=5, label="STK-01")
        ax.text(stk_xy[0] + 1, stk_xy[1] + 1, "STOCKER", ha='center', va='bottom', fontsize=9, zorder=6)

    # 축 설정
    ax.set_aspect('equal', 'box')
    ax.set_xlim(X_MIN, X_MAX)
    ax.set_ylim(Y_MIN, Y_MAX)
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title("AMR Runs (Loaded=Red, Empty=Blue)")

    # AMR별 아티스트 객체 생성
    artists = {}
    for amr in amr_runs.keys():
        (line,) = ax.plot([], [], linewidth=2, label=amr, zorder=3)  # Trail 라인
        marker = ax.scatter([], [], s=80, zorder=4)  # AMR 마커
        artists[amr] = {"line": line, "marker": marker, "trail_x": [], "trail_y": []}

    ax.legend(loc="upper left")

    def init():
        """애니메이션 초기화 함수"""
        dr = []
        for a in artists.values():
            a["line"].set_data([], [])
            a["marker"].set_offsets(np.empty((0, 2)))
            dr.extend([a["line"], a["marker"]])
        return dr

    def update(i):
        """
        애니메이션 업데이트 함수 (매 프레임 호출)
        
        Args:
            i: 현재 프레임 인덱스
        
        동작:
            1. 현재 시간 t 계산
            2. 각 AMR의 위치와 적재 상태 계산
            3. 마커 위치 및 색상 업데이트
            4. Trail 경로 업데이트 (옵션)
        """
        t = float(timeline[i])
        draw_list = []
        
        for amr, runs in amr_runs.items():
            # 현재 위치와 적재 상태 계산
            (x, y), loaded = _pos_loaded_at_t(runs, t)
            in_seg, last_e, last_ld = _segment_state(runs, t)

            # 색상 결정 (적재=빨강, 공차=파랑)
            if in_seg:
                color = "red" if loaded else "blue"
            else:
                # 세그먼트 외부 (대기 중)
                if last_ld and np.isfinite(last_e):
                    # 하역 완료 시간 이후면 파랑 (공차)
                    if t >= last_e + global_variable.CURRENT_CFG.amr_unload_time - EPS:
                        color = "blue"
                    else:
                        color = "red"  # 하역 중
                else:
                    color = "blue" if not loaded else "red"

            # Trail 업데이트 (경로 표시)
            if trail:
                artists[amr]["trail_x"].append(x)
                artists[amr]["trail_y"].append(y)
                artists[amr]["line"].set_data(artists[amr]["trail_x"], artists[amr]["trail_y"])

            # 마커 위치 및 색상 업데이트
            artists[amr]["marker"].set_offsets(np.array([[x, y]]))
            artists[amr]["marker"].set_color(color)
            draw_list.extend([artists[amr]["line"], artists[amr]["marker"]])

        ax.set_title(f"AMR Runs — t={t:.2f}s (Loaded=Red, Empty=Blue)")
        return draw_list

    # 애니메이션 생성
    ani = animation.FuncAnimation(fig, update, frames=len(timeline),
                                  init_func=init, blit=False,
                                  interval=interval_ms, repeat=False,
                                  cache_frame_data=False)

    # 애니메이션 객체 참조 유지 (가비지 컬렉션 방지)
    animate_from_amr_runs._ani_ref = ani
    plt.show()


# ================================================================================
# 설비 그리기 함수
# ================================================================================
def _build_outline_segments(cells: Set[Tuple[int, int]]):
    """
    셀 집합의 외곽선 세그먼트 계산
    
    Args:
        cells: 셀 좌표 집합
    
    Returns:
        list: 외곽선 세그먼트 리스트 [(점1, 점2), ...]
    
    알고리즘:
        각 셀의 4변을 카운트하여, 1번만 나타나는 변이 외곽선입니다.
        (내부 변은 인접 셀과 공유되어 2번 카운트됨)
    """
    from collections import Counter
    
    def _norm_edge(p0, p1):
        """엣지 정규화 (방향 무관하게 정렬)"""
        return tuple(sorted((p0, p1)))
    
    edges = Counter()
    for (x, y) in cells:
        # 각 셀의 4변
        e1 = _norm_edge((x, y), (x + 1, y))         # 하단
        e2 = _norm_edge((x + 1, y), (x + 1, y + 1)) # 우측
        e3 = _norm_edge((x + 1, y + 1), (x, y + 1)) # 상단
        e4 = _norm_edge((x, y + 1), (x, y))         # 좌측
        edges.update([e1, e2, e3, e4])

    # 1번만 나타나는 변 = 외곽선
    outline = [edge for edge, cnt in edges.items() if cnt == 1]
    return outline


def draw_group_outlines(ax, group_blocks, lw=2.0, color='k', z=6):
    """그룹별 외곽선 그리기 (레거시 함수)"""
    for group, blocks in group_blocks.items():
        cells = {(x, y) for (x, y), _c in blocks}
        if not cells:
            continue
        outline = _build_outline_segments(cells)
        for (x0, y0), (x1, y1) in outline:
            ax.plot([x0, x1], [y0, y1], linewidth=lw, color=color, zorder=z)


def draw_units(ax, units, edge_lw_fill=0.2):
    """
    설비 유닛 내부 색상 채우기
    
    Args:
        ax: matplotlib axes
        units: 설비 유닛 리스트
        edge_lw_fill: 셀 테두리 두께
    """
    for u in units:
        for (x, y) in u["cells"]:
            ax.fill_between([x, x + 1], y, y + 1,
                            color=u["color"], edgecolor='k',
                            linewidth=edge_lw_fill, zorder=2)


def draw_unit_outlines(ax, units, lw=2.0, color='k', z=6):
    """
    설비 유닛 외곽선 그리기
    
    Args:
        ax: matplotlib axes
        units: 설비 유닛 리스트
        lw: 선 두께
        color: 선 색상
        z: z-order
    """
    for u in units:
        outline = _build_outline_segments(u["cells"])
        for (x0, y0), (x1, y1) in outline:
            ax.plot([x0, x1], [y0, y1], linewidth=lw, color=color, zorder=z)


def _norm_edge(p0, p1):
    """엣지 정규화 (모듈 레벨 함수)"""
    return tuple(sorted((p0, p1)))


def draw_unit_seams(ax, units, lw=1.2, color='dimgray', z=5):
    """
    인접 설비 간 경계선 그리기
    
    Args:
        ax: matplotlib axes
        units: 설비 유닛 리스트
        lw: 선 두께
        color: 선 색상
        z: z-order
    
    동작:
        두 유닛이 공유하는 변을 찾아 경계선으로 표시합니다.
    """
    # 각 유닛의 엣지 집합 계산
    unit_edges = []
    for uid, u in enumerate(units):
        edges = set()
        for (x, y) in u["cells"]:
            e1 = _norm_edge((x, y), (x + 1, y))
            e2 = _norm_edge((x + 1, y), (x + 1, y + 1))
            e3 = _norm_edge((x + 1, y + 1), (x, y + 1))
            e4 = _norm_edge((x, y + 1), (x, y))
            edges.update([e1, e2, e3, e4])
        unit_edges.append(edges)

    # 유닛 쌍 간 공유 엣지 그리기
    n = len(units)
    for i in range(n):
        for j in range(i + 1, n):
            shared = unit_edges[i].intersection(unit_edges[j])
            if not shared:
                continue
            for (p0, p1) in shared:
                (x0, y0), (x1, y1) = p0, p1
                ax.plot([x0, x1], [y0, y1], linewidth=lw, color=color, zorder=z)
