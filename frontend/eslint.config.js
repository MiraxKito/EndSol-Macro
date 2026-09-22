import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // The pywebview bridge and several legacy configuration payloads are
      // intentionally dynamic: Python serializes arbitrary JSON objects and
      // optional methods are discovered at runtime. These values cannot be
      // represented honestly with `unknown` without adding unsafe casts at
      // every call site. Keep type-checking enabled, but do not reject the
      // explicit bridge types used for this boundary.
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
])
