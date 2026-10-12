# Rust 110% 목표: 2026-10-12 개선 및 검증 보고서

상태: **목표 미달, 진행 중**. 같은 완료 작업의 `Rust 시간 / Forge 시간 >= 1.10`을 유지한다. 한 경로의 개선으로 다른 경로의 미달을 숨기거나 전체 완료를 선언하지 않는다.

## 유지한 철학과 이번 변경

C 기반 AOT, 코루틴 실행 모델, checked 바이트·범위 접근, arena 수명과 immutable snapshot을 유지했다. 문자열 builder의 내부 버퍼를 length-delimited로 다루어 각 append의 불필요한 NUL 저장을 제거했으며, `finish`는 여전히 독립 메모리에 복사하고 NUL을 붙인다. 매핑된 문자열·view append와 view matches의 여유 용량/범위 경로는 inline 처리하고 exported ABI 및 성장 fallback은 유지했다. 기존 바이너리 호출과 새 inline 호출을 경계·성장·snapshot·인수 단일 평가 테스트로 대조했다.

자가 호스팅 의미 검사는 지원 부분집합의 이름·타입·사용자/SDK 서명·반환 경로를 출력 전에 검사한다. 이 검사는 Rust 수준의 전체 ownership/alias/lifetime 보증이 아니고 stage0의 정수 산술 계약과 전체 동등성을 아직 달성하지 않았다.

## CPU 및 문자열의 동일 세션 비교

변경 전 baseline, 문자열만 변경한 strings, 나눗셈만 변경한 division, combined와 같은 Rust 바이너리를 20개 위치 균형 paired group으로 비교했다. 같은 입력별 예열, 독립 Python reference와 결과 대조, native 최적화, 원시 표본을 보존했다. 순환 순서는 각 실행 위치를 균형화하지만 모든 이웃 조합을 균형화하지는 않는다. 아래 표는 **최종 유지한 문자열 변경만**의 비교다.

| 종목 | Rust 대비 처리 성능 | paired 95% 구간 | 기존 Forge 대비 개선 | 1.10 판정 |
| --- | ---: | --- | ---: | --- |
| lcg | 1.0096 | 1.0086–1.0113 | 0.9999 | 미달 |
| primes | 1.0111 | 1.0109–1.0114 | 1.0004 | 미달 |
| scan | 0.9454 | 0.9389–0.9502 | 0.9987 | 미달 |
| builder | 1.0037 | 0.9811–1.0056 | 1.1060 | 미달 |
| immutable | 0.2300 | 0.2291–0.2311 | 0.9991 | 미달 |

Builder 개선은 약 10.6%이며 Rust 대비 110%라는 뜻이 아니다. 나머지 네 종목에서 실질적 개선을 입증하지 못했다. immutable append의 문자열 길이 재탐색과 arena가 모든 중간 사본을 유지하는 비용은 남아 있다. [전체 비교](compiler-string-optimization-2026-10-12.md), [75개 correctness·500개 prewarm·500개 측정 및 해시](compiler-string-optimization-2026-10-12.json), [실행한 runner](compiler-string-optimization-2026-10-12.runner.py).

## 더 강한 Rust builder 기준

원래 Rust 기준은 Forge finish처럼 독립 immutable snapshot을 복사하는 `builder.clone()`이다. 해당 작업에서 builder를 이후 사용하지 않으므로 idiomatic Rust는 마지막 버퍼를 move하여 복사를 생략할 수 있다. 기존 결과를 보존하고 이 더 강한 기준을 별도로 측정했다. 최종 bytes/checksum은 같지만 builder를 유지하며 사본을 만드는 계약과 builder를 소비하는 계약은 다르다.

| Rust 기준 | 개선 Forge / Rust | 95% 구간 |
| --- | ---: | --- |
| rust | 1.0006 | 0.9909–1.0063 |
| rust_move | 0.9986 | 0.9814–1.0029 |

두 기준 모두 1.10을 입증하지 못했다. 새로운 `kernels_move.rs`는 마지막 clone을 move로 바꾼 별도 control이며 원래 Rust fixture를 바꾸거나 약하게 만들지 않았다. [복사/move 비교와 한계](builder-copy-move-controls-2026-10-12.md), [원시 표본](builder-copy-move-controls-2026-10-12.json).

