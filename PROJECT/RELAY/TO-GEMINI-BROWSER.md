I need you to fact-check and refine GitHub PAT setup instructions against
GitHub's LIVE UI. Open these two pages and look at the actual interface
(don't answer from memory — the UI changes):

1. https://github.com/settings/tokens/new  (classic token creation)
2. https://github.com/settings/personal-access-tokens/new  (fine-grained)

## The instructions to verify (current text from our README)

> A GitHub Personal Access Token — either:
> - **classic token** with the `repo` scope (GitHub offers no read-only
>   private scope on classic tokens; `public_repo` alone makes your private
>   work invisible to discovery), or
> - **fine-grained token** — change *Repository access* from the default
>   **"Public repositories"** to *All repositories* (or the ones you work
>   in), with read-only **Contents** and **Metadata** permissions.

## Verify each claim against what you actually see

1. Classic page: confirm the exact scope checkbox labels. Is there truly no
   read-only repo scope? Is `public_repo`'s label still "Access public
   repositories"? Quote the real labels so our docs can mirror them.
2. Fine-grained page: what is the actual DEFAULT "Repository access"
   selection today? Quote the three options' exact wording.
3. Fine-grained permissions: are "Contents: Read-only" and "Metadata:
   Read-only" the correct minimal pair for reading commits, issues, PRs,
   and comments via the REST API — or do Issues/Pull requests need their own
   read permissions? (Our tool reads repo activity: commits, issues, PRs,
   issue comments.)
4. **The one I couldn't verify from code:** does a fine-grained PAT work
   with the REST **Events API** (`GET /users/{username}/events`)? Our
   discovery feature depends on that endpoint. Fine-grained PATs historically
   did NOT support the Events API — if that's still true, recommending
   fine-grained tokens is wrong for us and classic `repo` must be the
   primary recommendation. Check GitHub's docs page "Endpoints available
   for fine-grained personal access tokens" for the Events endpoints.
5. Expiration: what does the UI default token expiration to now? Our
   background jobs run unattended — should the instructions say anything
   about expiration so syncs don't silently die in 30/90 days?

## Output

A corrected version of the instruction block above with: exact UI labels as
they appear today, the fine-grained recommendation kept/dropped/demoted based
on the Events API answer, the minimal permission set confirmed, and one
sentence on expiration. Flag every place my draft disagreed with the live UI.
