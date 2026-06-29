import { Orbitron, Rajdhani, Share_Tech_Mono } from "next/font/google";
import "./globals.css";

const orbitron = Orbitron({
  variable: "--font-orbitron",
  subsets: ["latin"],
  weight: ["400", "500", "700", "900"],
});

const rajdhani = Rajdhani({
  variable: "--font-rajdhani",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
});

const techMono = Share_Tech_Mono({
  variable: "--font-tech-mono",
  subsets: ["latin"],
  weight: ["400"],
});

export const metadata = {
  title: "S.H.I.E.L.D. Employee Portal — E.D.I.T.H. Gateway",
  description: "Secure tactical portal for Stark Industries fallback operations.",
};

export default function RootLayout({ children }) {
  return (
    <html
      lang="en"
      className={`${orbitron.variable} ${rajdhani.variable} ${techMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-[#030712] text-[#f3f4f6] font-sans selection:bg-[#ef4444] selection:text-black overflow-x-hidden">
        {children}
      </body>
    </html>
  );
}
