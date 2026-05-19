// Importación de las configuraciones recomendadas de ESLint para JavaScript
import js from '@eslint/js'
// Importación de variables globales (como 'window' o 'document') para que ESLint las reconozca
import globals from 'globals'
// Plugin para asegurar que los Hooks de React (useEffect, useState) se usen correctamente
import reactHooks from 'eslint-plugin-react-hooks'
// Plugin para permitir el "Hot Reload" (actualización rápida) en Vite sin perder el estado
import reactRefresh from 'eslint-plugin-react-refresh'
// Utilidades de configuración de ESLint para definir reglas e ignorar carpetas
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  // Indica a ESLint que ignore por completo la carpeta de compilación 'dist'
  globalIgnores(['dist']),
  {
    // Aplica esta configuración a todos los archivos con extensión .js y .jsx
    files: ['**/*.{js,jsx}'],
    // Extiende (copia) las reglas recomendadas de JS, React Hooks y Vite
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    // Configuración del entorno de lenguaje
    languageOptions: {
      ecmaVersion: 2020, // Soporte para características de JavaScript 2020
      globals: globals.browser, // Define que el código corre en un navegador
      parserOptions: {
        ecmaVersion: 'latest', // Usa la versión más reciente de ECMAScript
        ecmaFeatures: { jsx: true }, // Habilita el soporte para sintaxis JSX (React)
        sourceType: 'module', // Permite el uso de 'import' y 'export'
      },
    },
    // Reglas específicas personalizadas para SmartGuard
    rules: {
      // Configuración de variables no usadas:
      // Lanza un error si hay variables sin usar, a menos que empiecen con Mayúscula o guion bajo
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
    },
  },
])