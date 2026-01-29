/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: "#e60000",
        lagoon: "#008e97",
        curry: "#EFC900",
        "background-light": "#ffffff",
        "surface-light": "#f9f9f7",
        "surface-hover": "#f3f3f1",
        "text-main": "#1c1c1c",
        "text-sub": "#4b5563",
        "border-light": "#e5e7eb",
        "border-dark": "#d1d5db",
        // Docs-specific semantic colors
        "surface": "#ffffff",
        "surface-alt": "#f9f9f7",
        "text-primary": "#1c1c1c",
        "text-secondary": "#4b5563",
        "text-tertiary": "#9ca3af",
        "border": "#e5e7eb",
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        mono: ["Roboto Mono", "monospace"],
      },
      fontSize: {
        xs: ['10px', '14px'],      // --text-xs
        sm: ['11px', '16px'],      // --text-sm
        base: ['12px', '18px'],    // --text-base
        md: ['13px', '20px'],      // --text-md
        lg: ['14px', '20px'],      // --text-lg
        xl: ['16px', '24px'],      // --text-xl
        '2xl': ['18px', '26px'],   // --text-2xl
        '3xl': ['24px', '32px'],   // --text-3xl
        // Fluid typography that scales with viewport (for larger monitors)
        'fluid-sm': 'clamp(0.6875rem, 0.65rem + 0.1vw, 0.75rem)',      // 11px → 12px
        'fluid-base': 'clamp(0.75rem, 0.7rem + 0.15vw, 0.875rem)',     // 12px → 14px
        'fluid-lg': 'clamp(0.875rem, 0.8rem + 0.2vw, 1rem)',           // 14px → 16px
        'fluid-xl': 'clamp(1rem, 0.9rem + 0.25vw, 1.25rem)',           // 16px → 20px
        'fluid-2xl': 'clamp(1.125rem, 1rem + 0.35vw, 1.5rem)',         // 18px → 24px
        'fluid-3xl': 'clamp(1.5rem, 1.25rem + 0.5vw, 2rem)',           // 24px → 32px
        'fluid-hero': 'clamp(2rem, 1.5rem + 1vw, 3rem)',               // 32px → 48px (for hero headings)
      },
      borderRadius: {
        DEFAULT: "2px",
        'sm': "2px",
        'md': "2px",
        'lg': "4px",
        'full': "9999px",
      },
      boxShadow: {
        'subtle': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)',
        'floating': '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
      }
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
    require('@tailwindcss/container-queries'),
  ],
}
