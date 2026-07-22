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

static char x86intrin_str[] = "#define __readgsqword(offset) 0ULL\n";
static char emmintrin_str[] = "";
#endif

static string_include_t standard_includes[] = {{NULL, mirc},
                                               {NULL, x86_64_mirc},
#ifdef _WIN32
                                               {NULL, win_compat_mirc},
                                               {"mm_malloc.h", mm_malloc_str},
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
