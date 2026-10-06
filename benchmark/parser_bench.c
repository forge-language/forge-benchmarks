#define _POSIX_C_SOURCE 200809L
#include "parser.h"
#include <time.h>
static size_t reallocs;
void *__real_realloc(void *, size_t);
void *__wrap_realloc(void *p, size_t n) { reallocs++; return __real_realloc(p, n); }
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
int main(void) {
    const size_t count = 100000, iterations = 15;
    char *source = malloc(count * 40 + 1); size_t used = 0;
    for (size_t i = 0; i < count; ++i) used += sprintf(source + used, "extern fn f%zu();\n", i);
    double elapsed = 0; size_t calls = 0;
    for (size_t j = 0; j < iterations; ++j) {
        Lexer lx; lexer_init(&lx, source, used); reallocs = 0;
        double start = now(); Program p = parse_program(&lx); elapsed += now() - start;
        if (p.fn_count != count) return 1;
        calls += reallocs; program_free(&p);
    }
    printf("declarations=%zu iterations=%zu parse_seconds=%.9f realloc_calls=%zu\n", count, iterations, elapsed, calls);
    free(source);
}