## 채택하지 않은 정수 나눗셈 후보

기존 wrapping int64와 0/MIN÷−1 trap을 유지하면서 동적 두 피연산자가 unsigned32에 들어가면 div32를 사용하는 후보를 실험했다. 알려진 상수 divisor는 기존 strength reduction을 유지하도록 했으며, GCC/Clang 밖에서는 원래 full-width 연산으로 fallback했다. 별도 branch-likelihood 후보도 만들었다.

소수 탐색에서 원래 후보는 기존 Forge 대비 약 1% 느려졌다. disassembly에서 기존 GCC의 첫 divisor=3 reciprocal reduction이 후보에서 guarded hardware division으로 바뀐 것을 확인했다. 이는 원인 가설이며 타이밍만으로 인과를 확정하지 않는다. 6개 부호/폭 분포, 각각 8,000,000회 연산, 12개 균형 paired group의 추가 비교도 수행했다.

| 분포 | 기존 / narrowing | 95% 구간 | 기존 / likelihood 후보 |
| --- | ---: | --- | ---: |
| unsigned32 | 0.9869 | 0.9860–0.9881 | 0.9826 |
| negative32 | 0.9906 | 0.9901–0.9913 | 0.9823 |
| mixed32 | 0.9895 | 0.9858–0.9941 | 0.9859 |
| positive64 | 0.9997 | 0.9987–1.0000 | 0.9992 |
| negative64 | 0.9999 | 0.9994–1.0009 | 1.0003 |
| mixed64 | 1.0023 | 1.0011–1.0059 | 1.0026 |

작은 양수·음수·혼합 입력은 더 느려졌고 큰 값의 작은 차이는 대표 경로의 퇴행을 정당화하지 못했다. 두 후보를 기본 컴파일러에 채택하지 않았으며 원래 checked int64 연산을 복구했다. 새로운 동적 경계/인수 단일 평가/trap oracle 테스트는 유지했다. [분포 보고서](arithmetic-division-2026-10-12.md), [72개 correctness·288개 prewarm·288개 측정 및 prototype 근거](arithmetic-division-2026-10-12.json), [원래 후보의 재현 패치](dynamic-division-candidate-2026-10-12.patch).

## HTTP 동등 조건 검증

준비된 응답을 보내는 Forge `http_prepare`/`http_serve_mt`와 owned socket2/libc Rust backend를 비교한다. 같은 응답 바이트, 전체 header terminator 수신, 요청당 새 연결, level-triggered epoll/accept batch, 1/2/4 physical workers, 분리된 client cores와 모든 worker affinity/count를 검증한다. 기존 Axum fixture와 달리 method/path/routing의 추가 처리를 한쪽에만 요구하지 않는다. 전체 HTTP 파서·TLS·routing·keepalive·DB·코루틴 I/O 비교는 아니다.

V1 성능 측정은 **실패하여 비교 가능한 전체 결과를 내지 못했다**. 14번째 pair의 Rust, body 4096, worker 4, concurrency 16 측정에서 12,000개 응답은 도착했지만 클라이언트가 2개 오류를 기록해 runner가 전체 실행을 `failed_no_claim`으로 끝냈다. 그 전에 발생한 연결 지연도 모두 원시 시도에 남아 있다. 오류가 있던 행을 제거하거나 실패 이후 재시작하지 않았다. 따라서 이 실행에서 Forge와 Rust의 HTTP 성능 우열을 주장하지 않는다. [실패를 포함한 원시 보고서](http-prepared-rust-forge-2026-10-12.json), [전체 원시 시도 묶음 (SHA-256: a35035c8f0a0e999388f106d07dbfaffebaffb1f24d7c86a929518b5d37ad2ab)](http-prepared-rust-forge-2026-10-12.raw.tar.gz), [연결 지연 진단](http-prepared-handshake-diagnostic-2026-10-12.md).

## HTTP 수용량 및 처리량 V2

V2 관측기 검증 14/14와 observer 단위 테스트 8/8을 통과한 뒤 4 worker, 동시성 16/64/128/256/512, 응답 본문 32/4096바이트, 설정별 8회씩 측정했다. 총 320개 prewarm/measurement sample 모두 정확한 응답·EOF 검증을 통과했고 오류 행은 0개다. 이 닫힌 루프 loopback 테스트에서는 두 본문 크기 모두 시험한 최고 동시성인 **최소 512 client lane까지 오류가 없었다**. 실제 최대 수용량은 그 이상일 수 있으며 이 시험만으로 정해지지 않는다.

