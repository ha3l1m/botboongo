#!/usr/bin/env python3
"""주문 → 로봇 흐름 감시창. 바뀔 때만 한 줄씩 시간순으로 출력한다.

  source /opt/ros/jazzy/setup.bash && source ~/boong_bridge_ws/install/setup.bash
  python3 ~/boong-web/tools/watch_flow.py

보는 토픽:
  /boong/orders            주문 큐 상태 (대기/굽는 중/완료/실패, 웹 단계)
  /bungeoppang/start_bake  주문 큐 → 로봇 공정 (굽기 시작 명령)
  /bungeoppang/stage       로봇 공정 번호 0~8 (웹 단계 매핑과 함께 표시)
  /bungeoppang/bake_done   공정 완료(True) / 안전 정지(False)
"""
import json
import time

STAGE_NAME = {0: "홈·비커 접근", 1: "1차 반죽(비커 잡음)", 2: "속재료", 3: "2차 반죽", 4: "뚜껑 닫기",
              5: "굽기 대기", 6: "돌림판+뒤집기", 7: "다시 뒤집기", 8: "펼치기+원위치"}
# bungeo3.py 의 STAGE_TO_STEP 와 같은 값 (웹 단계)
STAGE_WEB = {0: "접수", 1: "반죽", 2: "속 넣기", 3: "속 넣기", 4: "굽기", 5: "굽기", 6: "굽기", 7: "굽기", 8: "굽기"}
STEP_WEB = {"received": "접수", "batter": "반죽", "filling": "속 넣기", "baking": "굽기", "packed": "포장", "ready": "픽업 대기"}
FLAVOR = {"redbean": "팥", "cream": "슈크림"}
STATE = {"waiting": "대기", "baking": "굽는 중", "done": "완료", "failed": "실패"}


def stamp() -> str:
    return time.strftime("%H:%M:%S")


def line(icon: str, text: str) -> str:
    return f"{stamp()}  {icon} {text}"


def order_changes(prev: dict, rows: list) -> list:
    """/boong/orders 한 번 받을 때, 이전과 달라진 것만 문장으로. prev 는 (order_id, flavor) → (state, step)."""
    out = []
    for r in rows:
        key = (r.get("order_id"), r.get("flavor"))
        now = (r.get("state"), r.get("step"), r.get("queue_position"))
        if prev.get(key) == now:
            continue
        label = f"No.{r.get('number')} {FLAVOR.get(r.get('flavor'), r.get('flavor'))} x{r.get('qty')}"
        state = r.get("state")
        if state == "waiting":
            icon, msg = "📥", f"{label} 접수 · 대기 {r.get('queue_position')}번째"
        elif state == "baking":
            step = STEP_WEB.get(r.get("step"), r.get("step"))
            icon, msg = "🔥", f"{label} 진행 · 웹 단계 [{step}] · {r.get('detail', '')}"
        elif state == "done":
            icon, msg = "✅", f"{label} 완료 · 웹 단계 [픽업 대기]"
        else:
            icon, msg = "❌", f"{label} {STATE.get(state, state)} · {r.get('detail', '')}"
        out.append(line(icon, msg))
        prev[key] = now
    return out


def stage_text(n: int) -> str:
    return line("🤖", f"공정 {n} · {STAGE_NAME.get(n, '?')}  →  웹 [{STAGE_WEB.get(n, '?')}]")


def main():
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Bool, Int32, String

    rclpy.init()
    node = Node("watch_flow")
    prev: dict = {}
    last_stage = {"n": None}
    seen_done = {"v": None}

    def on_orders(msg):
        try:
            rows = json.loads(msg.data)
        except ValueError:
            return
        for text in order_changes(prev, rows):
            print(text, flush=True)

    def on_start(msg):
        print(line("▶️ ", f"로봇에 굽기 시작 명령: {msg.data}"), flush=True)
        last_stage["n"] = None

    def on_stage(msg):
        if msg.data != last_stage["n"]:
            last_stage["n"] = msg.data
            print(stage_text(msg.data), flush=True)

    def on_done(msg):
        print(line("🏁" if msg.data else "🛑", "공정 완료" if msg.data else "공정 안전 정지 (bake_done=False)"), flush=True)

    node.create_subscription(String, "/boong/orders", on_orders, 10)
    node.create_subscription(String, "/bungeoppang/start_bake", on_start, 10)
    node.create_subscription(Int32, "/bungeoppang/stage", on_stage, 10)
    node.create_subscription(Bool, "/bungeoppang/bake_done", on_done, 10)
    print("== 주문 → 로봇 흐름 감시 시작 (Ctrl+C 종료) ==", flush=True)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
