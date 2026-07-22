extern void printf (const char *str, ...);
extern void exit (int);
#include <setjmp.h>

static jmp_buf env;

static void foo (void) {
  longjmp (env, 1);
  exit (1);
}
static void (*foop) (void) = foo;

static void bar (void) { (*foop) (); }
static void (*barp) (void) = bar;
#ifndef _WIN32
static int (*setjmp2) (jmp_buf) = setjmp;
#endif

int main (void) {
  int i = 42;
#ifdef _WIN32
  if (setjmp (env)) {
#else
  if (setjmp2 (env)) {
#endif
    return i != 42;
  }
  (*barp) ();
  return 1;
}
