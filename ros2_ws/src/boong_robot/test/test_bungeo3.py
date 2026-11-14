"""bungeoppang3 브리지 순수 로직 검증 (ROS 불필요): pytest ros2_ws/src/boong_robot/test"""
import pytest

from boong_robot.bungeo3 import (scene_state_for, STAGE_SECONDS, batches, estimated_stage, progress_for, start_command,
                                 step_for, to_fillings)


def test_orders_split_into_mold_pairs():
    assert batches(to_fillings("redbean", 3)) == [["팥", "팥"], ["팥"]]
    assert start_command(["팥", "슈크림"]) == "팥,슈크림"


def test_unsupported_flavor_rejected():
    with pytest.raises(ValueError):
        to_fillings("choco", 1)


def test_stage_to_web_steps_monotonic():
    order = ["received", "batter", "filling", "baking"]
    steps = [step_for(s)[0] for s in range(9)]
    assert [order.index(s) for s in steps] == sorted(order.index(s) for s in steps)
    assert steps[0] == "received" and steps[1] == "batter" and steps[-1] == "baking"  # 포장은 공정 뒤에 브리지가 붙인다


def test_estimated_stage_walks_all_stages():
    assert estimated_stage(0) == 0
    assert estimated_stage(sum(STAGE_SECONDS.values()) + 5) == 8
    assert estimated_stage(STAGE_SECONDS[0] + 1) == 1


def test_progress_bounded_and_increasing():
    p = [progress_for(s, 0, 2) for s in range(9)]
    assert p == sorted(p) and p[-1] < 1.0 and progress_for(8, 1, 2) <= 0.99


def test_scene_states_follow_process():
    states = [scene_state_for(s) for s in range(9)]
    assert states[1] == "batter" and states[2] == "filling" and states[5] == "baked" and states[8] == "flipped"
