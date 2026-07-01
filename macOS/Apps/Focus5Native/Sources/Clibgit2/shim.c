/* Empty translation unit — the Clibgit2 target is a header-only shim whose
 * symbols are resolved at link time against the Xcode-shipped libgit2.dylib
 * (see Package.swift linkerSettings). A C target needs at least one .c file. */
#include "clibgit2_shim.h"
