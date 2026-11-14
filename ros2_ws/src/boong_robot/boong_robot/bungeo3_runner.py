"""bungeoppang3 공정을 start_bake / bake_done 토픽으로 구동하고 진행을 웹 단계로 변환."""
import threading
import time

from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import Bool, Int32, String

from .bungeo3 import (PACK_DETAIL, PACK_SEC_DEFAULT, STAGE_SECONDS, batches, estimated_stage, progress_for, scene_state_for, start_command,
                      step_for, to_fillings)


class Bungeo3Runner:
    def __init__(self, node, timeout_sec: float = 1800.0, stage_seconds=None, scene=None):
        self.node = node
        self.scene = scene  # RViz 마커 (/boong/scene). 없으면 생략
        self.timeout = timeout_sec
        self.stage_seconds = stage_seconds or STAGE_SECONDS
        self.group = ReentrantCallbackGroup()  # execute 콜백이 도는 동안에도 구독이 처리되도록
        self._done = threading.Event()
        self._ok = False
        self._stage = None  # bungeoppang3가 stage를 보내오면 채워짐
        self._stage_seen = False
        self.pub = node.create_publisher(String, "/bungeoppang/start_bake", 10)
        self.estop_pub = node.create_publisher(Bool, "/bungeoppang/estop", 10)
        node.create_subscription(Bool, "/bungeoppang/bake_done", self._on_done, 10, callback_group=self.group)
        node.create_subscription(Int32, "/bungeoppang/stage", self._on_stage, 10, callback_group=self.group)

    def _on_done(self, msg):
        self._ok = bool(msg.data)
        self._done.set()

    def _on_stage(self, msg):
        self._stage, self._stage_seen = int(msg.data), True

    def set_estop(self, stop: bool):
        self.estop_pub.publish(Bool(data=stop))

    def run(self, flavor: str, qty: int, on_step, is_cancelled=lambda: False, pack_sec: float = PACK_SEC_DEFAULT):
        """주문 1건 실행. on_step(web_step, detail, piece_index, progress). 실패 시 RuntimeError.

        공정(bake_done)이 끝나면 포장 단계를 pack_sec초 보여준 뒤 반환한다 (반환 = 웹 '픽업 대기')."""
        groups = batches(to_fillings(flavor, qty))
        made = 0
        for bi, batch in enumerate(groups):
            self._done.clear()
            self._stage, self._stage_seen = None, False
            self.pub.publish(String(data=start_command(batch)))
            self.node.get_logger().info(f"▶ bungeoppang3 start_bake: {start_command(batch)}")
            t0 = time.monotonic()
            shown = None
            if self.scene:
                self.scene.set_state("empty", flavor)
            while not self._done.wait(0.5):
                if is_cancelled():
                    self.set_estop(True)
                    raise RuntimeError("취소됨")
                el = time.monotonic() - t0
                if el > self.timeout:
                    raise RuntimeError("bungeoppang3 응답 없음 (bake_done 타임아웃) — 공정 노드가 실행 중인지 확인")
                stage = self._stage if self._stage_seen else estimated_stage(el, self.stage_seconds)
                step, detail = step_for(stage)
                if self.scene and stage != shown:
                    self.scene.set_state(scene_state_for(stage), flavor)
                    shown = stage
                on_step(step, detail, made + 1, progress_for(stage, bi, len(groups)))
            if not self._ok:
                raise RuntimeError("로봇 안전 정지 (bake_done=false) — bungeoppang3 터미널의 [안전 정지] 로그 확인")
            made += len(batch)
        self._pack(flavor, qty, on_step, pack_sec, is_cancelled)

    def _pack(self, flavor, qty, on_step, pack_sec, is_cancelled):
        """포장 단계: 봉투에 담는 것처럼 pack_sec초 동안 웹 '포장'을 유지 (로봇 동작 없음)."""
        if self.scene:
            self.scene.set_state("bagged", flavor)
        self.node.get_logger().info(f"📦 포장 {pack_sec:.0f}초 → 픽업 대기")
        end = time.monotonic() + max(pack_sec, 0.0)
        while True:
            on_step("packed", PACK_DETAIL, qty, 0.95)
            left = end - time.monotonic()
            if left <= 0 or is_cancelled():
                return
            time.sleep(min(0.5, left))
