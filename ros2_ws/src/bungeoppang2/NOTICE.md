# 출처 · 수정 내역

이 폴더는 [SujinJi/bungeoppang3](https://github.com/SujinJi/bungeoppang3) 의 `bungeoppang2` 패키지(붕어빵 굽기 로봇 공정)를
팀원이 한 번에 클론해서 쓸 수 있도록 포함한 것입니다. 작성자: SujinJi. 원본 README 는 이 폴더의 `README.md` 에 그대로 있고,
라이선스는 원본 README 의 표기(MIT)를 따릅니다.

- 기준: 원본 `main` (`012b575`, 2026-11-13)
- 이 사본에서 달라진 파일

| 파일 | 변경 |
|---|---|
| `bungeoppang2_yammy/bake_sequence_node.py` | 원본 `main` 에는 11/13 16:04 커밋(`ab9d2e6`)에서 다른 내용이 들어가 있어, 같은 저장소의 `47381bb` 버전(실행 코드: `main()`, `--serve`, `start_bake` 구독, `bake_done` 발행)을 사용. 여기에 `/bungeoppang/stage`(공정 번호 0~8) 발행 패치(`tools/patch_bake_stage.py`, v2)를 적용 |
| `bungeoppang2_yammy/positions.py` | 원본 `main` 의 `bake_sequence_node.py` 내용(704줄, `END_GRIP_CLEAR` 등 최신 위치값)을 사용 |

나머지 파일은 원본 그대로입니다. 원본 저장소가 고쳐지면 이 폴더를 원본으로 교체하고,
`python3 tools/check_bungeo3_names.py ros2_ws/src/bungeoppang2/bungeoppang2_yammy` 로 이름 누락이 없는지 확인한 뒤
`python3 tools/patch_bake_stage.py ros2_ws/src/bungeoppang2/bungeoppang2_yammy/bake_sequence_node.py` 를 다시 적용하세요.
