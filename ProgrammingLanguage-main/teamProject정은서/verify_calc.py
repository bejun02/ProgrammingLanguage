# 이론적 최대 생산량 계산
SIM_TIME = 1296000  # 15일

# 설비 대수
machine_counts = {'A': 5, 'B': 9, 'C': 6, 'D': 5, 'E': 5}

print('=== 병목 공정별 최대 쌍 생산량 ===')
for stage in ['A', 'B', 'C', 'D', 'E']:
    # 1쌍당 필요 처리시간 (ProdA cycle0 + cycle1 + ProdB cycle0 + cycle1)
    if stage == 'A':
        total_time = (15+15+5+10) * 60  # 2700초
    elif stage == 'B':
        total_time = (15+15+40+10) * 60  # 4800초
    elif stage == 'C':
        total_time = (15+15+25+5) * 60  # 3600초
    elif stage == 'D':
        total_time = (15+15+2+10) * 60  # 2520초
    elif stage == 'E':
        total_time = (15+15+5+15) * 60  # 3000초
    
    max_pairs = SIM_TIME * machine_counts[stage] / total_time
    print(f'{stage}: 1쌍당 {total_time}초, 설비{machine_counts[stage]}대 -> 최대 {max_pairs:.0f} 쌍')

print()
print('=== 결론 ===')
B_max = SIM_TIME * 9 / 4800
print(f'B공정 병목: 최대 {B_max:.0f} 쌍')
print(f'teamProject수정중: 2,086 쌍 ({2086/B_max*100:.1f}%)')
print(f'teamProject정은서: 3,226 쌍 ({3226/B_max*100:.1f}%)')

if 3226 > B_max:
    print()
    print('!!! 경고: 3,226쌍은 이론적 최대치를 초과합니다 !!!')
    print('=> 시뮬레이션 로직에 문제가 있을 가능성이 높습니다')
