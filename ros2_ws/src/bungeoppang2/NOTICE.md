# 출처 · 수정 내역

## 출처
- 원본: [SujinJi/bungeoppang3](https://github.com/SujinJi/bungeoppang3) (`main`, `012b575`, 2026-11-13) — 작성자 SujinJi
- 라이선스: 원본 README 표기(MIT), 원본 README 는 이 폴더의 `README.md`
- 이름: 저장소는 `bungeoppang3`, ROS 패키지는 `bungeoppang2` (원본 그대로)

## 수정한 파일 (2개)
| 파일 | 변경 |
|---|---|
| `bungeoppang2_yammy/bake_sequence_node.py` | 원본 `main` 은 내용이 바뀌어 있어 같은 저장소의 `47381bb` 버전(실행 코드)으로 교체하고, 공정 번호(`/bungeoppang/stage`) 발행을 추가 |
| `bungeoppang2_yammy/positions.py` | 원본 `main` 의 `bake_sequence_node.py` 내용(최신 위치값)으로 교체 |

나머지는 원본 그대로입니다.

## 원본이 고쳐지면
이 폴더를 원본으로 바꾼 뒤 아래 두 명령으로 확인·적용하세요.
```bash
python3 tools/check_bungeo3_names.py ros2_ws/src/bungeoppang2/bungeoppang2_yammy
python3 tools/patch_bake_stage.py ros2_ws/src/bungeoppang2/bungeoppang2_yammy/bake_sequence_node.py
```
