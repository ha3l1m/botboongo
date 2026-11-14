"""bungeoppang3 공정 노드 대역 (테스트용): start_bake를 받으면 stage를 0→8 내보내고 bake_done 발행.

실제 공정(bake_sequence --serve)이 아직 /bungeoppang/start_bake를 받지 못할 때,
웹 → rosbridge → order_manager → action → 브리지 전체 흐름을 로봇·RViz 없이 확인하는 용도.
  ros2 run boong_robot bungeo3_sim --ros-args -p speed:=0.2    # speed 작을수록 빠름
  ros2 run boong_robot bungeo3_sim --ros-args -p fail:=true    # 안전정지 재현
"""
import threading
import time

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Bool, Int32, String

from .bungeo3 import STAGE_SECONDS


class Bungeo3Sim(Node):
    def __init__(self):
        super().__init__("bungeo3_sim")
        self.declare_parameter("speed", 0.2)
        self.declare_parameter("fail", False)
        self.stop = False
        self.stage_pub = self.create_publisher(Int32, "/bungeoppang/stage", 10)
        self.done_pub = self.create_publisher(Bool, "/bungeoppang/bake_done", 10)
        self.create_subscription(String, "/bungeoppang/start_bake", self.on_start, 10)
        self.create_subscription(Bool, "/bungeoppang/estop", lambda m: setattr(self, "stop", m.data), 10)
        self.get_logger().info("bungeoppang3 대역 시작 (/bungeoppang/start_bake 대기)")

    def on_start(self, msg):
        threading.Thread(target=self.bake, args=(msg.data,), daemon=True).start()

    def bake(self, cmd):
        speed = self.get_parameter("speed").value
        self.get_logger().info(f"🔥 굽기 시작: {cmd}")
        for stage, sec in STAGE_SECONDS.items():
            self.stage_pub.publish(Int32(data=stage))
            t_end = time.monotonic() + sec * speed
            while time.monotonic() < t_end:
                if self.stop:
                    self.done_pub.publish(Bool(data=False))
                    return
                time.sleep(0.1)
        self.done_pub.publish(Bool(data=not self.get_parameter("fail").value))


def main():
    rclpy.init()
    node = Bungeo3Sim()
    ex = MultiThreadedExecutor()
    ex.add_node(node)
    try:
        ex.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
