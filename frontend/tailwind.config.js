/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f1c18",
        moss: "#1f4d3a",
        fern: "#3d7a5c",
        mist: "#e8f0eb",
        sand: "#f4efe6",
        ember: "#c45c26",
      },
      fontFamily: {
        display: ['"Fraunces"', "Georgia", "serif"],
        body: ['"Source Sans 3"', "system-ui", "sans-serif"],
      },
      backgroundImage: {
        mesh: "radial-gradient(ellipse at 20% 0%, rgba(61,122,92,0.25), transparent 50%), radial-gradient(ellipse at 80% 20%, rgba(196,92,38,0.12), transparent 45%), linear-gradient(165deg, #f4efe6 0%, #e8f0eb 45%, #d9e8df 100%)",
      },
    },
  },
  plugins: [],
};
