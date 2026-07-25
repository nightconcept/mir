/* This file is a part of MIR project.
   Copyright (C) 2018-2024 Vladimir Makarov <vmakarov.gcc@gmail.com>.
*/

#include "../mirc.h"

#ifndef _WIN32
#include "mirc_x86_64_linux.h"
#else
#include "mirc_x86_64_win.h"
#endif

#include "mirc_x86_64_float.h"
#include "mirc_x86_64_limits.h"
#include "mirc_x86_64_stdarg.h"
#include "mirc_x86_64_stdint.h"
#include "mirc_x86_64_stddef.h"

#ifdef _WIN32
static char win_compat_mirc[]
  = "#define __stdcall\n"
    "#define __fastcall\n"
    "#define __thiscall\n"
    "#define __vectorcall\n"
    "#define FORCEINLINE static inline\n"
    "#define __builtin_offsetof(type, member) ((unsigned long long) &((type *) 0)->member)\n"
    "#define __CRT__NO_INLINE 1\n"
    "#define _INC_STRING_S 1\n";

static char mm_malloc_str[]
  = "#ifndef _MM_MALLOC_H_INCLUDED\n"
    "#define _MM_MALLOC_H_INCLUDED\n"
    "#include <stddef.h>\n"
    "void *_aligned_malloc (size_t, size_t);\n"
    "void _aligned_free (void *);\n"
    "static inline void *_mm_malloc (size_t size, size_t align) {\n"
    "  return _aligned_malloc (size, align);\n"
    "}\n"
    "static inline void _mm_free (void *ptr) { _aligned_free (ptr); }\n"
    "#endif\n";

/* MSVC's <vadefs.h> is the root of the CRT header lattice and expands va_start
   to __va_start, a compiler intrinsic c2m has no symbol for -- every CRT header
   that inlines a printf-family function then fails to link with "can not load
   symbol __va_start".  Supply the same contract in terms of c2m's own builtins.
   Scoped to _MSC_VER because ADDITIONAL_INCLUDE_PATH only points at the MSVC
   header set in an MSVC build -- MinGW's own <vadefs.h> (pulled in by _mingw.h)
   is GCC-flavoured, already works, and must not be shadowed by this. */
#ifdef _MSC_VER
static char vadefs_str[]
  = "#ifndef _INC_VADEFS\n"
    "#define _INC_VADEFS\n"
    "#ifndef _W64\n"
    "#define _W64\n"
    "#endif\n"
    "#ifndef _UINTPTR_T_DEFINED\n"
    "#define _UINTPTR_T_DEFINED\n"
    "typedef unsigned long long uintptr_t;\n"
    "#endif\n"
    "#ifndef _VA_LIST_DEFINED\n"
    "#define _VA_LIST_DEFINED\n"
    "typedef char *va_list;\n"
    "#endif\n"
    "#define _ADDRESSOF(v) (&(v))\n"
    "#define __crt_va_start_a(ap, v) __builtin_va_start (ap, v)\n"
    "#define __crt_va_start(ap, v) __builtin_va_start (ap, v)\n"
    "#define __crt_va_arg(ap, t) __builtin_va_arg (ap, (t *) 0)\n"
    "#define __crt_va_end(ap) ((void) 0)\n"
    "#define _crt_va_start(ap, v) __crt_va_start (ap, v)\n"
    "#define _crt_va_arg(ap, t) __crt_va_arg (ap, t)\n"
    "#define _crt_va_end(ap) __crt_va_end (ap)\n"
    "#endif\n";

#endif

/* MSVC's <setjmp.h> does `#define setjmp _setjmp` and declares _setjmp as taking the
   jmp_buf alone, because on x64 _setjmp is a compiler intrinsic: cl.exe passes the
   caller's frame pointer as a hidden second argument, which _setjmp stores in
   jmp_buf's leading Frame field.  c2m has no such intrinsic, so it emitted a one-
   argument call and left Frame holding whatever was in rdx; longjmp then took that
   for a real frame and handed it to RtlUnwindEx, faulting with STATUS_STACK_OVERFLOW
   in every -eg/-O mode (the interpreter survived only by accident).

   Pass an explicit 0 instead.  A zero Frame is the documented "do not unwind" case:
   longjmp restores the saved registers directly rather than running an SEH unwind.
   That is both what C requires of setjmp/longjmp and the only thing JIT-generated
   code can support, having no unwind info to unwind through.  jmp_buf must keep
   UCRT's shape (16 x 16 bytes, 16-byte aligned) since ucrtbase writes it -- the
   array-of-SETJMP_FLOAT128 spelling is what gets the alignment.

   This is not MSVC-only: MinGW's <setjmp.h> needs the same replacement whenever it
   resolves against UCRT (zig's bundled mingw-w64 headers, ucrt64 msys2), where it
   spells the call `_setjmp` -> `__intrinsic_setjmpex`.  That name reaches
   MIR_load_external as `__intrinsic_setjmpex`, which does not match the
   setjmp/_setjmp names mir.c records setjmp_addr for, so the interpreter's special
   CALL handling never fires: longjmp restores the FFI shim's native frame and
   interpretation resumes at the wrong point (-ei only; -eg/-O have real frames).
   An msvcrt-targeted MinGW emits plain `_setjmp` and happened to work.  Registering
   this header for every _WIN32 build makes all four combinations emit the one call
   shape -- `_setjmp (buf, 0)` -- that both the interpreter and the generator handle. */
static char setjmp_str[]
  = "#ifndef _INC_SETJMP\n"
    "#define _INC_SETJMP\n"
    "#ifndef _JMP_BUF_DEFINED\n"
    "#define _JMP_BUF_DEFINED\n"
    "typedef struct _SETJMP_FLOAT128 { unsigned long long Part[2]; } SETJMP_FLOAT128;\n"
    "#define _JBLEN 16\n"
    "typedef SETJMP_FLOAT128 _JBTYPE;\n"
    "typedef _JBTYPE jmp_buf[_JBLEN];\n"
    "#endif\n"
    "int _setjmp (jmp_buf, void *);\n"
    "void longjmp (jmp_buf, int);\n"
    "#define setjmp(buf) _setjmp ((buf), 0)\n"
    "#endif\n";

static char x86intrin_str[] = "#define __readgsqword(offset) 0ULL\n";
static char emmintrin_str[] = "";
#endif

static string_include_t standard_includes[] = {{NULL, mirc},
                                               {NULL, x86_64_mirc},
#ifdef _WIN32
                                               {NULL, win_compat_mirc},
                                               {"mm_malloc.h", mm_malloc_str},
#ifdef _MSC_VER
                                               {"vadefs.h", vadefs_str},
#endif
                                               {"setjmp.h", setjmp_str},
                                               {"x86intrin.h", x86intrin_str},
                                               {"emmintrin.h", emmintrin_str},
#endif
                                               TARGET_STD_INCLUDES};

#define MAX_ALIGNMENT 16

#define ADJUST_VAR_ALIGNMENT(c2m_ctx, align, type) x86_adjust_var_alignment (c2m_ctx, align, type)

static int x86_adjust_var_alignment (c2m_ctx_t c2m_ctx, int align, struct type *type) {
  /* see https://gitlab.com/x86-psABIs/x86-64-ABI */
  if (type->mode == TM_ARR && raw_type_size (c2m_ctx, type) >= 16) return 16;
  return align;
}

static int invalid_alignment (mir_llong align) {
  return align != 0 && align != 1 && align != 2 && align != 4 && align != 8 && align != 16;
}
