import type { Config } from 'tailwindcss';
import { designTheme } from './design-system.tailwind.snippet';

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx,js,jsx}'],
  darkMode: 'class',
  corePlugins: { preflight: false },
  theme: designTheme,
  plugins: [],
};
export default config;