성공 요청 처리량 중앙값 범위는 32바이트에서 Forge 2,958–4,240 req/s, Rust 3,720–4,326 req/s이고 4096바이트에서 Forge 3,732–4,210 req/s, Rust 3,950–4,254 req/s다. payload 처리량은 각각 약 0.266–0.382 / 0.335–0.389 MB/s, 15.511–17.500 / 16.415–17.680 MB/s다. 각 8개 paired ratio의 bootstrap 구간이 넓고 반복 변동이 커 언어 간 성능 우열을 주장하지 않는다. 이 관측기는 매 요청 새 TCP 연결을 사용하며 로깅 비용을 타이머에 포함한다. 일반 사용자 수, 외부 네트워크, keepalive, 전체 parser/routing/TLS/DB 성능으로 환산하지 않는다. [측정표와 조건](http-v2-capacity-2026-10-12.md), [JSON과 TSV 전체 원시 시도](http-v2-capacity-2026-10-12.json), [압축 원시 자료와 SHA-256](http-v2-capacity-2026-10-12.raw.tar.gz).

## 추가된 보안·견고성 작업

보안 점검에서는 소스/모듈 입력으로 커질 수 있는 parser 인자·coroutine 배열과 module registry/import 목록의 `realloc` 실패·크기 산술 경로를 우선 다룬다. 이 영역은 잘못된 대형 입력 또는 메모리 고갈에서 null 역참조나 capacity overflow를 만들 수 있다. 수정은 실패 시 기존 포인터를 보존하고, `SIZE_MAX` 곱셈/증가를 검사하며, 명확한 진단으로 종료하도록 한다. 구현과 확인이 끝난 뒤에만 취약점 수정으로 보고한다.

## 검증과 근거의 범위

이번 통합 Release build에서 21개 CTest와 selfhost stage3/stage4 C 고정점이 통과했다. 문자열 변경은 normal 및 ASan/UBSan 각각 string/ABI 2개 suite를 leak detection과 함께 통과했다. 산술은 native O0/O3 UBSan과 JS/Python oracle로 새로운 경계와 오류를 검증했다. SDK는 local source override build이며 공개 pin의 clean-fetch 검증 또는 새 GitHub CI 결과로 대신 표현하지 않는다.

공유 Linux 호스트의 유한 workload 결과다. CPU affinity, 예열과 위치 균형을 사용했지만 호스트 서비스/주파수/스케줄링 영향은 남으며 confidence interval은 해당 행과 실행의 불확실성이다. 서로 다른 날짜의 중앙값을 같은 세션의 causal improvement로 취급하지 않는다. RSS는 whole-process 정보이며 정확한 language heap 크기가 아니다.

## 하위 에이전트와 후속 실험

사용자의 병렬 작업 요청에 따라 별도 native 하위 에이전트 3개로 문자열 구현·compiler 분석/실험·HTTP 비교 구축을 분담하고 측정 시간에는 모든 빌드/테스트를 중단했다. 실제 OMO primary audit도 현재 설정된 seohu-llm/glm-5.3-flash로 시도했으나 API 연결 오류가 발생하여 결과를 받지 못했다. 전역 provider/계정 설정은 바꾸지 않았고 자동 재시도 프로세스를 종료했다. 실패를 성공한 OMO 하위 작업으로 계산하지 않는다. [OMO 실패 근거](omo-attempt-2026-10-12.json).

다음 구현 후보는 guard가 지배하는 단일 정수 induction increment의 overflow 불가능성을 입증하여 해당 C 연산만 간소화하는 것이다. 입증하지 못한 경로와 coroutine/state emission은 wrapping 연산을 유지해야 한다. immutable append의 길이 추적은 UTF-8 bytes, NUL narrowing, OOM, 외부 호출/alias effect와 arena reset의 불변식 검증 후 별도 후보로 다룬다. 대표 coroutine/mailbox/native thread의 최신 SDK 반복, HTTP 측정 결과, 지원하지 않는 typed vector 경로와 다른 호스트 검증도 전체 목표의 남은 근거다. 목표는 활성 상태로 유지한다.
