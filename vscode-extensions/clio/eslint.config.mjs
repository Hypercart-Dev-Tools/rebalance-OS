import js from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    // Build output and dependencies are not ours to lint.
    ignores: ['dist/**', 'out-test/**', 'node_modules/**', 'docs/**'],
  },
  js.configs.recommended,
  {
    // Type-aware rules only where there is a TypeScript project behind the file.
    files: ['src/**/*.ts', 'test/**/*.ts'],
    extends: [...tseslint.configs.recommendedTypeChecked],
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  {
    // node:test's describe/it return promises the runner owns; awaiting them
    // is not the intended usage, so the floating-promise rule is noise here.
    files: ['test/**/*.ts'],
    rules: { '@typescript-eslint/no-floating-promises': 'off' },
  },
  {
    // Webview client: plain browser JS, no TypeScript project behind it.
    files: ['media/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'script',
      globals: {
        acquireVsCodeApi: 'readonly',
        document: 'readonly',
        window: 'readonly',
        requestAnimationFrame: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        Element: 'readonly',
        CSS: 'readonly',
      },
    },
  },
);
