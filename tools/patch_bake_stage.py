#!/usr/bin/env python3
"""SujinJi bake_sequence_node.py 에 공정 번호 발행(/bungeoppang/stage, Int32)을 추가하는 로컬 패치 (v2).

웹 주문 화면의 단계를 추정 시간이 아니라 실제 공정 진행에 맞추기 위함.
- 공정 0 (홈 이동 · 비커로 접근)           → 웹 "접수"
- 공정 1 (1차 반죽): **비커를 잡은 직후**부터 → 웹 "반죽"   (v1은 1차 반죽 시작 시점이었음)
- 공정 2~8: 각 단계 시작 때
원본을 건드리지 않고 로컬 복사본에만 적용하며, 원본/v1/v2 어느 상태에서 실행해도 안전하다.

  python3 tools/patch_bake_stage.py ~/bungeoppang3_ws/src/bungeoppang2/bungeoppang2_yammy/bake_sequence_node.py
"""
import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
src = path.read_text(encoding="utf-8")

MARK_V2 = "# stage-patch v2"
PICK_ANCHOR = '             "비커 손잡이", obj="kettle", side=P.CUP_APPROACH)\n'
AFTER_PICK = (
    '        if tag == "1차 반죽":   # stage-patch v2: 비커를 잡은 뒤부터 웹 "반죽" 단계\n'
    "            stage_pub.publish(Int32(data=1))\n"
)
V1_LINE = "        if do(1):\n            stage_pub.publish(Int32(data=1))\n"

if MARK_V2 in src:
    print("이미 v2 패치됨 — 변경 없음")
    sys.exit(0)

has_v1 = "/bungeoppang/stage" in src

if not has_v1:
    # --- 원본: import + 발행자 + 단계별 발행 ---
    imp = "from std_msgs.msg import Bool, String\n"
    if imp not in src:
        sys.exit("패치 실패: 'from std_msgs.msg import Bool, String' 줄을 못 찾음 (예상한 버전이 아님)")
    src = src.replace(imp, "from std_msgs.msg import Bool, Int32, String\n", 1)
    anchor = '    done_pub = grip_node.create_publisher(Bool, "/bungeoppang/bake_done", 10)\n'
    if anchor not in src:
        sys.exit("패치 실패: done_pub 줄을 못 찾음")
    src = src.replace(anchor, anchor + '    stage_pub = grip_node.create_publisher(Int32, "/bungeoppang/stage", 10)   # 웹 단계 표시용: 현재 공정 번호 0~8\n', 1)
    for n in range(9):
        pat = f"        if do({n}):\n"
        if pat not in src:
            sys.exit(f"패치 실패: 'if do({n}):' 를 못 찾음")
        src = src.replace(pat, pat + f"            stage_pub.publish(Int32(data={n}))\n", 1)

# --- v1 → v2: 'if do(1)' 시작 시점 발행을 지우고, 비커를 잡은 직후로 옮김 ---
if V1_LINE in src:
    src = src.replace(V1_LINE, "        if do(1):\n", 1)
if PICK_ANCHOR not in src:
    sys.exit("패치 실패: pour_round 의 비커 pick 호출을 못 찾음 (예상한 버전이 아님)")
src = src.replace(PICK_ANCHOR, PICK_ANCHOR + AFTER_PICK, 1)

path.write_text(src, encoding="utf-8")
print(f"패치 완료(v2): {'v1에서 업그레이드' if has_v1 else '새로 적용'} → {path}")
