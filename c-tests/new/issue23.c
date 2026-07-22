#include <stdio.h>
#include <string.h>
#include <math.h>
int main (void) {
  char buf[1000], n;
  n = sprintf (buf, "%lf", NAN);
  n += sprintf (&buf[n], ";%lf", INFINITY);
  n += sprintf (&buf[n], ";%lf", HUGE_VAL);
  n += sprintf (&buf[n], ";%f", HUGE_VALF);
  n += sprintf (&buf[n], ";%Lf", HUGE_VALL);
  if (strcmp (buf, "nan;inf;inf;inf;inf") == 0) return 0;
#ifdef _WIN32
  if (strcmp (buf, "-nan(ind);inf;inf;inf;inf") == 0) return 0;
  if (strcmp (buf, "1.#QNAN0;1.#INF00;1.#INF00;1.#INF00;1.#INF00") == 0) return 0;
#endif
  return 1;
}
