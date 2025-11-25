"""
================================================================================
layout_visualizer.py - 설비 배치 시각화 도구
================================================================================
설비 배치를 시뮬레이션 없이 빠르게 시각화합니다.

사용법:
    python layout_visualizer.py

기능:
    - 30개 가능한 설비 위치 표시
    - 설비 배치 시각화 (공정별 색상 구분)
    - Warehouse, Stocker 위치 표시
    - 입력/출력 포트 표시
================================================================================
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# ================================================================================
# 상수 정의
# ================================================================================
# 맵 크기
MAP_WIDTH = 60
MAP_HEIGHT = 20

# 설비 크기
MACHINE_WIDTH = 3
MACHINE_HEIGHT = 2

# 포트 오프셋
PORT_OFFSET = 2

# Warehouse, Stocker 위치
WAREHOUSE_XY = (4, 10)
STOCKER_XY = (56, 10)

# 30개 가능한 설비 좌표
AVAILABLE_POSITIONS = [
    (14, 3), (14, 5), (14, 7), (14, 13), (14, 15), (14, 17),
    (22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17),
    (30, 3), (30, 5), (30, 7), (30, 13), (30, 15), (30, 17),
    (38, 3), (38, 5), (38, 7), (38, 13), (38, 15), (38, 17),
    (46, 3), (46, 5), (46, 7), (46, 13), (46, 15), (46, 17),
]

# 공정별 색상
STAGE_COLORS = {
    "A": "#FF6B6B",  # 빨강 (산화)
    "B": "#4ECDC4",  # 청록 (노광)
    "C": "#45B7D1",  # 파랑 (식각)
    "D": "#96CEB4",  # 초록 (증착)
    "E": "#FFEAA7",  # 노랑 (계측)
}

STAGE_NAMES = {
    "A": "산화",
    "B": "노광", 
    "C": "식각",
    "D": "증착",
    "E": "계측",
}


# ================================================================================
# 시각화 함수
# ================================================================================
def visualize_layout(machine_positions: dict, title: str = "설비 배치도"):
    """
    설비 배치 시각화
    
    Args:
        machine_positions: {"A": [(x,y), ...], "B": [...], ...}
        title: 그래프 제목
    """
    fig, ax = plt.subplots(1, 1, figsize=(16, 8))
    
    # 배경 설정
    ax.set_xlim(0, MAP_WIDTH)
    ax.set_ylim(0, MAP_HEIGHT)
    ax.set_aspect('equal')
    ax.set_facecolor('#f0f0f0')
    ax.grid(True, alpha=0.3)
    
    # 가능한 위치 표시 (빈 슬롯)
    used_positions = set()
    for positions in machine_positions.values():
        used_positions.update(positions)
    
    for pos in AVAILABLE_POSITIONS:
        if pos not in used_positions:
            # 빈 슬롯 - 점선 사각형
            rect = patches.Rectangle(
                (pos[0] - MACHINE_WIDTH/2, pos[1] - MACHINE_HEIGHT/2),
                MACHINE_WIDTH, MACHINE_HEIGHT,
                linewidth=1, edgecolor='gray', facecolor='white',
                linestyle='--', alpha=0.5
            )
            ax.add_patch(rect)
    
    # 설비 그리기
    for stage, positions in machine_positions.items():
        color = STAGE_COLORS.get(stage, "gray")
        for idx, (cx, cy) in enumerate(positions):
            # 설비 본체
            rect = patches.Rectangle(
                (cx - MACHINE_WIDTH/2, cy - MACHINE_HEIGHT/2),
                MACHINE_WIDTH, MACHINE_HEIGHT,
                linewidth=2, edgecolor='black', facecolor=color, alpha=0.8
            )
            ax.add_patch(rect)
            
            # 설비 이름
            ax.text(cx, cy, f"{stage}-{idx+1}", ha='center', va='center', 
                   fontsize=9, fontweight='bold')
            
            # 입력 포트 (왼쪽, 파란 점)
            ax.plot(cx - PORT_OFFSET, cy, 'b^', markersize=6)
            
            # 출력 포트 (오른쪽, 빨간 점)
            ax.plot(cx + PORT_OFFSET, cy, 'rv', markersize=6)
    
    # Warehouse 표시
    wh_rect = patches.Rectangle(
        (WAREHOUSE_XY[0] - 1.5, WAREHOUSE_XY[1] - 1.5), 3, 3,
        linewidth=2, edgecolor='black', facecolor='#A29BFE', alpha=0.8
    )
    ax.add_patch(wh_rect)
    ax.text(WAREHOUSE_XY[0], WAREHOUSE_XY[1], "WH", ha='center', va='center',
           fontsize=10, fontweight='bold')
    
    # Stocker 표시
    stk_rect = patches.Rectangle(
        (STOCKER_XY[0] - 1.5, STOCKER_XY[1] - 1.5), 3, 3,
        linewidth=2, edgecolor='black', facecolor='#FD79A8', alpha=0.8
    )
    ax.add_patch(stk_rect)
    ax.text(STOCKER_XY[0], STOCKER_XY[1], "STK", ha='center', va='center',
           fontsize=10, fontweight='bold')
    
    # 범례
    legend_elements = [
        patches.Patch(facecolor=STAGE_COLORS["A"], edgecolor='black', label=f'A ({STAGE_NAMES["A"]})'),
        patches.Patch(facecolor=STAGE_COLORS["B"], edgecolor='black', label=f'B ({STAGE_NAMES["B"]})'),
        patches.Patch(facecolor=STAGE_COLORS["C"], edgecolor='black', label=f'C ({STAGE_NAMES["C"]})'),
        patches.Patch(facecolor=STAGE_COLORS["D"], edgecolor='black', label=f'D ({STAGE_NAMES["D"]})'),
        patches.Patch(facecolor=STAGE_COLORS["E"], edgecolor='black', label=f'E ({STAGE_NAMES["E"]})'),
        patches.Patch(facecolor='#A29BFE', edgecolor='black', label='Warehouse'),
        patches.Patch(facecolor='#FD79A8', edgecolor='black', label='Stocker'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=9)
    
    # 설비 개수 표시
    counts_text = "설비 개수: " + ", ".join([f"{s}={len(p)}대" for s, p in machine_positions.items()])
    total = sum(len(p) for p in machine_positions.values())
    counts_text += f" (총 {total}대)"
    ax.set_xlabel(counts_text, fontsize=11)
    
    # 제목
    ax.set_title(title, fontsize=14, fontweight='bold')
    
    # 축 레이블
    ax.set_ylabel("Y (m)", fontsize=10)
    
    plt.tight_layout()
    plt.show()


def print_layout_info(machine_positions: dict):
    """배치 정보 출력"""
    print("\n" + "="*60)
    print("설비 배치 정보")
    print("="*60)
    
    total = 0
    for stage in ["A", "B", "C", "D", "E"]:
        positions = machine_positions.get(stage, [])
        print(f"\n{stage}공정 ({STAGE_NAMES[stage]}): {len(positions)}대")
        for idx, pos in enumerate(positions):
            input_port = (pos[0] - PORT_OFFSET, pos[1])
            output_port = (pos[0] + PORT_OFFSET, pos[1])
            print(f"  {stage}-{idx+1}: 중심{pos}, 입력포트{input_port}, 출력포트{output_port}")
        total += len(positions)
    
    print(f"\n총 설비 수: {total}대")
    print("="*60)


# ================================================================================
# 메인
# ================================================================================
if __name__ == "__main__":
    
    # ===== 배치 설정 (여기서 수정) =====
    
    # 배치안 1: 순차 배치 (A: 5, B: 8, C: 6, D: 6, E: 5 = 30대)
    machine_positions = {
        "A": [(14, 3), (14, 5), (14, 7), (14, 13), (14, 15)],  # 5대
        "B": [(22, 3), (22, 5), (22, 7), (22, 13), (22, 15), (22, 17), (30, 3), (30, 5)],  # 8대
        "C": [(30, 7), (30, 13), (30, 15), (30, 17), (38, 3), (38, 5)],  # 6대
        "D": [(38, 7), (38, 13), (38, 15), (38, 17), (46, 3), (46, 5)],  # 6대
        "E": [(46, 7), (46, 13), (46, 15), (46, 17), (14, 17)],  # 5대 (마지막 1대는 x=14에)
    }
    
    # 배치 정보 출력
    print_layout_info(machine_positions)
    
    # 시각화
    visualize_layout(machine_positions, "설비 배치안 1: 순차 배치")
