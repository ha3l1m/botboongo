"""주문 관리: 선입선출 Queue → action 서버에 1건씩 전달, 현황을 /boong/orders(JSON)로 발행.

웹앱(rosbridge) →  /boong/submit_order (srv)
웹앱 구독      ←  /boong/orders (std_msgs/String, JSON 배열)
"""
import json
import time
import uuid
from collections import deque

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from datetime import datetime, timezone

from std_msgs.msg import Bool, String

from boong_interfaces.action import MakeBungeoppang
from boong_interfaces.srv import ResolveAlert, SetEstop, SubmitOrder

KEEP_DONE = 20


class OrderManager(Node):
    def __init__(self):
        super().__init__("boong_order_manager")
        self.queue: deque[dict] = deque()
        self.current: dict | None = None
        self.done: deque[dict] = deque(maxlen=KEEP_DONE)
        self.pub = self.create_publisher(String, "/boong/orders", 10)
        self.create_service(SubmitOrder, "/boong/submit_order", self.on_submit)
        # 실패 주문을 붙잡고 ResolveAlert(retry/continue/cancel)를 기다릴지. 기본 꺼짐:
        # 공유 서버(server/rows.ts)는 state=failed 행을 보고 처리·재전송하므로 그대로 둔다.
        self.declare_parameter("hold_on_failure", False)
        self.estop = False
        self.alert: dict | None = None      # 이상 발생 시 {order_id, kind, ...}
        self.held: dict | None = None       # 이상으로 멈춘 주문 (ResolveAlert 대기)
        self.alert_pub = self.create_publisher(String, "/boong/robot_alert", 10)
        self.state_pub = self.create_publisher(String, "/boong/robot_state", 10)
        self.estop_pub = self.create_publisher(Bool, "/bungeoppang/estop", 10)
        self.create_service(ResolveAlert, "/boong/resolve_alert", self.on_resolve)
        self.create_service(SetEstop, "/boong/set_estop", self.on_estop)
        self.client = ActionClient(self, MakeBungeoppang, "/boong/make_bungeoppang")
        self.create_timer(0.5, self.tick)
        self.create_timer(1.0, self.publish)
        self.get_logger().info("주문 관리 시작: /boong/submit_order 대기 중")

    # ---- 주문 받기 --------------------------------------------------------
    def on_submit(self, req, res):
        if req.flavor not in ("redbean", "cream") or req.qty < 1:
            res.accepted, res.message = False, "단팥(redbean) / 슈크림(cream), 1개 이상만 가능해요"
            return res
        # 응답이 유실돼 웹이 다시 보내도 두 번 굽지 않게. 실패한 건은 재전송을 받는다.
        known = [*([self.current] if self.current else []), *self.queue, *self.done]
        if req.order_id and any(
            o["order_id"] == req.order_id and o["flavor"] == req.flavor and o["state"] != "failed" for o in known
        ):
            res.accepted, res.message = True, "이미 접수된 주문"
            return res
        order = {
            "order_id": req.order_id or str(uuid.uuid4()),
            "number": req.order_number,
            "flavor": req.flavor,
            "qty": req.qty,
            "state": "waiting",
            "step": "received",
            "detail": "",
            "progress": 0.0,
            "created_at": time.time(),
        }
        self.queue.append(order)
        res.accepted = True
        res.queue_position = len(self.queue) - (0 if self.current else 1)
        res.message = f"주문 접수 (대기 {res.queue_position})"
        self.get_logger().info(f"📥 No.{order['number']} {order['flavor']} x{order['qty']} → {res.message}")
        self.publish()
        return res

    # ---- 1건씩 굽기 -------------------------------------------------------
    def tick(self):
        if self.current or not self.queue or self.estop or self.alert:
            return
        if not self.client.server_is_ready():
            return
        self.current = self.queue.popleft()
        o = self.current
        o["state"] = "baking"
        goal = MakeBungeoppang.Goal(order_id=o["order_id"], order_number=o["number"], flavor=o["flavor"], qty=o["qty"])
        fut = self.client.send_goal_async(goal, feedback_callback=self.on_feedback)
        fut.add_done_callback(self.on_goal_response)

    def on_feedback(self, msg):
        if self.current:
            fb = msg.feedback
            self.current.update(step=fb.step, detail=fb.detail, progress=round(fb.progress, 2), piece=fb.piece_index)

    def on_goal_response(self, fut):
        handle = fut.result()
        if not handle.accepted:
            self.get_logger().warn("로봇이 주문을 거절 → 다시 대기열 앞으로")
            self.current["state"] = "waiting"
            self.queue.appendleft(self.current)
            self.current = None
            return
        handle.get_result_async().add_done_callback(self.on_result)

    def on_result(self, fut):
        res = fut.result().result
        o = self.current
        if not res.success and self.get_parameter("hold_on_failure").value:
            # 이상 → 주문을 붙잡고 웹에 알림. 웹 관제가 retry/continue/cancel 중 고를 때까지 대기
            o.update(state="paused", detail=res.message)
            self.held, self.current = o, None
            self.raise_alert(o, "gripper", "driver", res.message)
            self.publish()
            return
        o["state"] = "done" if res.success else "failed"
        o["step"] = "ready" if res.success else o["step"]
        o["detail"] = res.message
        self.done.appendleft(o)
        self.current = None
        self.get_logger().info(f"{'✅' if res.success else '❌'} No.{o['number']} {res.message}")
        self.publish()

    # ---- 이상 알림 · 관제 (웹 주문판) ---------------------------------------
    def raise_alert(self, order, kind, source, message):
        self.alert = {"order_id": order["order_id"], "kind": kind, "source": source, "message": message,
                      "at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
        self.alert_pub.publish(String(data=json.dumps(self.alert, ensure_ascii=False)))
        self.get_logger().warn(f"🚨 이상: {kind} — {message}")

    def on_resolve(self, req, res):
        o = self.held
        if not self.alert or not o or o["order_id"] != req.order_id:
            res.ok, res.message = False, "대기 중인 이상 알림이 없어요"
            return res
        if req.action == "retry":
            o.update(state="waiting", step="received", progress=0.0)
            self.queue.appendleft(o)
        elif req.action == "continue":
            o.update(state="done", step="ready")
            self.done.appendleft(o)
        elif req.action == "cancel":
            o.update(state="failed")
            self.done.appendleft(o)
        else:
            res.ok, res.message = False, "action은 retry | continue | cancel"
            return res
        self.held, self.alert = None, None
        res.ok, res.message = True, req.action
        self.publish()
        return res

    def on_estop(self, req, res):
        self.estop = bool(req.stop)
        self.estop_pub.publish(Bool(data=self.estop))   # bungeoppang3 쪽이 구독하면 즉시 반영
        self.get_logger().warn("🛑 비상 정지" if self.estop else "▶ 재개")
        res.ok = True
        self.publish_state()
        return res

    def publish_state(self):
        mode = "estop" if self.estop else "paused" if self.alert else "running" if self.current else "idle"
        cur = (self.current or self.held or {}).get("order_id", "")
        connected = self.client.server_is_ready()
        self.state_pub.publish(String(data=json.dumps({"mode": mode, "current_order_id": cur, "connected": connected})))

    # ---- 현황 -------------------------------------------------------------
    def publish(self):
        rows = []
        if self.current:
            rows.append({**self.current, "queue_position": 0})
        for i, o in enumerate(self.queue, start=1):
            rows.append({**o, "queue_position": i})
        rows += [{**o, "queue_position": -1} for o in self.done]
        if self.held:
            rows.insert(0, {**self.held, "queue_position": 0})
        self.pub.publish(String(data=json.dumps(rows, ensure_ascii=False)))
        self.publish_state()


def main():
    rclpy.init()
    node = OrderManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
