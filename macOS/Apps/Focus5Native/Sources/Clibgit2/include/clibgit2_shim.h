/*
 * clibgit2_shim.h — Minimal hand-written libgit2 prototype shim (Phase 0-R spike).
 *
 * WHY THIS EXISTS: this environment has NO public libgit2 SDK header (`git2.h`
 * is absent everywhere on disk — see PHASE-0-R-FINDINGS.md). The only linkable
 * libgit2 on this machine is the arm64 dylib Xcode ships at
 *   /Applications/Xcode.app/Contents/Developer/usr/lib/libgit2.dylib
 * (936 git_* exports, confirmed via `nm`). To prove the *embedded, in-process*
 * git path links and runs under the App Sandbox, we declare by hand only the
 * handful of libgit2 C symbols the Focus 5 fact set needs and link against that
 * dylib. This is a SPIKE shim, NOT the shippable dependency (that would be a
 * proper macOS-sliced libgit2 xcframework / SwiftPM systemLibrary against a
 * bundled dylib — see findings doc).
 */
#ifndef CLIBGIT2_SHIM_H
#define CLIBGIT2_SHIM_H

#include <stddef.h>
#include <stdint.h>

typedef struct git_repository git_repository;
typedef struct git_reference  git_reference;
typedef struct git_commit     git_commit;
typedef struct git_status_list git_status_list;
typedef struct git_revwalk    git_revwalk;
typedef struct git_object     git_object;

typedef int64_t git_time_t;

/* git_oid — 20-byte SHA-1. */
typedef struct { unsigned char id[20]; } git_oid;

/* status flags subset we test. */
#define GIT_STATUS_WT_NEW      (1u << 7)
#define GIT_STATUS_INDEX_NEW   (1u << 0)

/* library lifecycle */
int  git_libgit2_init(void);
int  git_libgit2_shutdown(void);
int  git_libgit2_version(int *major, int *minor, int *rev);

/* error reporting */
typedef struct { char *message; int klass; } git_error;
const git_error *git_error_last(void);

/* repository */
int  git_repository_open(git_repository **out, const char *path);
void git_repository_free(git_repository *repo);
int  git_repository_head_detached(git_repository *repo);

/* references / HEAD */
int  git_repository_head(git_reference **out, git_repository *repo);
const char *git_reference_shorthand(const git_reference *ref);
int  git_reference_name_to_id(git_oid *out, git_repository *repo, const char *name);
void git_reference_free(git_reference *ref);

/* ahead/behind vs an upstream oid */
int  git_graph_ahead_behind(size_t *ahead, size_t *behind,
                            git_repository *repo,
                            const git_oid *local, const git_oid *upstream);

/* status (dirty / modified / untracked) */
typedef struct {
    unsigned int version;
    int show;
    uint32_t flags;
    /* pathspec strarray + baseline omitted; zeroed struct uses defaults */
    char **pathspec_strings;
    size_t pathspec_count;
    void *baseline;
    uint16_t rename_threshold;
} git_status_options;

#define GIT_STATUS_OPTIONS_VERSION 1
#define GIT_STATUS_OPT_INCLUDE_UNTRACKED (1u << 0)

typedef struct {
    unsigned int status;
    void *head_to_index;
    void *index_to_workdir;
} git_status_entry;

int    git_status_list_new(git_status_list **out, git_repository *repo,
                           const git_status_options *opts);
size_t git_status_list_entrycount(git_status_list *statuslist);
const git_status_entry *git_status_byindex(git_status_list *statuslist, size_t idx);
void   git_status_list_free(git_status_list *statuslist);

/* last-commit timestamp via HEAD commit */
int       git_commit_lookup(git_commit **commit, git_repository *repo, const git_oid *id);
git_time_t git_commit_time(const git_commit *commit);
void      git_commit_free(git_commit *commit);

#endif /* CLIBGIT2_SHIM_H */
