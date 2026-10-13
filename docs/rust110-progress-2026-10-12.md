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

## 증명 기반 loop increment의 성능 재검증

C codegen 후보는 제한된 증명 조건을 만족한 `i = i + 1`만 wrapping helper 대신 C signed `+`로 내보낸다. 바로 이전 compiler commit과 후보 commit을 분리 빌드하고 runtime/stdlib archive, Forge/Rust fixture, native flags를 공유해 5개 CPU/string workload를 18 position-balanced paired group으로 비교했다. 45개 소규모 correctness check와 270개 측정·270개 per-input prewarm이 모두 독립 reference를 통과했다. 후보/기준 처리량 중앙값은 LCG 0.9980, 소수 탐색 1.0043, scan 0.9978, builder 0.9963, immutable append 0.9933이었다. 신뢰구간은 각각 [0.9961, 1.0053], [0.9991, 1.0070], [0.9816, 1.0034], [0.9559, 1.1072], [0.9914, 1.0004]로 builder의 불확실성이 크고 유의한 개선을 입증하지 않는다. 후보의 Rust 대비 ratio도 1.0049/1.0116/0.9405/0.9970/0.2303으로 모두 1.10 목표에 미달했다. 따라서 이 codegen 후보를 성능 승리로 보고하지 않는다. [재검증 조건과 모든 표본](https://github.com/forge-language/forge-benchmarks/blob/main/docs/compiler-loop-proof-recheck-2026-10-12.md).

## HTTP 동등 조건 검증

준비된 응답을 보내는 Forge `http_prepare`/`http_serve_mt`와 owned socket2/libc Rust backend를 비교한다. 같은 응답 바이트, 전체 header terminator 수신, 요청당 새 연결, level-triggered epoll/accept batch, 1/2/4 physical workers, 분리된 client cores와 모든 worker affinity/count를 검증한다. 기존 Axum fixture와 달리 method/path/routing의 추가 처리를 한쪽에만 요구하지 않는다. 전체 HTTP 파서·TLS·routing·keepalive·DB·코루틴 I/O 비교는 아니다.

V1 성능 측정은 **실패하여 비교 가능한 전체 결과를 내지 못했다**. 14번째 pair의 Rust, body 4096, worker 4, concurrency 16 측정에서 12,000개 응답은 도착했지만 클라이언트가 2개 오류를 기록해 runner가 전체 실행을 `failed_no_claim`으로 끝냈다. 그 전에 발생한 연결 지연도 모두 원시 시도에 남아 있다. 오류가 있던 행을 제거하거나 실패 이후 재시작하지 않았다. 따라서 이 실행에서 Forge와 Rust의 HTTP 성능 우열을 주장하지 않는다. [실패를 포함한 원시 보고서](http-prepared-rust-forge-2026-10-12.json), [전체 원시 시도 묶음 (SHA-256: a35035c8f0a0e999388f106d07dbfaffebaffb1f24d7c86a929518b5d37ad2ab)](http-prepared-rust-forge-2026-10-12.raw.tar.gz), [연결 지연 진단](http-prepared-handshake-diagnostic-2026-10-12.md).

## HTTP 수용량 및 처리량 V2

V2 관측기 검증 14/14와 observer 단위 테스트 8/8을 통과한 뒤 4 worker, 동시성 16/64/128/256/512, 응답 본문 32/4096바이트, 설정별 8회씩 측정했다. 총 320개 prewarm/measurement sample 모두 정확한 응답·EOF 검증을 통과했고 오류 행은 0개다. 이 닫힌 루프 loopback 테스트에서는 두 본문 크기 모두 시험한 최고 동시성인 **최소 512 client lane까지 오류가 없었다**. 실제 최대 수용량은 그 이상일 수 있으며 이 시험만으로 정해지지 않는다.

성공 요청 처리량 중앙값 범위는 32바이트에서 Forge 2,958–4,240 req/s, Rust 3,720–4,326 req/s이고 4096바이트에서 Forge 3,732–4,210 req/s, Rust 3,950–4,254 req/s다. payload 처리량은 각각 약 0.266–0.382 / 0.335–0.389 MB/s, 15.511–17.500 / 16.415–17.680 MB/s다. 각 8개 paired ratio의 bootstrap 구간이 넓고 반복 변동이 커 언어 간 성능 우열을 주장하지 않는다. 이 관측기는 매 요청 새 TCP 연결을 사용하며 로깅 비용을 타이머에 포함한다. 일반 사용자 수, 외부 네트워크, keepalive, 전체 parser/routing/TLS/DB 성능으로 환산하지 않는다. [측정표와 조건](http-v2-capacity-2026-10-12.md), [JSON과 TSV 전체 원시 시도](http-v2-capacity-2026-10-12.json), [압축 원시 자료와 SHA-256](http-v2-capacity-2026-10-12.raw.tar.gz).

## 장시간 HTTP paired run 실패 기록

V2의 4-worker·64-client·4096-byte·12,000-request primary 비교는 7개 완전한 paired group 뒤 pair 8의 Rust prewarm에서 실패했다. 991개 시도 행 중 927개가 완료되고 64개가 5초 TCP connect timeout으로 끝났다. Global conntrack 관측치는 시험 전 261,217/262,144, 실패 sample 후 262,144/262,144였고 global TCPTimeWaitOverflow도 증가했지만, 공유 network namespace의 수치여서 프로세스별 원인을 증명하지 못한다. 부분 완료 쌍을 집계하거나 재시도하지 않아 전체 상태는 `failed_no_claim`이며 HTTP 언어 간 처리량 주장을 하지 않는다. 앞선 수용량 sweep은 반복당 1,024 요청까지만 검증했다. [원시 오류 및 제한](https://github.com/forge-language/forge-benchmarks/blob/main/docs/http-v2-primary-2026-10-12.md).

## 보안·견고성 패치 확인

컴파일러 입력·할당 경로 강화는 `6a2fa8c`에서 구현됐다. 공통 배열 reserve/calloc helper가 capacity 곱셈과 성장 overflow를 검사하고, parser 인자·coroutine·semantic locals와 module import/declaration 목록이 이 helper를 사용한다. 모듈 import 재귀는 64단계로 제한하고, module 파일은 일반 파일·유효 크기·seek/read 오류를 확인한다. driver argv 배열의 두 parallel allocation과 path 구성도 실패를 확인하며, library output과 header가 같은 파일을 덮어쓰지 못하게 한다. 신규 parser, module merge, compiler, driver 회귀를 포함해 현재 build에서 관련 CTest 4개가 통과했고, 전체 21개 suite도 통합 검증에서 통과했다. 이는 해당 입력·할당 경로 강화의 확인이며, 컴파일러 전체에 대한 보안 감사나 모든 메모리 고갈 상황의 보증을 뜻하지 않는다.

## 검증과 근거의 범위

이번 통합 Release build에서 21개 CTest와 selfhost stage3/stage4 C 고정점이 통과했다. 문자열 변경은 normal 및 ASan/UBSan 각각 string/ABI 2개 suite를 leak detection과 함께 통과했다. 산술은 native O0/O3 UBSan과 JS/Python oracle로 새로운 경계와 오류를 검증했다. SDK는 local source override build이며 공개 pin의 clean-fetch 검증 또는 새 GitHub CI 결과로 대신 표현하지 않는다.

공유 Linux 호스트의 유한 workload 결과다. CPU affinity, 예열과 위치 균형을 사용했지만 호스트 서비스/주파수/스케줄링 영향은 남으며 confidence interval은 해당 행과 실행의 불확실성이다. 서로 다른 날짜의 중앙값을 같은 세션의 causal improvement로 취급하지 않는다. RSS는 whole-process 정보이며 정확한 language heap 크기가 아니다.

## 하위 에이전트와 후속 실험

사용자의 병렬 작업 요청에 따라 별도 native 하위 에이전트 3개로 문자열 구현·compiler 분석/실험·HTTP 비교 구축을 분담하고 측정 시간에는 모든 빌드/테스트를 중단했다. 실제 OMO primary audit도 현재 설정된 seohu-llm/glm-5.3-flash로 시도했으나 API 연결 오류가 발생하여 결과를 받지 못했다. 전역 provider/계정 설정은 바꾸지 않았고 자동 재시도 프로세스를 종료했다. 실패를 성공한 OMO 하위 작업으로 계산하지 않는다. [OMO 실패 근거](omo-attempt-2026-10-12.json).

다음 구현 후보는 guard가 지배하는 단일 정수 induction increment의 overflow 불가능성을 입증하여 해당 C 연산만 간소화하는 것이다. 입증하지 못한 경로와 coroutine/state emission은 wrapping 연산을 유지해야 한다. immutable append의 길이 추적은 UTF-8 bytes, NUL narrowing, OOM, 외부 호출/alias effect와 arena reset의 불변식 검증 후 별도 후보로 다룬다. 대표 coroutine/mailbox/native thread의 최신 SDK 반복, HTTP 측정 결과, 지원하지 않는 typed vector 경로와 다른 호스트 검증도 전체 목표의 남은 근거다. 목표는 활성 상태로 유지한다.

추가 source audit에서 현재 optimizer는 arithmetic expression folding만 하며, semantic checker는 string alias/liveness를 추적하지 않는 것을 확인했다. native `str_append`의 arbitrary-byte/NUL 동작과 JS의 `String.fromCharCode` 동작은 기존 UTF-8 builder API와 동치가 아니어서 자동 builder lowering은 보류했다. 대신 cached length를 전달하는 additive `str_view_append_byte`를 구현했다. 단일 allocation으로 immutable snapshot과 view metadata를 만들고, legacy ABI는 유지한다. 동일 `4096 × 512` workload·seed·실행 순서를 사용한 독립 16-pair run 2회에서 legacy 대비 Forge 처리량이 1.1149배 및 1.1134배였고, 합친 32-pair median은 1.1141 (95% CI 1.1060–1.1189)였다. Rust 대비 처리량은 0.2862 및 0.2824로 여전히 1.10에 크게 미달한다. 매 append의 prefix copy와 arena 보존은 남아 O(n²)다. [측정·원시 표본](immutable-view-append-2026-10-12.md), [compiler/backend gate](immutable-append-and-ownership-next-steps-2026-10-10.md#compilerbackend-audit-current-lowering-is-not-safe).

추가로 정수 나눗셈의 0/overflow trap 분기에 unlikely hint를 넣은 compiler 후보를 직전 compiler와 같은 Rust control로 비교했다. 24개 paired group에서 후보/기준 처리량은 LCG 0.9956 (95% CI 0.9909–0.9994), primes 0.9866 (0.9815–0.9887)으로 두 workload 모두 느려져 소스 변경은 폐기했다. [실험과 raw JSON](division-trap-branch-hint-2026-10-12.md).

## Private append-loop lowering recheck

A fresh five-workload comparison used 42 position-balanced pairs with identical Forge/Rust fixture, timer, runtime archive, stdlib archive and public headers; only compiler binaries differed. The baseline was compiler commit `88290b8`, immediately before the private append-loop lowering, and the candidate was `4bdd4ec`. The compatibility fixture removed `immutable_view` and used the older builder constructor/finish APIs so the baseline compiler could build it. The immutable append loop itself was unchanged. All 99 correctness checks, 630 per-input prewarms and 630 measured outputs matched the independent oracle.

| Workload | Before Forge/Rust | Current Forge/Rust (95% interval) | Current vs previous Forge (95% interval) |
| --- | ---: | ---: | ---: |
| LCG | 1.0009 | 1.0036 [1.0007–1.0075] | 1.0013 [0.9993–1.0057] |
| Primes | 1.0102 | 1.0102 [1.0082–1.0127] | 1.0017 [0.9996–1.0045] |
| Scan | 1.9434 | 1.9490 [1.9176–1.9631] | 1.0019 [0.9987–1.0137] |
| Builder | 1.1983 | 1.2084 [1.0931–1.2740] | 1.0132 [0.9820–1.0959] |
| Immutable append | 0.2319 | 18.0431 [17.2501–18.3175] | 77.5045 [74.4483–78.6935] |

The generated C changes the immutable loop from repeated `fr_str_append` calls to a private builder and `fr_str_builder_finish_take`. This supports a large gain for the proven immutable-append pattern; it does not imply every Forge workload reaches 110% of Rust. The direct builder `finish` versus `finish_take` experiment was inconclusive for standalone throughput (1.008x, 95% interval 0.946–1.030). [Conditions and raw samples](compiler-append-lowering-2026-10-12.md), [direct transfer API comparison](builder-finish-take-2026-10-12.md).

## HTTP tested capacity extension

The V2 prepared-response loopback test now also passed 1024, 2048 and 4096 simultaneous client lanes for 32-byte responses, with four clean repeats for both Forge and Rust at each level. Thus the tested error-free capacity is **at least 4096 lanes** under this connection-per-request workload, not an absolute user limit. At 4096 lanes median successful throughput was 6243 req/s for Forge and 7964 req/s for Rust (0.562 and 0.717 MB/s); the four paired ratios are too variable to establish a throughput winner. At 2048 lanes, medians were 4423 and 6550 req/s. [1024/2048 report and raw attempts](http-v2-capacity-extended-2026-10-12.md), [4096 report and raw attempts](http-v2-capacity-4096-2026-10-12.md).

## Builder preallocation comparison

A 120-pair comparison isolated `str_builder()` versus `str_builder_with_capacity(n)` using the same compiler, runtime, stdlib, headers, clock, and source-matched Rust control. Rust uses `String::with_capacity(n)` in both variants. Forge preallocation improved throughput 1.0246x over its default-capacity builder (95% interval 1.0066–1.0679). Candidate Forge/Rust was 1.0929x with a wide interval (1.0158–1.1999); the source-matched alternative Rust control gave 1.0996x [1.0246–1.2158]. This supports a small builder improvement but does not establish 1.10 versus Rust. [Conditions and raw samples](builder-capacity-reservation-2026-10-12.md).

## SDK LTO experiment

The generated C and standard SDK archives were built with LTO enabled, then compared with the normal SDK for builder, scan and immutable workloads (42 paired groups, identical compiler and source fixtures). The LTO/normal Forge throughput ratios were 0.993x for scan [0.986–1.001], 0.979x for builder [0.921–1.031], and 1.003x for immutable append [0.956–1.141]. Results do not establish an LTO gain, so the default SDK build policy stays unchanged. All 10 stdlib CTest cases passed on the LTO build. [Conditions and raw samples](sdk-lto-comparison-2026-10-12.md).

## Rejected contiguous builder allocation candidate

A stdlib candidate combined `str_builder_with_capacity` metadata and its initial bytes in one arena allocation and removed zero-fill for the length-delimited capacity area. Native and ABI CTest suites passed (10/10). The same compiler/source/runtime was compared against the current SDK for 120 and then 240 paired builder groups. Baseline/candidate Forge throughput was 1.0059x [0.9857–1.0479] in the first run and 0.9958x [0.9823–1.0106] in the larger run. The direction changed and the later interval includes no change; the candidate was reverted. The experiment does not support a speed claim. [Conditions, raw samples, and reversible patch](builder-contiguous-allocation-2026-10-12.md).


## Constant-divisor lowering experiment

A compiler candidate bypassed checked integer division/remainder helpers for nonzero literal divisors other than `-1`. Arithmetic regressions passed on native O0/O3 UBSan and JavaScript, and all benchmark outputs matched the independent reference. In a 24-pair frozen five-workload comparison, the candidate regressed builder throughput to 0.8616 of baseline (95% CI 0.7878–0.9415); the candidate was discarded. It did not move the broader suite to the 1.10 Rust-relative target. [Conditions and per-workload results](constant-divisor-fast-path-2026-10-12.md), [raw samples](constant-divisor-fast-path-2026-10-12.json), [reproduction patch](constant-divisor-fast-path-2026-10-12.patch).
## Guarded string-view bounds-check elimination

A compiler candidate removes the repeated checked accessor call only for a native `while (i < n)` loop where `i` is initialized to zero, `n` is captured from `str_view_len(view)`, the view/index/bound remain stable, and the loop body contains no invalidating calls or suspension. A private stdlib accessor performs the proven byte load; all other paths retain the checked API. The analyzer supports a direct increment in the loop body even when it is followed by pure statements, and refuses an accessor after that increment. Negative starts, arena reset before/inside the loop, and increment-before-access regressions stay on the checked path.

All 21 Forge CTest suites passed. A frozen five-workload comparison used 42 position-balanced pairs, matching fixtures, timer, runtime/stdlib archives and headers, and independent output references. All correctness checks and measured checksums passed. The initial candidate versus baseline throughput was LCG 0.9998 [0.9996–1.0001], primes 1.0003 [0.9999–1.0009], scan 1.1488 [1.1441–1.1540], builder 1.0019 [0.9949–1.0067], and immutable append 1.0683 [1.0637–1.0748]. The initial run overlapped an OMO process using about 21% CPU across the available affinity set. After the OMO review and proof correction, the current compiler was rebuilt; it produced the identical Forge executable and byte-identical measured C fixture. A lower-background-load repeat of 42 pairs confirmed scan at 1.1484 [1.1454–1.1526] and immutable append at 1.0785 [1.0677–1.1464]; LCG was 1.0001 [0.9997–1.0003], primes 1.0001 [0.9999–1.0003], and builder 0.9978 [0.9940–1.0029]. The repeated scan gain is stable; immutable append is directionally positive with a wider interval. Current Forge/Rust ratios are 1.0040 for LCG, 1.0112 for primes, 2.2463 for scan, 1.2878 for builder and 19.2542 for immutable append. Thus three of these five rows exceed 1.10; this is not a language-wide guarantee or completion of the broader objective. The OMO Sisyphus-Junior audit found the index-write gap before bound capture; commit `8f87f2c` fixes it, the negative-index regression returns the checked result, and all 21 CTest suites pass after the fix. [Initial conditions and safety correction](string-view-bounds-elision-2026-10-12.md), [lower-background-load repeat and per-pair data](string-view-bounds-elision-rerun-2026-10-12.md), [full repeat JSON samples](string-view-bounds-elision-rerun-2026-10-12.json), [initial run JSON samples](string-view-bounds-elision-2026-10-12.json).

## Current SDK CPU recheck with 120 paired samples

A fresh 120-pair `cpu_compare.py` run used the same current Forge compiler,
runtime and stdlib artifacts for all five workloads, the matching Rust source
control, frozen dimensions from the weighted-cycle run, balanced execution
order, per-input prewarm, and the independent Python output reference. All
correctness checks passed. Forge/Rust throughput was LCG 1.0068
([1.0018, 1.0085]), primes 1.0113 ([1.0092, 1.0130]), scan 2.2701
([2.2645, 2.2765]), builder 1.3071 ([1.2014, 1.3713]), and immutable append
17.4990 ([10.9507, 18.0257]). This run supports the 1.10 target on scan,
builder, and immutable append, while LCG and primes remain below it. Builder
and immutable append intervals are wide enough to warrant a quieter-host
repeat; this remains one machine and this fixture suite, not a language-wide
claim. The source variant and archives differ from earlier CPU reports, so
their medians must not be pooled. [Conditions and raw samples](cpu-current-rerun-2026-10-12.md),
[raw report](cpu-current-rerun-2026-10-12.json).

## Linux HTTP accepted-socket optimization candidate

To remove two per-client `fcntl` calls, a Linux-only candidate kept the epoll listener nonblocking and accepted client fds as blocking with `SOCK_CLOEXEC`. The candidate passed 14 HTTP V2 correctness probes and the 10-test stdlib CTest suite. In a 24-triplet, position-balanced run at two workers, 64 clients and 32-byte responses, candidate/baseline throughput was 0.8323 [0.6969, 1.3336] and candidate/Rust was 0.8205 [0.7258, 0.9343]. All 72 measured samples and 72 prewarms passed, but p99 latency reached roughly 208 ms and the baseline interval remained very wide. The candidate is not a performance win and was reverted. The broader HTTP path remains below the 1.10 target on this sample. [Decision, failed attempt, conditions and raw bundles](http-accept4-blocking-experiment-2026-10-12.md).

## Prime-loop wheel candidate

Fixed a benchmark reference gap: the prime oracle previously assumed positive values and the two language fixtures misclassified 2 and 3. Commit `9c7e27c` corrects the oracle and both fixtures; five unit tests and 78 signed-seed Forge/Rust checks pass. A separate 24-pair trial-divisor wheel experiment reduced both Forge and source-matched Rust median time by about 1.49x, but their matched throughput ratio remained 1.0074 [1.0025, 1.0103]. This is an algorithmic speedup shared by both implementations, not evidence that Forge reached 1.10x Rust, so it is not adopted as a compiler performance claim. [Conditions and paired results](cpu-prime-wheel-2026-10-12.md), [all samples](cpu-prime-wheel-2026-10-12.json), [reproduction patch](cpu-prime-wheel-2026-10-12.patch), [frozen builds and checksums](cpu-prime-wheel-2026-10-12.raw.tar.gz).

## Corrected-prime-fixture CPU recheck

After the prime-oracle boundary fix, a fresh 40-pair full-suite run used the
same compiler/SDK archives and frozen dimensions as the 120-pair current-SDK
recheck. LCG measured 1.0039 [0.9999, 1.0111], primes 1.0118
[1.0089, 1.0133], scan 1.9439 [1.9368, 1.9548], builder 1.2439
[1.0954, 1.3073], and immutable append 18.1410 [9.3272, 18.9618]
Rust/Forge throughput. The fixture correction leaves LCG and primes below 1.10;
scan and immutable append support this host/run, and builder remains
inconclusive. Its source, executable hashes, conditions, and all samples are
preserved separately from the earlier 120-pair run. [Report and raw samples](cpu-current-edgefix-40-2026-10-12.md), [machine-readable data](cpu-current-edgefix-40-2026-10-12.json).

## Signed 32-bit remainder fast-path candidates

Two compiler-only candidates added a checked signed-32-bit remainder path with a full-width fallback. Candidate v2 also tried to preserve the initial divisor 3 path. Both passed the 18 arithmetic tests under UBSan at `-O0` and `-O3`, but a 24-pair compiler-only comparison regressed primes throughput to 0.9863 [0.9814, 0.9884] and 0.9860 [0.9838, 0.9895] of baseline; immutable append also regressed, especially in v2. Matched Forge/Rust prime ratios were 0.9980 and 0.9985, while baseline was 1.0107. Disassembly retained `idiv` instructions in both 64-bit and 32-bit paths, so these candidates are discarded. A new signed-32-bit overflow edge regression is covered in Forge commit `10e05d1`. [Measurements, exact patches and frozen builds](arithmetic-mod-narrowing-2026-10-12.md).

A follow-up paired the signed-remainder narrowing candidate with the equivalent prime wheel kernel, removing the `d=3` first-iteration issue. At 24 pairs, Forge/Rust was 1.0040 [1.0021, 1.0108] for baseline and 0.9969 [0.9915, 1.0036] for narrowing; candidate/baseline Forge throughput was 0.9953 [0.9918, 0.9984]. The candidate was discarded: even without the initial divisor, its generic guard remains a small regression and does not support 1.10. [Conditions and full data](arithmetic-mod-narrowing-wheel-recheck-2026-10-12.md), [samples](arithmetic-mod-narrowing-wheel-recheck-2026-10-12.json), [frozen builds](arithmetic-mod-narrowing-wheel-recheck-2026-10-12.raw.tar.gz).

## LCG countdown-loop probe

A source-level countdown rewrite was measured against the original Forge loop
and unchanged Rust control in 28 prewarmed position-balanced pairs at the
current LCG dimensions. Forge/Rust moved from 0.9977 [0.9954, 1.0046] to
1.0134 [1.0049, 1.0180], but Forge's own paired speedup was 0.9997
[0.9951, 1.0082]. Disassembly shows both Forge loops retain three loop
control/data-movement instructions; the incrementing form places its increment
before the expensive remainder, while countdown requires a move after it.
The change is not adopted and does not support the 1.10 target. [Conditions,
assembly rationale and results](lcg-countdown-loop-2026-10-12.md).

The same below-target workloads were screened with GCC `-funroll-loops` in
20 prewarmed position-balanced pairs. Candidate/baseline Forge throughput was
1.0001 [0.9927, 1.0101] for LCG and 1.0013 [0.9990, 1.0033] for primes. The
LCG binary grew by 2.8 KB and showed duplicated loop bodies, but neither
workload gained measurable speed. Default `-O3` remains unchanged. [Conditions
and data](gcc-loop-unroll-screen-2026-10-12.md).

A follow-up tested a per-value signed-32-bit fast path for trial division,
guarded once by `0 <= value <= INT32_MAX`, with the original checked 64-bit
loop as fallback. The candidate passed reference checks and 13 direct
primality cases spanning the signed-32-bit boundary. Across 24 paired groups,
the seed-matched candidate/baseline Forge/Rust ratio-of-ratios was 0.9973
[0.9896, 1.0024], which includes no change; candidate Forge/Rust was 1.0101
[1.0073, 1.0170]. Disassembly contains both `idivl` and `idivq`. The runs do
not establish an end-to-end benefit for the guard/split, so the candidate is
not adopted.
[Conditions, proof boundary and raw samples](prime-hoisted-int32-remainder-2026-10-12.md).

## Quotient-based prime-loop bound

A source-level rewrite changed `d*d <= value` to `d <= value/d` in Forge and
Rust, recomputing the quotient after each divisor increment. At 24 paired
seeds, Forge kernel throughput was unchanged: candidate/baseline was 0.9980
[0.9950, 1.0046]. Rust became about 1.97x slower, making the apparent
Forge/Rust ratio rise from 1.0104 to 1.9925; this is not a Forge gain. The
candidate is rejected. [Conditions and raw samples](prime-quotient-loop-bound-2026-10-12.md).

## Positive constant remainder lowering

Native codegen now has a candidate path that emits `%` directly only for a
positive integer literal divisor and a left expression conservatively known
to be integer or boolean. All dynamic, nonpositive and unknown cases retain
the checked helper. The `INT64_MIN` boundary test passes at `-O0` and `-O3`,
and all 21 CTest suites pass. In a 48-pair interleaved baseline/candidate/Rust
comparison, scan Forge throughput rose 1.1571x [1.1509, 1.1729] and
Forge/Rust reached 2.2504 [2.2330, 2.2738]. LCG and primes remained below 1.10;
builder's Forge gain was inconclusive; immutable append stayed well above 1.10
with broad noise. This supports the 1.10 target for scan only. [Method and
raw samples](positive-constant-remainder-lowering-2026-10-12.md).

## HTTP timeout inheritance probe

A Linux candidate configured the existing read/write socket timeout on each
listener so accepted sockets could inherit it, avoiding two per-request
`setsockopt` calls while preserving per-client fallback on setup failure. The
V2 HTTP benchmark proved too noisy to establish a benefit: across 24 matched
groups candidate/baseline Forge throughput was 0.976 [0.549, 1.434]. A larger
attempt also stopped on 502 connect timeouts during the unmodified baseline.
The candidate was reverted; per-connection timeout setup remains. [Conditions,
timings and raw attempts](http-timeout-inheritance-probe-2026-10-12.md).

## Mersenne constant remainder candidate

A compiler prototype replaced positive `2^k-1` remainders (`16 <= k <= 62`)
with four unsigned folds and sign restoration. Its formula matched 47,470
signed boundary/random cases, but a 48-pair interleaved comparison regressed
LCG Forge throughput to 0.6384 [0.6369, 0.6397] of baseline and primes to
0.9965 [0.9955, 0.9996]. The compiler's existing constant-divisor lowering
was faster; the prototype was reverted. [Method and raw samples](mersenne-remainder-lowering-2026-10-12.md).

## LCG and prime-search code-generation audit

A static GCC/Rust assembly review found nearly identical reciprocal-multiply lowering for the LCG's positive constant remainder. Prime search differs: GCC emits `idivq` for dynamic trial division, while Rust uses a guarded `divl` path when both operands fit 32 bits and falls back to `idivq`. A prior guarded 32-bit Forge trial-division prototype showed no paired improvement (candidate/baseline 0.9973 [0.9896, 1.0024]), so the same guard split is not repeated. All 21 Forge CTest suites passed after rebuilding current source. OMO's configured `glm-5.3-flash` and `qwen3.8-flash` attempts both ended in API connection failures before returning a delegated review; this audit does not claim OMO findings. [Static evidence and artifact hashes](lcg-prime-codegen-audit-2026-10-12.md).

## Fresh 120-pair LCG and prime-search recheck

The current compiler and SDK were rebuilt from Forge `368b9c8` and compared with the checked-in Rust controls in 120 prewarmed, position-balanced pairs per below-target workload, using dimensions from the corrected-prime 40-pair run. All 12 direct correctness checks, 484 prewarms, and 480 measured executions matched the independent reference. LCG measured 1.0046 Rust-relative throughput [1.0016, 1.0085]; prime search measured 1.0105 [1.0082, 1.0123]. Both intervals are well below 1.10 and reinforce the static finding that the current hot loops are near parity. [Conditions and full sample data](cpu-current-lcg-primes-120-2026-10-12.md), [machine-readable report](cpu-current-lcg-primes-120-2026-10-12.json).

## Coroutine yield-call inlining probe

The current four-worker mixed-CPU coroutine case is below Rust. A generic LTO runtime did not produce a supported gain; a matched native-target LTO build plus forced inlining removed the `fr_coro_inline_yield` call from generated coroutine code but still did not improve mixed-CPU throughput. Across 16 pairs, forced-inline candidate/baseline was 0.8855 [0.8289, 0.9873] at two workers and 0.9815 [0.8764, 1.1539] at four. Both LTO runtime builds passed all three runtime CTests; all 27 direct checks and 288 prewarms plus 288 measured runs per comparison matched every result. Neither candidate is adopted. The OMO endpoint timed out again, so no delegated review result is claimed. [Experiment interpretation](coroutine-yield-inline-investigation-2026-10-12.md), [generic LTO comparison](coroutine-runtime-lto-2026-10-12.md), [forced-inline comparison](coroutine-yield-always-inline-2026-10-12.md).

## Current HEAD full CPU recheck and LCG fast path

Forge HEAD `368b9c8` was rebuilt and compared with the unchanged Rust fixtures over 40 prewarmed, position-balanced pairs for all five CPU/string workloads. The 30 correctness checks, 430 prewarms and 400 measurements passed. Rust/Forge medians were LCG 1.0051 [0.9998, 1.0092], primes 1.0111 [1.0094, 1.0130], scan 2.2727 [2.2642, 2.2884], builder 1.2703 [1.0744, 1.3736], and immutable append 16.5657 [9.3426, 18.5838]. A focused 120-pair current-HEAD builder run tightened that result to 1.3607 [1.3099, 1.3812]. Thus scan, builder and immutable append support the target on this host; baseline LCG and primes remain below it. [Full current-HEAD report and samples](cpu-current-all-2026-10-12.md), [focused builder report](cpu-current-builder-120-2026-10-12.md).

A guarded single-fold LCG implementation was then compared against the unchanged Rust control and current Forge baseline in 60 balanced three-way pairs. It was 1.1464 [1.1419, 1.1488] faster than baseline Forge and reached 1.1563 [1.1506, 1.1590] Rust-relative throughput. All 584 direct boundary/randomized checks, 180 prewarms and 180 measurements matched the independent reference. The fast path applies only when the initial seed lies in the proven nonnegative modulus range; other seeds retain the original wrapping and signed-remainder path. This is a source-level LCG optimization, not a generic compiler lowering claim. [Proof and result](lcg-positive-mersenne-fold-2026-10-12.md), [candidate fixture](../benchmark/cpu/kernels_lcg_mersenne_fold.fg), [raw samples](lcg-positive-mersenne-fold-2026-10-12.json).

The 1.10 objective remains incomplete because equivalent prime-search code still measures near parity. The OMO scan review attempt in this turn did not return delegated findings: the configured agent name was unavailable and the fallback call remained without a response, so it was stopped. No OMO analysis is represented as evidence.

An additional Forge-only 6k wheel candidate cut prime-search time from 74.711 ms to 49.731 ms and reached 1.5143 [1.5104, 1.5174] relative to the unchanged Rust fixture across 60 three-way paired groups. All 160 direct cases, 180 prewarms and 180 measurements passed. Because the earlier source-matched wheel control reached only 1.0074 [1.0025, 1.0103], this is evidence for an algorithm-level workload improvement, not for a compiler/language speed advantage. Keep both interpretations visible when reporting the target. [Conditions and full samples](prime-wheel-vs-rust-baseline-2026-10-12.md), [candidate kernel](../benchmark/cpu/kernels_prime_wheel.fg), [raw data](prime-wheel-vs-rust-baseline-2026-10-12.json).

## Matched Miller–Rabin prime-search comparison

A bounded deterministic Miller–Rabin path (bases 2 and 3 below 1,373,653) was implemented in both benchmark fixtures, with overflow-safe trial division as the fallback. In 48 randomized groups balanced across all 24 execution orders, Forge and Rust candidates passed 175 direct reference cases, 192 same-input prewarms and 192 timed measurements. The common algorithm improved Forge by 2.8212 [2.8073, 2.8329] and Rust by 2.7874 [2.7807, 2.8071] relative to their respective baselines. The matched Forge/Rust throughput ratio was 1.0192 [1.0130, 1.0261], below the 1.10 objective. The experimental fixture is not adopted as a compiler or default-kernel change. [Method and interpretation](prime-miller-rabin-matched-2026-10-12.md), [full paired samples](prime-mr-matched-fourway-2026-10-12.json).

## Dynamic remainder guard probes

Two compiler-only positive-remainder fast paths were measured in 48 randomized balanced groups. A checked 32-bit fast path regressed Forge prime throughput (baseline/candidate 0.9878 [0.9862, 0.9905]); a checked positive 64-bit unsigned path also regressed (0.9893 [0.9872, 0.9918]). All 160 reference cases passed for each; the first candidate also passed all 21 CTests. Assembly retained both narrow/wide divide forms or unsigned/signed wide divide forms. Both changes were reverted. [Interpretation and raw samples](prime-modulo-guard-probes-2026-10-12.md).

## GCC profile-guided optimization probe

The frozen Forge C output was PGO-trained with eight seeds each for LCG and prime search and compared with the standard Forge and unchanged Rust binaries in 48 balanced three-way pairs. All 308 direct cases, 288 prewarms and 288 measurements matched. LCG baseline/candidate was 1.0047 [0.9959, 1.0076], inconclusive; prime was 0.9887 [0.9864, 0.9904], a regression. The PGO candidate is discarded. [Conditions and paired samples](cpu-profile-guided-2026-10-12.md).

## Combined CPU candidate and extended HTTP concurrency

The LCG positive-state fold and bounded Miller–Rabin were combined in one Forge benchmark fixture and compared with baseline Forge and unchanged Rust in 48 balanced groups across all five CPU/string modes. The 1,000 direct cases, 720 prewarms and 720 measurements matched. A 120-pair recheck for scan/builder produced Rust/candidate ratios of scan 1.8918 [1.8735, 1.9318] and builder 1.3151 [1.1897, 1.3703]. Across the suite all candidate/Rust intervals exceed 1.10; this is workload-level evidence, not a compiler-wide claim. The combined fixture also regressed scan against baseline Forge to 0.8476 [0.8338, 0.8540], so it remains an experimental fixture. [Consolidated analysis](rust110-final-cpu-http-measurements-2026-10-12.md), [48-pair samples](cpu-combined-five-workloads-2026-10-12.json), [focused recheck](cpu-combined-scan-builder120-2026-10-12.json).

The V2 prepared HTTP capacity sweep was extended to 28,000 loopback client lanes, with four clean measured repeats for both languages at 8,192, 16,384, 24,576 and 28,000. At 28,000, median successful rates were 9,046 req/s Forge and 8,817 req/s Rust; the paired interval spans 0.940–1.124, so it does not establish a winner. The result is at least 28,000 error-free clients in this finite request-per-lane test, not the server's absolute maximum; two pinned client CPUs, one thread per lane, per-request logging and a 28,232-port ephemeral range constrain the observation. [Method and samples](http-capacity-extended-2026-10-12.md).

The prepared HTTP observer was extended to V3.2 with an eight-source loopback bind pool, a bounded 256-connect ramp window, and periodic deadline scans. Forge and Rust each completed 128,000 one-shot requests in all eight measured pairs (4 workers, 32-byte response, 120-second phase timeouts). This is a repeatable lower bound of at least 128,000 tested lanes; it is not an absolute server maximum. Median throughput was 2,692 req/s for Forge and 4,080 req/s for Rust, but the paired 95% interval was 0.358–1.746 and per-sample variance was high, so there is no throughput winner. Single-shot 220,000-lane successes coexist with high-load timeout failures, indicating the shared host's TCP churn and single-reactor observer limit boundary claims. [V3.2 conditions and evidence](http-v32-capacity-128k-paired-2026-10-12.md).

## Positive constant division lowering probe

The native code generator now also emits direct division for known-integer expressions with a positive literal divisor, preserving checked helper lowering for dynamic, zero, negative, and unknown-type cases. The signed-boundary regression passed under UBSan at `-O0`/`-O3` and through the JavaScript backend. This is a proven lowering simplification, not a measured release speedup: GCC 13.3 `-O3` already reduced the helper form to the same instruction sequence. It is not counted as progress toward 1.10×. An OMO Sisyphus-Junior review recommended this extension; its read-only task is `ses_ecd9ca1a1ffemKBJ2u3GYQWlhL`. [Proof and measurement limit](positive-constant-division-lowering-2026-10-12.md).

## Affine Mersenne multiply-add codegen probe

Extended the compiler's guarded Mersenne fold from `(x*C)%M` to `(x*C+K)%M` for positive constant `K` and `M=2^k-1`. The helper folds only when `x` and the full multiply-add are nonnegative and representable; all other cases use Forge's wrapping multiply/add and signed-remainder helpers. A new UBSan/JavaScript arithmetic regression checks INT64 boundaries and randomized inputs across both optimization levels. All 22 CTests passed.

The matched affine LCG fixture applies `(value*48271+1)%2147483647` for 8,000,000 iterations from positive runtime seeds. In 60 three-way prewarmed balanced groups, candidate Forge reached 1.7861× [1.7614, 1.7925] baseline Forge throughput and 2.1024× [2.0864, 2.1119] Rust throughput. All direct oracle checks, prewarms and measurements matched. This is a narrow arithmetic microbenchmark and does not establish a language-wide speed ratio. The [paired report](affine-mersenne-final-2026-10-12.md) and [raw data](affine-mersenne-final-2026-10-12.json) preserve samples and hashes.

## Source-level small-prime prefilter: matched CPU recheck

A benchmark-only Forge prime kernel now rejects values divisible by 3 or 5
before its existing Miller–Rabin/trial-division path, after handling values
below 2 and the primes 2, 3 and 5. This preserves the result for every integer:
any remaining value divisible by 3 or 5 is composite, while all other values
reach the unchanged prior decision path. The Rust control remains the existing
base-2/3 Miller–Rabin fixture. The benchmark runner accepts explicit fixture
source paths and records them and their hashes, so the pair is reproducible.
This is an algorithm-level fixture optimization, not evidence of a general
compiler or language advantage.

The matched prime workload (2000 × 128) produced Forge/Rust throughput ratios
of 1.6869 [1.6657, 1.7010] in a focused 120-pair run and 1.6915
[1.6685, 1.7038] inside the 120-pair, five-workload run. Across that full
suite, LCG was 1.5083 [1.5030, 1.5142], scan 1.9388 [1.9276, 1.9478], and
immutable append 18.7241 [11.0113, 19.5311]. Builder was 1.0966
[1.0663, 1.1539], inconclusive against 1.10; its separate focused 120-pair
run was 1.1990 [1.1087, 1.2786]. Treat the builder results separately because
the full-suite interval does not establish the threshold. Six correctness
checks per workload in the suite, 1230 prewarms and 1200 measured executions
passed; an additional 175 prime input cases across boundary and randomized
seeds matched the independent sieve reference in both binaries. [Full-suite
conditions and samples](cpu-prime-mr-smallprime-full-120-2026-10-12.md),
[focused prime run](cpu-prime-mr-smallprime-120-2026-10-12.md), [focused
builder run](cpu-prime-mr-smallprime-builder-120-2026-10-12.md).

The matched 30-wheel prime fixture was also checked and measured at 1.0020
[1.0011, 1.0039] across 60 pairs. It is retained as a rejected experiment;
it does not support the 1.10 threshold. [Wheel report and samples](cpu-prime-wheel30-matched-2026-10-12.md).

## Algorithm-matched small-prime control and rejected builder predicate

The previous small-prime run kept the Rust Miller–Rabin control unchanged.
Applying the same 3/5 prefilter to Rust removes the algorithm asymmetry. In a
fresh 60-group balanced three-way run, the original Forge binary measured
1.0314 [1.0177, 1.0436] Rust/Forge prime throughput, below 1.10. Its executable,
compiler/runtime/stdlib archives and installed headers are byte-for-byte
identical to the prior Forge small-prime run; only the Rust fixture/binary
changes. The earlier ~1.69 ratio therefore must not establish a matched-
algorithm compiler advantage.

The same run screened a header-only candidate dropping `cap > len` from
`cap > len && cap - len > 1`. API-created builders maintain `len <= cap`, so
subtraction cannot underflow even for an empty/detached builder. The candidate
passed all 11 stdlib CTests (including checked-inline and ABI string variants)
and an optimized UBSan-instrumented string caller test. Builder improvement
was 1.0052 [0.9322, 1.0562], while scan regressed slightly to 0.9939
[0.9833, 0.9997] of baseline throughput. The candidate is rejected and the
original header restored. All 45 correctness checks, 900 prewarms and 900
measurements passed; an additional 175 matched-prime input cases in each
binary passed the sieve reference. The original Forge baseline's matched
Rust ratios for LCG/scan/builder/immutable were 1.5049/1.9384/0.9883/18.5695
in this session. Builder and primes still do not support the target.
[Three-way report](builder-capacity-invariant-2026-10-12.md), [all samples](builder-capacity-invariant-2026-10-12.json), [extended prime correctness](prime-smallprime-matched-correctness-2026-10-12.json), [candidate patch](builder-capacity-invariant-2026-10-12.patch), [frozen binaries, SDK inputs and runner](builder-capacity-invariant-2026-10-12.raw.tar.gz) (SHA-256 `83067692b91a1bc7eef1b7cc57b414a295913a98e0246b5de7f15966b049091c`).

## Cross-OS verification requirement

After validating the remaining implementation improvements, repeat the
matched before/after and Forge/Rust experiments on macOS and Windows, with
identical workload sources, dimensions and independent output oracles. Keep
per-OS compiler/hardware/architecture details, raw observations and paired
intervals. Compare improvement ratios within each OS and report absolute
throughput separately across different hardware. A successful build or an
unmeasured portability fallback does not prove a performance improvement on
another OS. The implementation was subsequently measured on native macOS and Windows. The cross-OS similarity requirement remains unachieved; see the measured negative evidence below.

## Invariant parameter remainder: compiler implementation

A compiler-only change now caches an exact reciprocal for stable, unshadowed
integer parameters used as divisors in loops. The preparation keeps its own
`divisor > 1` guard; negative dividends/divisors, exceptional cases and targets
without int128 retain checked signed remainder. The scan rejects all writes,
shadowing and move/coroutine paths, is bounded, and avoids generated-name
collisions. OMO reviewed the arithmetic and hoisting guard; one incorrect
special-case explanation was corrected against exact integer calculation.

With matched small-prime filters in both languages, the independent-seed
120-group repeat measured LCG 1.5024 [1.4996,1.5061], primes 1.5616
[1.5408,1.5752], scan 2.2639 [2.2523,2.2712], builder 1.2148
[1.1358,1.2764] and immutable 13.1377 [11.3787,17.1067] Rust/Forge
throughput. All five row-wise lower bounds exceed 1.10 in this run. Direct
baseline Forge speedups were 0.9984/1.5272/1.1634/1.0725/1.0009; LCG's
small regression is retained in the report, and immutable's direct interval
includes no change. The earlier 60-group builder interval crossed 1.10,
so this does not prove stable cross-run or cross-OS support. No language-wide
completion is claimed. [Proof, implementation scope and validation](invariant-mod-lowering-2026-10-13.md), [120-group full measurements](invariant-mod-compiler-full-120-2026-10-12.json), [OMO arithmetic review and correction](invariant-mod-omo-review-2026-10-12.md).


## Native cross-OS evidence and Windows fixes

The unchanged compiler was measured twice on native Windows after fixing temporary-file collision handling, const-correct spawn arguments, CRT file close/stat ABI, canonical source checking and the Rust control's QPC link order. Both native Windows API tests and all workload checks passed. Windows prime throughput gained about 5.6% versus old Forge and reached about 1.24× Rust, but scan and builder reached only about 0.53× and 0.77× Rust. Virtual Apple M1 prime throughput repeatedly fell to about 0.73× old Forge and 0.70× Rust. Identical Linux OS runners also differed by CPU: about 0.80× old Forge on EPYC 7763 versus 1.21× on Xeon 8573C. The current evidence contradicts a blanket similar effect across OSes and does not complete the 1.10 target.

Eight attempts preserve all 40 job outcomes, 26 completed reports and four failed-before-measurement reports. Generated-C bounded-range and forced-inline experiments failed to solve the ARM64 regression and remain rejected. Reserved-buffer and hardware-remainder prototypes are being measured separately; their results cannot be credited to the shipped compiler. [Cross-OS protocol, all current workload intervals, failures and OMO proof corrections](cross-os-verification-2026-10-13.md), [run ledger](cross-os-attempts-2026-10-13.json).


## Private reserved-builder compiler lowering

Compiler `d4c632b` now moves the capacity check out of a proven private, pure byte-fill loop, while preserving the checked fallback, wrapping byte expression, allocation lifetime and finish API. All 22 Linux CTest suites pass, including signed-boundary/UBSan/ABI-only/JavaScript oracles, capacity/allocation fallback cases and rejection of escaping or observable loops. In the local unchanged-compiler 60-group builder measurement, throughput was 1.3944× old Forge and 1.4777× Rust; this does not complete the full suite.

The preceding six native generated-C screening jobs showed positive builder gains on macOS, Linux and Windows, although Windows remained below Rust 1.10. All samples and the rejected hardware-remainder variant are preserved. The actual compiler cross-OS verification run 38339445212 completed successfully, with all 720 direct checks, 5400 prewarms and 5400 measured executions matching. Builder throughput improves old Forge on all tested OSes: Linux 1.27–1.29×, macOS 2.25–2.28× and Windows 1.19–1.30×, each row-wise lower 95% bound above 1.10. This proves a positive cross-OS effect for the private builder workload; Windows builder remains below Rust, and prime/scan gaps keep the overall goal unachieved. [Proof and benchmark scope](reserved-builder-lowering-2026-10-13.md).


## Guarded scan/arithmetic screening and generic LCG loop implementation

A six-job native generated-C experiment compared current d4c632b against the same producer with guarded positive arithmetic and 13-byte periodic weighting. Every native scan and builder row exceeded Rust 1.10; scan gained roughly 9× current Forge on macOS, 4.4–10.2× on Windows and 2.6× on Linux. macOS prime still reached only about 0.95–0.96× Rust, so the overall goal remains unachieved. The [complete current-control report](hybrid-range-cross-os-2026-10-13.md) preserves all rows and intervals and is explicitly a prototype, not a new compiler release.

The demonstrated LCG range-guard removal is now implemented generically in compiler 5481e3a, without matching benchmark names. Full-width/affine arithmetic and matcher checks pass; [proof and test correction](mersenne-loop-lowering-2026-10-13.md). Actual compiler native verification run 38349470617 remains running; bounded modular-power precision screening run 38348975326 completed all six jobs, with its artifacts pending download/assessment. General periodic-scan/compiler integration and the remaining macOS prime gap still require work.
