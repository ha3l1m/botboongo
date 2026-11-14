# bungeoppang3(RViz 공정) ↔ 고객앱·어드민 연결

```
고객앱/어드민 ─roslib─▶ rosbridge :9090 ─▶ order_manager(큐·이상알림·비상정지)
                                              │ action /boong/make_bungeoppang
                                              ▼
                                     robot_action_server (backend:=bungeoppang3)
                                              │ /bungeoppang/start_bake  "팥,슈크림"   (최대 2개/틀 2개)
                                              ▼
                                     bungeoppang3 공정 노드 → RViz / 에뮬레이터
                              ◀── /bungeoppang/bake_done (Bool), /bungeoppang/stage (Int32, 선택)
```

## 웹 연동은 팀의 공유 서버를 쓴다
`npm run server`(server/) 가 `/boong/submit_order` · `/boong/orders` 로 ROS와 통신하고 웹은 `/api` 를 폴링한다.
이 문서의 ROS 쪽(`backend:=bungeoppang3`)은 그 인터페이스를 그대로 지키므로 서버 수정이 필요 없다.
웹 `.env.local`: `VITE_ROBOT_MODE=ros`, `VITE_ADMIN_PIN=<4~8자리>`.

## 실행 (RViz)
1. 터미널 1 — SujinJi 쪽: `ros2 launch bungeoppang2 sim.launch.py bake:=false` 후 공정 노드를 `--serve` 로 실행
2. 터미널 2 — 우리 쪽: `ros2 launch boong_robot boong.launch.py backend:=bungeoppang3`
3. 터미널 3: `npm run server` (다른 PC면 `ROSBRIDGE_URL=ws://<로봇PC IP>:9090 npm run server`), 터미널 4: `npm run dev`

로봇/RViz 없이 흐름만 확인: `ros2 launch boong_robot boong.launch.py backend:=bungeoppang3 sim:=true`
(`bungeo3_sim` 이 공정 대역으로 start_bake → stage 0~8 → bake_done 을 흉내 냄. `-p fail:=true` 로 안전정지 재현)

## 웹 단계 매핑 (bungeoppang3 공정 번호 → 고객앱 단계)
| 공정 | 웹 단계 |
|---|---|
| 0 홈 이동 · 비커로 접근 | received (접수) — 비커를 잡기 전까지 |
| 1 1차 반죽 (비커를 잡은 직후부터) | batter (반죽 붓는 중) |
| 2 속재료 · 3 2차 반죽 | filling (속 넣는 중) |
| 4 뚜껑 · 5 굽기 · 6 돌림판+뒤집기 · 7 다시 뒤집기 | baking (굽는 중) |
| 8 펼치기+원위치 | baking (굽기에 포함) |
| bake_done=true 직후 `pack_sec`초(기본 6) | packed (포장) — SujinJi 공정에 포장이 없어 브리지가 만든 단계 |
| 그 뒤 | ready (픽업 대기) |

## 이상 알림 · 관제
- 실패(`bake_done=false`, 타임아웃) → 기본은 order_manager 행에 `state: failed` (공유 서버가 처리·재전송). `hold_on_failure:=true` 이면 주문을 붙잡고 `/boong/robot_alert` 발행, `/boong/resolve_alert`(retry/continue/cancel)로 대응
- 어드민 버튼 → `/boong/resolve_alert` (retry=다시 굽기 / continue / cancel), 비상정지 → `/boong/set_estop`
- 명령이 ROS에 전달되지 않으면 화면 상단 빨간 배너로 알림 (로컬 화면만 정지로 바뀌고 실제 로봇은 안 멈추는 상황 방지)

## ⚠️ 알아둘 점 (공정 쪽)
1. **공정 노드는 서빙 모드(`bake_sequence --serve`)로 실행**해야 한다. `/bungeoppang/start_bake` 를 받아 굽고 끝나면 `/bungeoppang/bake_done` 을 낸다. 사용하는 공정 코드 버전에서 필요한 이름이 모두 있는지 `tools/check_bungeo3_names.py` 로 먼저 확인한다.
2. **`/bungeoppang/stage`(Int32, 공정 번호 0~8) 발행을 추가하면** 고객앱 단계가 실제 진행과 맞는다. 없으면 `bungeo3.py` 의 `STAGE_SECONDS` 추정 시간으로 진행(에뮬레이터 실측 후 조정).
3. **`/bungeoppang/estop`(Bool) 구독을 추가해야** 웹 비상정지가 공정을 실제로 멈춘다. 지금은 대기열 투입 중단 + 토픽 발행까지만.
4. 틀 2개 = 한 번에 2개. 3개 이상 주문은 2개씩 나눠 연속 실행. 맛은 팥/슈크림만(웹도 ros 모드에서 초코 주문 차단).
