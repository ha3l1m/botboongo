# 봇붕 (BOTBOONG) — 붕어빵 로봇 주문 시스템

고객 앱 → 어드민 → 주문 큐 → 두산 협동로봇(E0509, RViz 에뮬레이터)까지 한 흐름으로 연결한 프로젝트입니다.

```
[고객앱 / 어드민 (React)] ─/api─▶ [공유 서버 :8787] ─ws─▶ [rosbridge :9090] ─▶ [주문 큐 order_manager]
                                                                                  │ action
                                                                                  ▼
                                                    [robot_action_server (backend:=bungeoppang3)]
                                                                                  │ /bungeoppang/start_bake
                                                                                  ▼
                                                     [붕어빵 공정 노드 (bungeoppang3)] ▶ RViz / 에뮬레이터
```

| 폴더 | 내용 |
|---|---|
| `src/` | 고객 앱 · 어드민 (React + three.js) |
| `server/` | 공유 서버 (주문·재고 저장, rosbridge 연결) |
| `ros2_ws/src/boong_interfaces` | 주문·관제 서비스/액션 정의 |
| `ros2_ws/src/boong_robot` | 주문 큐, 로봇 액션 서버, 공정 브리지(`bungeo3*`), RViz 마커 |
| `tools/` | 공정 번호 패치, 이름 검사, 흐름 감시(`watch_flow.py`) |
| `docker/` | 두산 드라이버 + 에뮬레이터 + rosbridge 컨테이너 |
| `docs/` | 설계·계획 문서 (`docs/plans/2026-11-14-bungeoppang3-rviz-link.md` 에 연결 구조) |

## 로봇 공정
로봇 공정은 별도 저장소 [SujinJi/bungeoppang3](https://github.com/SujinJi/bungeoppang3) 의 `bungeoppang2` 패키지를 사용합니다.
이 저장소의 브리지(`backend:=bungeoppang3`)는 그 공정과 `/bungeoppang/start_bake`, `/bungeoppang/bake_done`, `/bungeoppang/stage` 토픽으로 연결됩니다.

- 공정 번호 신호(`/bungeoppang/stage`)는 `python3 tools/patch_bake_stage.py <bake_sequence_node.py>` 로 로컬 복사본에 추가합니다 (원본은 수정하지 않습니다).
- 공정 코드가 쓰는 이름이 모두 정의돼 있는지는 `python3 tools/check_bungeo3_names.py <bungeoppang2_yammy 폴더>` 로 미리 확인할 수 있습니다.

주문 화면 단계 ↔ 공정 번호

| 공정 | 화면 단계 |
|---|---|
| 0 홈 이동 · 비커 접근 | 접수 |
| 1 1차 반죽 (비커를 잡은 직후부터) | 반죽 |
| 2 속재료 · 3 2차 반죽 | 속 넣기 |
| 4 뚜껑 · 5 굽기 · 6 돌림판+뒤집기 · 7 다시 뒤집기 · 8 펼치기 | 굽기 |
| 공정 끝 → `pack_sec`초(기본 6) | 포장 (공정에 포장이 없어 브리지가 만든 단계) |
| 그 뒤 | 픽업 대기 |

## 실행 (터미널 6개)
```bash
# 1 RViz + 에뮬레이터 (bungeoppang2 패키지 필요)
ros2 launch bungeoppang2 sim.launch.py bake:=false
# 2 공정 노드 (서빙 모드)
ros2 run bungeoppang2 bake_sequence --serve
# 3 주문 큐 + rosbridge
ros2 launch boong_robot boong.launch.py backend:=bungeoppang3      # 대역: sim:=true, 포장 시간: pack_sec:=6.0
# 4 공유 서버
npm run server
# 5 웹 (.env.local 에 VITE_ROBOT_MODE=ros, VITE_ADMIN_PIN=<4~8자리>)
npm run dev
# 6 흐름 감시 (선택)
python3 tools/watch_flow.py
```
로봇 없이 화면만 볼 때는 `.env.local` 에서 `VITE_ROBOT_MODE=mock` (기본) 으로 두면 브라우저 안에서 타이머로 진행됩니다.

## 개발
```bash
npm install
npm test            # 웹 테스트
npm run build       # 타입 검사 + 빌드
```

## 보안 · 시연용 한계
이 프로젝트는 **로컬 시연용**입니다. 공개 서버에 그대로 배포하지 마세요.
- 공유 서버(`server/`)는 `127.0.0.1` 에만 바인딩되고, `/api` 는 인증이 없습니다. `npm run dev -- --host` 로 웹을 외부에 열면 같은 네트워크의 누구나 `/api` 를 호출할 수 있습니다.
- 관리자 화면의 PIN(`VITE_ADMIN_PIN`)은 브라우저에서만 확인합니다. 빌드된 JS 에 값이 들어가므로 보안 수단이 아니라 임시 잠금입니다.
- 로봇 컨트롤러 IP, 네트워크 대역 등 현장 정보는 `docker/.env` (git 제외)에 두고, 문서에는 `<...>` 자리표시자만 둡니다.
- `.env.local`, `.boong-data/`(서버 저장 데이터)는 `.gitignore` 로 제외돼 있습니다.
