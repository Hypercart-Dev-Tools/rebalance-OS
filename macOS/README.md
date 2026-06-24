# Text Replacement Studio

A Swift package for managing macOS Text Replacements: a SwiftUI app, a CLI, and a reusable core library.

Contents:

- `TextReplacementCore`: the core library — codecs (Apple plist, JSON), importers/exporters, GRDB-backed SQLite storage, and lint/merge services.
- `TextReplacementStudio`: the SwiftUI macOS app.
- `trstudio`: an ArgumentParser-based CLI.

The architecture is protocol-first: storage and import/export engines sit behind the interfaces in `TextReplacementCore`.

## Install the app

Build, bundle, and install Text Replacement Studio to `/Applications` (release build, real icon, ad-hoc signed):

```bash
./make-app.sh                # or: ./make-app.sh --no-install to assemble into ./dist only
```

## Build / develop

```bash
swift build
```

> If `swift build` fails with `fatal: cannot use bare repository … (safe.bareRepository is 'explicit')`,
> either use `./make-app.sh` (which already handles it) or prefix the command:
> `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.bareRepository GIT_CONFIG_VALUE_0=all swift build`

## Run the CLI

```bash
swift run trstudio list
swift run trstudio lint
swift run trstudio export --format apple-plist --output ./TextReplacements.plist
```

## Run the SwiftUI app (dev)

```bash
swift run TextReplacementStudio
```

`swift run` launches a bare development build. For a packaged, double-clickable `.app` installed to `/Applications`, use `./make-app.sh` (see **Install the app** above).
