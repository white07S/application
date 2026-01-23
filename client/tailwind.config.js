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
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
        mono: ["Roboto Mono", "monospace"],
      },
      fontSize: {
        xs: ['12px', '16px'],
        sm: ['13px', '18px'],
        base: ['14px', '20px'],
        lg: ['18px', '24px'],
        xl: ['20px', '28px'],
        '2xl': ['24px', '32px'],
        '3xl': ['30px', '36px'],
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
