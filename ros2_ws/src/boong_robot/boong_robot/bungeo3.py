"""bungeoppang3(SujinJi, RViz/에뮬레이터 공정)와 붕붕 웹앱을 잇는 브리지.

bungeoppang3 쪽 규약 (그 레포 README 기준):
  /bungeoppang/start_bake  (String)  "팥,슈크림"  ← 우리가 발행 (틀 2개라 한 번에 최대 2개)
  /bungeoppang/bake_done   (Bool)    True=완료 / False=안전정지  → 우리가 구독
  /bungeoppang/stage       (Int32)   현재 공정 번호 0~8        → 우리가 구독 (선택, 아직 그쪽에 없음)
  /bungeoppang/estop       (Bool)    True=정지                  ← 우리가 발행 (그쪽이 구독해야 반영됨)

stage 토픽이 없으면 STAGE_SECONDS 기준 시간 추정으로 웹 단계를 진행시킨다.
이 파일은 ROS에 의존하지 않는다 (단위 테스트 가능). 노드 연결은 bungeo3_runner.py.
"""
from typing import Callable, Iterable

# 웹 flavor → bungeoppang3 속재료 이름
FILLING_KO = {"redbean": "팥", "cream": "슈크림"}
MOLDS = 2  # 틀 개수 = 한 번에 굽는 수

# SujinJi 공정에는 포장·픽업이 없다. 공정이 끝나면 웹 "포장"을 이 시간(초) 보여준 뒤 "픽업 대기"로 넘긴다.
PACK_SEC_DEFAULT = 6.0
PACK_DETAIL = "봉투에 담는 중"

# bungeoppang3 공정 번호(README 표) → 웹 단계(src/domain/order.ts BAKE_STEPS)
STAGE_TO_STEP = {
    0: ("received", "홈 이동 · 비커 집으러 가는 중"),   # 비커를 잡기 전까지는 웹 "접수"
    1: ("batter", "1차 반죽 붓는 중"),            # 비커를 잡은 직후부터 웹 "반죽"
    2: ("filling", "속재료 넣는 중"),
    3: ("filling", "2차 반죽으로 덮는 중"),
    4: ("baking", "뚜껑 닫는 중"),
    5: ("baking", "굽는 중"),
    6: ("baking", "틀 돌리고 뒤집는 중"),
    7: ("baking", "다시 뒤집는 중"),
    8: ("baking", "틀 펼쳐서 꺼내는 중"),   # SujinJi 공정은 여기서 끝 → 포장·픽업은 브리지가 이어서 진행
}

# 공정 번호 → RViz 마커 상태 (boong_robot/scene.py 의 state: empty/batter/filling/covered/baked/flipped/bagged)
STAGE_TO_SCENE = {0: "empty", 1: "batter", 2: "filling", 3: "covered", 4: "covered",
                  5: "baked", 6: "flipped", 7: "flipped", 8: "flipped"}


def scene_state_for(stage: int) -> str:
    return STAGE_TO_SCENE[max(0, min(stage, max(STAGE_TO_SCENE)))]


# stage 토픽이 없을 때 쓰는 추정 소요(초). 에뮬레이터 실측 후 launch 파라미터로 덮어쓸 것.
STAGE_SECONDS = {0: 3, 1: 25, 2: 30, 3: 20, 4: 25, 5: 10, 6: 40, 7: 30, 8: 30}


def to_fillings(flavor: str, qty: int) -> list[str]:
    if flavor not in FILLING_KO or qty < 1:
        raise ValueError(f"지원하지 않는 주문: {flavor} x{qty}")
    return [FILLING_KO[flavor]] * qty


def batches(fillings: Iterable[str], size: int = MOLDS) -> list[list[str]]:
    items = list(fillings)
    return [items[i:i + size] for i in range(0, len(items), size)]


def start_command(batch: list[str]) -> str:
    return ",".join(batch)


def step_for(stage: int) -> tuple[str, str]:
    return STAGE_TO_STEP[max(0, min(stage, max(STAGE_TO_STEP)))]


def progress_for(stage: int, done_batches: int, total_batches: int) -> float:
    """주문 전체 진행률 0~1 (배치 단위 + 배치 내 공정 번호)."""
    within = (stage + 1) / (max(STAGE_TO_STEP) + 1)
    return min((done_batches + within) / max(total_batches, 1), 0.99)


def estimated_stage(elapsed: float, seconds: dict[int, float] = STAGE_SECONDS) -> int:
    """stage 토픽이 없을 때: 시작 후 경과 시간으로 현재 공정 번호 추정."""
    t = 0.0
    for stage in sorted(seconds):
        t += seconds[stage]
        if elapsed < t:
            return stage
    return max(seconds)


StepCb = Callable[[str, str, float], None]  # (web step, detail, progress)
